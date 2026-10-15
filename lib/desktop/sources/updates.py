"""Tema `updates`: actualizaciones pendientes de pacman y AUR.

- Consulta con `checkupdates` (pacman-contrib: usa una base de datos temporal, nunca toca
  la del sistema ni requiere root) y con el helper AUR instalado (`paru -Qua`/`yay -Qua`).
- Resultado en caché; se vuelve a consultar según updates.refresh_minutes y cuando cambia
  /var/lib/pacman/local (es decir, tras cualquier transacción de pacman).
- Nunca actualiza en silencio: `update` abre una terminal interactiva.
"""
import asyncio
import json
import os
import time

from .. import config, paths
from ..daemon import Source
from ..util import have, log, run, spawn_detached, terminal_command

OFFICIAL = {"core", "extra", "multilib", "core-testing", "extra-testing", "multilib-testing"}
PACMAN_LOCAL = "/var/lib/pacman/local"


def aur_helper(preferred: str) -> str:
    if preferred not in ("", "auto", "none") and have(preferred):
        return preferred
    if preferred == "none":
        return ""
    return next((h for h in ("paru", "yay") if have(h)), "")


class UpdatesSource(Source):
    topic = "updates"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.cache = paths.CACHE_DIR / "updates.json"
        self.status = "idle"
        self.data: dict = {"packages": [], "checked": 0, "error": ""}
        self._lock = asyncio.Lock()

    def _publish(self) -> None:
        pk = self.data.get("packages", [])
        checked = self.data.get("checked", 0)
        self.publish({
            "count": len(pk), "packages": pk, "status": self.status, "error": self.data.get("error", ""),
            "checked": time.strftime("%H:%M", time.localtime(checked)) if checked else "nunca",
            "aur_helper": aur_helper(config.load().get("updates", {}).get("aur_helper", "auto")),
            "available": have("checkupdates"),
        })

    async def start(self) -> None:
        self.data = config.read_state(self.cache, self.data)
        self._publish()
        if not have("checkupdates"):
            self.data["error"] = "Falta pacman-contrib (checkupdates)"
            self._publish()
            return
        interval = 60 * float(config.load().get("updates", {}).get("refresh_minutes", 60))
        last_db = _mtime(PACMAN_LOCAL)
        if time.time() - self.data.get("checked", 0) > interval:
            await self.check()
        while True:
            await asyncio.sleep(30)  # stat barato; la consulta real solo si toca
            db = _mtime(PACMAN_LOCAL)
            if db != last_db or time.time() - self.data.get("checked", 0) > interval:
                last_db = db
                await self.check()

    async def check(self) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            self.status = "checking"
            self._publish()
            helper = aur_helper(config.load().get("updates", {}).get("aur_helper", "auto"))
            (c1, repo_out, err1), (c2, aur_out, _), (_, sl, _) = await asyncio.gather(
                run("checkupdates", "--nocolor", timeout=120),
                run(helper, "-Qua", timeout=120) if helper else _empty(),
                run("pacman", "-Sl", timeout=30),
                )
            repo_of = {}
            for line in sl.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    repo_of.setdefault(parts[1], parts[0])
            packages, error = [], ""
            # checkupdates: 0 = hay actualizaciones, 2 = ninguna, otro = error
            if c1 not in (0, 2):
                error = (err1.strip().splitlines() or ["checkupdates falló"])[-1]
            for line in repo_out.splitlines():
                p = _parse(line)
                if p:
                    repo = repo_of.get(p["name"], "")
                    packages.append({**p, "repo": repo, "origin": "oficial" if repo in OFFICIAL else (repo or "repo")})
            for line in aur_out.splitlines():
                p = _parse(line)
                if p and not line.endswith("[ignored]"):
                    packages.append({**p, "repo": "aur", "origin": "aur"})
            packages.sort(key=lambda p: (p["origin"] != "oficial", p["name"]))
            self.data = {"packages": packages, "checked": time.time(), "error": error}
            config.write_json(self.cache, self.data)
            self.status = "idle"
            self._publish()

    # ---- órdenes -------------------------------------------------------------
    async def cmd_refresh(self) -> None:
        await self.check()

    async def cmd_update(self) -> str:
        settings = config.load()
        helper = aur_helper(settings.get("updates", {}).get("aur_helper", "auto"))
        upgrade = f"{helper} -Syu" if helper else "sudo pacman -Syu"
        inner = (f"echo 'hyprland-desktop: {upgrade}'; {upgrade}; s=$?; echo; "
                 f"echo \"Terminado (código $s). Pulsa Enter para cerrar.\"; read _")
        marker = paths.RUNTIME_DIR / "updating"
        marker.write_text(str(time.time()))
        cmd = terminal_command(settings["apps"]["terminal"], inner + f"; rm -f '{marker}'")
        spawn_detached(cmd)
        self.status = "updating"
        self._publish()
        asyncio.get_running_loop().create_task(self._wait_marker(marker))
        return "Actualización abierta en la terminal"

    async def _wait_marker(self, marker) -> None:
        while marker.exists():
            await asyncio.sleep(2)
        self.status = "idle"
        await self.check()

    async def cmd_changes(self) -> None:
        """Abre en la terminal la lista detallada (ver cambios)."""
        settings = config.load()
        names = " ".join(p["name"] for p in self.data.get("packages", []) if p["origin"] != "aur")
        inner = (f"pacman -Si {names} 2>/dev/null | grep -E '^(Name|Nombre|Version|Versión|Description|Descripción|Repository|Repositorio)' | less"
                 if names else "echo 'No hay paquetes de repositorios pendientes'; read _")
        spawn_detached(terminal_command(settings["apps"]["terminal"], inner))


async def _empty():
    return 0, "", ""


def _parse(line: str):
    # "nombre 1.0-1 -> 1.1-1"
    parts = line.split()
    if len(parts) >= 4 and parts[2] == "->":
        return {"name": parts[0], "old": parts[1], "new": parts[3]}
    return None


def _mtime(path: str) -> float:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0
