"""Tema `system`: usuario, equipo, batería, perfil de energía, sesión y estado de servicios."""
import asyncio
import os
import platform
import pwd
import socket
from pathlib import Path

from .. import config, paths
from ..daemon import Source
from ..util import have, run, spawn_detached

BATTERY_GLYPHS = ["󰂎", "󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹"]

# (etiqueta, tipo, unidad o proceso)
SERVICES = [
    ("PipeWire", "user", "pipewire.service"),
    ("WirePlumber", "user", "wireplumber.service"),
    ("PipeWire Pulse", "user", "pipewire-pulse.service"),
    ("NetworkManager", "system", "NetworkManager.service"),
    ("Bluetooth", "system", "bluetooth.service"),
    ("Perfiles de energía", "system", "power-profiles-daemon.service"),
    ("hypridle", "proc", "hypridle"),
    ("Fondo (awww)", "proc", "awww-daemon"),
]


def _avatar() -> str:
    user = pwd.getpwuid(os.getuid()).pw_name
    for p in (Path.home() / ".face", Path.home() / ".face.icon", Path(f"/var/lib/AccountsService/icons/{user}")):
        if p.is_file():
            return str(p)
    return str(paths.ASSETS_DIR / "icons" / "zombie.png")


def _os_name() -> str:
    try:
        for line in open("/etc/os-release", encoding="utf-8"):
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _battery() -> dict:
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            cap = int((bat / "capacity").read_text().strip())
            status = (bat / "status").read_text().strip()
        except (OSError, ValueError):
            continue
        charging = status in ("Charging", "Full")
        glyph = "󰂄" if status == "Charging" else BATTERY_GLYPHS[min(10, cap // 10)]
        return {"present": True, "percent": cap, "status": status, "charging": charging, "glyph": glyph}
    return {"present": False}


def _uptime() -> str:
    try:
        secs = int(float(open("/proc/uptime").read().split()[0]))
    except OSError:
        return ""
    d, h, m = secs // 86400, secs % 86400 // 3600, secs % 3600 // 60
    return (f"{d} d " if d else "") + f"{h} h {m} min"


class SystemSource(Source):
    topic = "system"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.static = {
            "user": pwd.getpwuid(os.getuid()).pw_name,
            "host": socket.gethostname(),
            "avatar": _avatar(),
            "os": _os_name(),
            "kernel": platform.release(),
            "assets": str(paths.ASSETS_DIR),
        }
        self.services: list = []
        self.profiles: list = []
        self.profile = ""
        self.can_hibernate = False
        self._icons = None

    async def start(self) -> None:
        self.can_hibernate = await self._can("CanHibernate")
        await self.refresh(full=True)
        battery = _battery()["present"]
        while True:  # sin batería basta con refrescar el tiempo de actividad cada minuto
            await asyncio.sleep(30 if battery else 60)
            await self.refresh(full=False)

    async def _can(self, method: str) -> bool:
        code, out, _ = await run("busctl", "--system", "call", "org.freedesktop.login1", "/org/freedesktop/login1",
                                 "org.freedesktop.login1.Manager", method)
        return code == 0 and '"yes"' in out

    async def refresh(self, full: bool = True) -> None:
        if full:
            await asyncio.gather(self._services(), self._power_profiles())
        settings = config.load()
        self.publish({
            **self.static,
            "wm": (self.hub.get("wm") or {}).get("wm", ""),
            "uptime": _uptime(),
            "battery": _battery(),
            "can_hibernate": self.can_hibernate,
            "power_profile": self.profile, "power_profiles": self.profiles,
            "services": self.services,
            "idle": settings.get("idle", {}),
            "quick_launch": self._quick_launch(settings),
            # escrito por config/hypr/modules/keybinds.lua al cargar la configuración
            "keybinds": config.read_state(paths.RUNTIME_DIR / "keybinds.json", []),
        })

    def _quick_launch(self, settings: dict) -> list:
        """Resuelve los iconos de los accesos rápidos: 'assets:x.png', 'theme:nombre', ruta o glifo."""
        out = []
        for i, item in enumerate(settings.get("quick_launch", [])):
            icon, image, glyph = item.get("icon", ""), "", ""
            if icon.startswith("assets:"):
                image = str(paths.ASSETS_DIR / "icons" / icon[7:])
            elif icon.startswith("theme:"):
                if self._icons is None:
                    from .apps import IconResolver
                    self._icons = IconResolver()
                image = self._icons.lookup(icon[6:], 32)
            elif icon.startswith(("/", "~")):
                image = str(Path(icon).expanduser())
            else:
                glyph = icon
            out.append({"index": i, "name": item.get("name", ""), "tooltip": item.get("tooltip", item.get("name", "")),
                        "exec": item.get("exec", ""), "image": image, "glyph": glyph or ("" if image else "󰀻")})
        return out

    async def _services(self) -> None:
        async def state(label, kind, unit):
            if kind == "proc":
                code, _, _ = await run("pgrep", "-x", unit)
                return {"name": label, "active": code == 0, "state": "activo" if code == 0 else "detenido"}
            args = ["systemctl", "--user"] if kind == "user" else ["systemctl"]
            _, out, _ = await run(*args, "is-active", unit)
            s = out.strip() or "desconocido"
            return {"name": label, "active": s == "active", "state": {"active": "activo", "inactive": "inactivo",
                                                                      "failed": "fallido"}.get(s, s)}
        self.services = list(await asyncio.gather(*(state(*s) for s in SERVICES)))

    async def _power_profiles(self) -> None:
        if not have("powerprofilesctl"):
            self.profiles, self.profile = [], ""
            return
        (_, cur, _), (_, lst, _) = await asyncio.gather(run("powerprofilesctl", "get"), run("powerprofilesctl", "list"))
        self.profile = cur.strip()
        self.profiles = [l.strip(" *:").strip() for l in lst.splitlines() if l.rstrip().endswith(":")]

    # ---- órdenes -------------------------------------------------------------
    async def cmd_refresh(self) -> None:
        await self.refresh(full=True)

    async def cmd_profile(self, name: str) -> None:
        await run("powerprofilesctl", "set", name)
        await self.refresh(full=True)

    async def cmd_power(self, action: str) -> str:
        """lock | logout | suspend | hibernate | reboot | poweroff (la confirmación la hace la interfaz)."""
        await self.hub.execute(["popup", "close"])
        if action == "lock":
            await run("loginctl", "lock-session")
        elif action == "logout":
            await self.hub.sources["wm"].wm.logout()
        elif action in ("suspend", "hibernate", "reboot", "poweroff"):
            if action == "hibernate" and not self.can_hibernate:
                return "La hibernación no está disponible en este equipo"
            await run("systemctl", action)
        else:
            return f"acción desconocida: {action}"
        return action

    async def cmd_launch(self, command: str) -> None:
        """Lanza un acceso rápido de settings.json ('@terminal' se resuelve a settings.apps.terminal)."""
        spawn_detached(config.resolve_app(config.load(), command))

    async def cmd_quick(self, index: str) -> None:
        items = config.load().get("quick_launch", [])
        i = int(index)
        if 0 <= i < len(items):
            await self.cmd_launch(items[i].get("exec", ""))

    async def cmd_edit_settings(self) -> None:
        settings = config.load()
        if not paths.USER_SETTINGS.exists():
            paths.USER_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            paths.USER_SETTINGS.write_text(paths.DEFAULT_SETTINGS.read_text())
        spawn_detached(f"{settings['apps'].get('editor', 'xdg-open')} '{paths.USER_SETTINGS}'")

    async def cmd_uptime(self) -> str:
        return _uptime()

