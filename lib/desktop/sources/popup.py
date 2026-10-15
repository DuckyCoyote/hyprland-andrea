"""Tema `popup`: gestor de ventanas emergentes.

- Solo hay un popup abierto a la vez: abrir uno cierra el anterior.
- Se abre en el monitor desde el que se pulsó (la barra pasa su monitor) o, si se invoca
  con un atajo, en el monitor enfocado según el compositor.
- Opcionalmente abre detrás una capa transparente que cierra el popup al hacer clic fuera.
- Activa en el compositor un modo de teclado en el que Escape cierra el popup.
"""
import asyncio

from .. import config, eww
from ..daemon import Source

POPUPS = {"launcher", "settings", "power", "network", "audio", "updates", "media", "weather", "calendar", "notifications"}
CLOSER = "popup-closer"


class PopupSource(Source):
    topic = "popup"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.state = {"open": "", "monitor": "", "tab": "", "confirm": ""}

    async def start(self) -> None:
        self.publish(self.state)

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
        if self.state["open"] and (self.state["open"] != name or self.state["monitor"] != monitor):
            await self._close_windows()
        self.state.update(open=name, monitor=monitor, tab=tab or self.state["tab"] if name == self.state["open"] else tab, confirm="")
        self.publish(dict(self.state))
        if config.load().get("popups", {}).get("close_on_click_outside", True):
            await asyncio.to_thread(eww.open_window, "popup_closer", CLOSER, screen)
        await asyncio.to_thread(eww.open_window, name, name, screen)
        await self.wm.wm.popup_mode(True)
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
        await self._close_windows()
        self.state.update(open="", confirm="")
        self.publish(dict(self.state))
        await self.wm.wm.popup_mode(False)
        return "cerrado"

    async def cmd_tab(self, tab: str) -> None:
        self.state["tab"] = tab
        self.publish(dict(self.state))

    async def cmd_confirm(self, action: str = "") -> None:
        """Paso de confirmación genérico (lo usa el menú de energía)."""
        self.state["confirm"] = action
        self.publish(dict(self.state))
