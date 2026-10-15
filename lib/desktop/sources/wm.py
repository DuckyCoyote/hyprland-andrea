"""Tema `wm`: monitores, espacios de trabajo por monitor y gestión de las barras."""
import asyncio
import time

from .. import config, eww
from ..daemon import Source
from ..util import Debouncer, log
from ..wm import detect

# Los espacios de cada monitor ocupan un bloque de ids: monitor 0 -> 1..N, monitor 1 -> 11..N+10...
# config/hypr/modules/workspaces.lua usa exactamente la misma regla.
ID_STRIDE = 10


class WmSource(Source):
    topic = "wm"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.wm = detect(config.load().get("wm", "auto"))
        self.monitors: list[dict] = []
        self.bars: set[str] = set()
        self._icon_names: dict[str, str] | None = None
        self._icons = None
        self._icon_cache: dict[str, str] = {}
        self._last_restart = 0.0
        self._refresh = Debouncer(0.03, self.refresh)
        self._monitors_changed = Debouncer(0.5, self.sync_bars)

    async def start(self) -> None:
        log(f"adaptador de compositor: {self.wm.name}")
        await self.refresh()
        await asyncio.to_thread(eww.start_daemon)
        await self.sync_bars()
        asyncio.create_task(self._watchdog())
        await self.wm.start(self.on_change)

    async def _watchdog(self) -> None:
        """Si Eww deja de responder, lo reinicia: un Eww colgado deja la capa de cierre de los
        popups cubriendo la pantalla y el teclado en modo popup («pantalla pegada»)."""
        failures = 0
        while True:
            await asyncio.sleep(5)
            if self.hub.eww_lock.locked():  # recarga en curso: es normal que tarde
                continue
            alive = await asyncio.to_thread(eww.running)
            failures = 0 if alive else failures + 1
            if failures < 2:
                continue
            failures = 0
            log("Eww no responde: reiniciándolo")
            popup = self.hub.sources["popup"]
            await popup.reset()  # libera el teclado sin esperar a Eww
            async with self.hub.eww_lock:
                await asyncio.to_thread(eww.restart_daemon)
                for _ in range(30):
                    if not await self.wm.count_layers("hd-bar"):
                        break
                    await asyncio.sleep(0.1)
                await self._sync_bars(retry=False)

    async def on_change(self, kind: str) -> None:
        self._refresh()
        if kind == "monitors":
            self._monitors_changed()

    def ordered_monitors(self, monitors: list[dict]) -> list[dict]:
        """Orden: los declarados en settings.json (el principal primero), después el resto por posición."""
        declared = config.load().get("monitors", [])
        primary = [m["name"] for m in declared if m.get("primary")]
        order = primary + [m["name"] for m in declared if m["name"] not in primary]
        known = sorted((m for m in monitors if m["name"] in order), key=lambda m: order.index(m["name"]))
        rest = sorted((m for m in monitors if m["name"] not in order), key=lambda m: (m["x"], m["y"]))
        return known + rest

    async def refresh(self) -> None:
        settings = config.load()
        per_monitor = int(settings.get("workspaces", {}).get("per_monitor", 6))
        self.monitors = self.ordered_monitors(await self.wm.monitors())
        existing = {w["id"]: w for w in await self.wm.workspaces()}
        result, used = {}, set()

        for index, mon in enumerate(self.monitors):
            base = index * ID_STRIDE
            items = []
            ids = [base + slot for slot in range(1, per_monitor + 1)]
            # espacios que viven en este monitor pero fuera de su bloque (p. ej. tras desconectar otro monitor)
            ids += sorted(i for i, w in existing.items() if w["monitor"] == mon["name"] and i not in ids)
            for wid in ids:
                w = existing.get(wid)
                if w and w["monitor"] != mon["name"]:
                    continue
                state = ("active" if mon["active_workspace"] == wid else
                         "urgent" if w and w["urgent"] else
                         "occupied" if w and w["windows"] > 0 else "empty")
                label = str(wid - base) if base < wid <= base + per_monitor else str(wid)
                items.append({"id": wid, "label": label, "state": state})
                used.add(wid)
            mon["index"] = index
            result[mon["name"]] = items

        active = await self.wm.active_windows()
        windows = {}
        for mon in self.monitors:
            win = active.get(mon["name"]) or {}
            cls = win.get("class", "")
            windows[mon["name"]] = {"class": cls, "title": win.get("title", ""),
                                    "icon": await self.window_icon(cls) if cls else ""}

        self.publish({
            "wm": self.wm.name,
            "windows": windows,
            "has_workspaces": self.wm.has_workspaces,
            "focused": next((m["name"] for m in self.monitors if m["focused"]), ""),
            "monitors": self.monitors,
            "workspaces": result,
        })

    async def window_icon(self, cls: str) -> str:
        """Ruta del icono de una clase de ventana (resuelto una vez y guardado en caché)."""
        key = cls.lower()
        if key not in self._icon_cache:
            def resolve() -> str:
                from .apps import IconResolver, window_icon_names
                if self._icon_names is None:
                    self._icon_names = window_icon_names()
                    self._icons = IconResolver()
                candidates = [self._icon_names.get(key), self._icon_names.get(key.rsplit(".", 1)[-1]), key]
                for name in filter(None, candidates):
                    found = self._icons.lookup(name, 32)
                    if found and "application-x-executable" not in found:
                        return found
                return ""
            self._icon_cache[key] = await asyncio.to_thread(resolve)
        return self._icon_cache[key]

    def screen_of(self, monitor: str | None):
        for m in self.monitors:
            if m["name"] == monitor:
                return m["screen"]
        return self.monitors[0]["screen"] if self.monitors else 0

    async def sync_bars(self) -> None:
        """Abre una barra por monitor conectado y cierra las de monitores desaparecidos."""
        async with self.hub.eww_lock:  # nunca a la vez que una recarga de Eww
            await self._sync_bars()

    async def _sync_bars(self, retry: bool = True) -> None:
        await self.refresh()
        bar = config.load().get("bar", {})
        default_modules = bar.get("modules", [])
        wanted = {}
        for m in self.monitors:
            modules = bar.get("per_monitor", {}).get(m["name"], default_modules)
            wanted[f"bar-{m['name']}"] = (m, "," + ",".join(modules) + ",")

        active = await asyncio.to_thread(eww.active_windows_or_none)
        if active is None:  # Eww ocupado: reintentar en lugar de abrir barras a ciegas
            if retry:
                await asyncio.sleep(1)
                await self._sync_bars(retry=False)
            return
        current = {wid for wid, name in active.items() if name == "bar"}
        stale = current - set(wanted)
        if stale:
            await asyncio.to_thread(eww.close, *stale)
        for wid, (mon, modules) in wanted.items():
            if wid not in current:
                await asyncio.to_thread(eww.open_window, "bar", wid, mon["screen"],
                                        {"monitor": mon["name"], "modules": modules})
        self.bars = set(wanted)

        # Red de seguridad: si Eww dejó barras huérfanas (superficies que ya no controla), solo
        # reiniciarlo las elimina. Se comprueba dos veces (las superficies de una recarga tardan
        # un instante en desaparecer) y como mucho una vez por minuto, para no entrar en bucle.
        if retry and await self._too_many_bars(len(wanted)):
            await asyncio.sleep(2)
            if await self._too_many_bars(len(wanted)) and time.monotonic() - self._last_restart > 60:
                self._last_restart = time.monotonic()
                log("barras huérfanas de Eww: reiniciando Eww")
                await asyncio.to_thread(eww.restart_daemon)
                for _ in range(30):  # esperar a que el compositor retire las superficies viejas
                    if not await self.wm.count_layers("hd-bar"):
                        break
                    await asyncio.sleep(0.1)
                await self._sync_bars(retry=False)
                await self.hub.sources["popup"].reopen()

    async def _too_many_bars(self, expected: int) -> bool:
        layers = await self.wm.count_layers("hd-bar")
        return layers is not None and layers > expected

    async def reload_eww(self) -> None:
        """Recarga Eww (tras regenerar estilos) y restablece barras y popup abierto."""
        # Con ventanas abiertas, `eww reload` las recrea en segundo plano y abrir otra a la vez
        # bloquea Eww: se cierran todas, se recarga sin ventanas y se vuelven a abrir.
        async with self.hub.eww_lock:
            await asyncio.to_thread(eww.close_all)
            await asyncio.to_thread(eww.reload)
            for _ in range(50):
                if await asyncio.to_thread(eww.running):
                    break
                await asyncio.sleep(0.1)
            else:
                log("Eww no respondió tras recargar: reiniciando Eww")
                await asyncio.to_thread(eww.restart_daemon)
            await self._sync_bars()
        await self.hub.sources["popup"].reopen()

    # ---- órdenes -------------------------------------------------------------
    async def cmd_focus(self, workspace_id: str) -> None:
        await self.wm.focus_workspace(int(workspace_id))

    async def cmd_scroll(self, monitor: str, direction: str) -> None:
        """Rueda del ratón sobre los espacios de la barra: siguiente/anterior dentro del monitor."""
        data = self.hub.get("wm") or {}
        items = data.get("workspaces", {}).get(monitor, [])
        ids = [w["id"] for w in items]
        current = next((w["id"] for w in items if w["state"] == "active"), None)
        if not ids or current is None:
            return
        step = 1 if direction in ("down", "next") else -1
        await self.wm.focus_workspace(ids[(ids.index(current) + step) % len(ids)])

    async def cmd_bars(self) -> str:
        await self.sync_bars()
        return f"barras: {', '.join(sorted(self.bars))}"

    async def cmd_logout(self) -> None:
        await self.wm.logout()

    async def cmd_reload(self) -> None:
        await self.wm.reload()
