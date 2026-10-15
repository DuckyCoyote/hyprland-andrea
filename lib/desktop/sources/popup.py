"""Tema `popup`: gestor de ventanas emergentes.

- Solo hay un popup abierto a la vez: abrir uno cierra el anterior.
- Se abre en el monitor desde el que se pulsó (la barra pasa su monitor) o, si se invoca
  con un atajo, en el monitor enfocado según el compositor.
- Opcionalmente abre detrás una capa transparente que cierra el popup al hacer clic fuera.
- Activa en el compositor un modo de teclado en el que Escape cierra el popup.
"""
import asyncio

from .. import config, eww, paths
from ..daemon import Source

POPUPS = {"launcher", "settings", "power", "network", "audio", "updates", "media", "weather", "calendar",
          "notifications", "keymap", "switcher"}
# Modo de teclado del compositor mientras el popup está abierto (por defecto: Escape cierra)
KEY_MODES = {"switcher": "switcher"}
CLOSER = "popup-closer"


class PopupSource(Source):
    topic = "popup"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.state = {"open": "", "monitor": "", "tab": "", "confirm": ""}

    async def start(self) -> None:
        self.publish(self.state)
        await self._close_windows()  # popups que quedaron abiertos de un daemon anterior

    @property
    def wm(self):
        return self.hub.sources["wm"]

    async def _resolve_monitor(self, monitor: str) -> str:
        if monitor and monitor != "focused":
            return monitor
        return await self.wm.wm.focused_monitor() or ""

    async def cmd_open(self, name: str, monitor: str = "", tab: str = "") -> str:
        if name not in POPUPS:
            return f"popup desconocido: {name}"
        monitor = await self._resolve_monitor(monitor)
        screen = self.wm.screen_of(monitor)
        if name == "launcher":  # abre en Favoritas (o en Todas si aún no hay ninguna)
            favs = config.read_state(paths.UI_STATE, {}).get("favorites", [])
            await asyncio.to_thread(eww.update, launcher_query="",
                                    launcher_cat="favorites" if favs else "all")
        if name == "keymap":  # la lista la reescribe Hyprland en cada recarga
            await self.hub.sources["system"].refresh(full=False)
        # Si Eww ya tiene la ventana abierta (en otro monitor, o de un daemon anterior), `eww open`
        # la dejaría donde está: se cierra cualquier popup salvo que sea el mismo en el mismo monitor.
        if self.state["open"] != name or self.state["monitor"] != monitor:
            await self._close_windows()
        self.state.update(open=name, monitor=monitor, tab=tab or self.state["tab"] if name == self.state["open"] else tab, confirm="")
        self.publish(dict(self.state))
        if config.load().get("popups", {}).get("close_on_click_outside", True):
            await asyncio.to_thread(eww.open_window, "popup_closer", CLOSER, screen)
        await asyncio.to_thread(eww.open_window, name, name, screen)
        await self.wm.wm.popup_mode(True, KEY_MODES.get(name, "popup"))
        return f"{name} abierto en {monitor or 'monitor por defecto'}"

    async def cmd_toggle(self, name: str, monitor: str = "", tab: str = "") -> str:
        target = await self._resolve_monitor(monitor)
        if self.state["open"] == name and self.state["monitor"] == target and (not tab or tab == self.state["tab"]):
            return await self.cmd_close()
        return await self.cmd_open(name, target, tab)

    async def _close_windows(self) -> None:
        active = await asyncio.to_thread(eww.active_windows)
        ids = [wid for wid in active if wid in POPUPS or wid == CLOSER]
        if ids:
            await asyncio.to_thread(eww.close, *ids)

    async def cmd_close(self) -> str:
        # primero se libera el teclado: si Eww no respondiera, Super seguiría funcionando
        await self.wm.wm.popup_mode(False)
        self.state.update(open="", confirm="")
        self.publish(dict(self.state))
        await self._close_windows()
        return "cerrado"

    async def reset(self) -> None:
        """Olvida el popup abierto y libera el teclado sin hablar con Eww (por si está colgado)."""
        await self.wm.wm.popup_mode(False)
        self.state.update(open="", confirm="")
        self.publish(dict(self.state))

    async def reopen(self) -> None:
        """Tras recargar o reiniciar Eww: vuelve a abrir el popup que estaba abierto (o libera el
        teclado si ya no se puede)."""
        name, monitor = self.state["open"], self.state["monitor"]
        if not name:
            return
        screen = self.wm.screen_of(monitor)
        active = await asyncio.to_thread(eww.active_windows_or_none)
        if active is None:
            await self.cmd_close()
            return
        if config.load().get("popups", {}).get("close_on_click_outside", True) and CLOSER not in active:
            await asyncio.to_thread(eww.open_window, "popup_closer", CLOSER, screen)
        if name not in active and not await asyncio.to_thread(eww.open_window, name, name, screen):
            await self.cmd_close()

    async def cmd_tab(self, tab: str) -> None:
        self.state["tab"] = tab
        self.publish(dict(self.state))

    async def cmd_confirm(self, action: str = "") -> None:
        """Paso de confirmación genérico (lo usa el menú de energía)."""
        self.state["confirm"] = action
        self.publish(dict(self.state))
