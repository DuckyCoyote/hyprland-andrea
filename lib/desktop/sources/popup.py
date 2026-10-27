"""Tema `popup`: gestor de ventanas emergentes.

- Solo hay un popup abierto a la vez: abrir uno cierra el anterior.
- Se abre en el monitor desde el que se pulsó (la barra pasa su monitor) o, si se invoca
  con un atajo, en el monitor enfocado según el compositor.
- Opcionalmente abre detrás una capa transparente que cierra el popup al hacer clic fuera.
- Activa en el compositor un modo de teclado en el que Escape cierra el popup.
"""
import asyncio
import time

from .. import config, eww, paths
from ..daemon import Source

POPUPS = {"launcher", "startmenu", "settings", "power", "network", "bluetooth", "audio", "updates", "media", "weather", "calendar",
          "notifications", "keymap", "switcher", "groups"}
# Modo de teclado del compositor mientras el popup está abierto (por defecto: Escape cierra)
KEY_MODES = {"switcher": "switcher", "power": "power", "groups": "groups"}
# Menú de energía: orden de las filas y acciones que piden confirmación (power.yuck)
POWER_ACTIONS = ["lock", "suspend", "hibernate", "logout", "reboot", "poweroff"]
POWER_CONFIRM = {"logout", "reboot", "poweroff"}
CLOSER = "popup-closer"
# Con la barra inferior (bar_style «taskbar») los popups se abren abajo, junto a la barra, en el
# lado de su botón; los centrados no cambian. El lanzador pasa a ser el menú de inicio.
BOTTOM_LEFT = {"weather"}
CENTERED = {"keymap", "switcher", "startmenu", "groups"}
# Tras abrir o cerrar con toggle, se ignoran más toggles durante este tiempo (doble clic o clics
# impacientes): abrir y cerrar a la vez una ventana pesada como Configuración bloquea Eww.
TOGGLE_COOLDOWN = 0.5


class PopupSource(Source):
    topic = "popup"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.state = {"open": "", "monitor": "", "tab": "", "confirm": "", "sel": "", "csel": ""}
        self._busy = asyncio.Lock()  # una sola apertura/cierre a la vez
        self._last_toggle = 0.0

    async def start(self) -> None:
        self.publish(self.state)
        await self._close_windows()  # popups que quedaron abiertos de un daemon anterior

    @property
    def wm(self):
        return self.hub.sources["wm"]

    @staticmethod
    def _taskbar() -> bool:
        return config.load().get("appearance", {}).get("bar_style") == "taskbar"

    def _alias(self, name: str) -> str:
        return "startmenu" if name == "launcher" and self._taskbar() else name

    def _placement(self, name: str) -> dict:
        if name in CENTERED or not self._taskbar():
            return {}
        return {"anchor": "bottom left" if name in BOTTOM_LEFT else "bottom right", "pos": "10x0"}

    async def _resolve_monitor(self, monitor: str) -> str:
        if monitor and monitor != "focused":
            return monitor
        return await self.wm.wm.focused_monitor() or ""

    async def cmd_open(self, name: str, monitor: str = "", tab: str = "") -> str:
        async with self._busy:
            return await self._open(name, monitor, tab)

    async def _open(self, name: str, monitor: str = "", tab: str = "") -> str:
        name = self._alias(name)
        if name not in POPUPS:
            return f"popup desconocido: {name}"
        monitor = await self._resolve_monitor(monitor)
        screen = self.wm.screen_of(monitor)
        if name == "launcher":  # abre en Favoritas (o en Todas si aún no hay ninguna)
            favs = config.read_state(paths.UI_STATE, {}).get("favorites", [])
            await asyncio.to_thread(eww.update, launcher_query="",
                                    launcher_cat="favorites" if favs else "all")
        if name == "startmenu":
            await asyncio.to_thread(eww.update, launcher_query="", start_view="pinned")
        if name == "keymap":  # la lista la reescribe Hyprland en cada recarga
            await self.hub.sources["system"].refresh(full=False)
        # Si Eww ya tiene la ventana abierta (en otro monitor, o de un daemon anterior), `eww open`
        # la dejaría donde está: se cierra cualquier popup salvo que sea el mismo en el mismo monitor.
        if self.state["open"] != name or self.state["monitor"] != monitor:
            await self._close_windows()
        self.state.update(open=name, monitor=monitor, tab=tab or self.state["tab"] if name == self.state["open"] else tab, confirm="",
                          sel=self._initial_sel(name), csel="")
        self.publish(dict(self.state))
        if config.load().get("popups", {}).get("close_on_click_outside", True):
            await asyncio.to_thread(eww.open_window, "popup_closer", CLOSER, screen)
        await asyncio.to_thread(eww.open_window, name, name, screen, None, **self._placement(name))
        await self.wm.wm.popup_mode(True, KEY_MODES.get(name, "popup"))
        return f"{name} abierto en {monitor or 'monitor por defecto'}"

    async def cmd_toggle(self, name: str, monitor: str = "", tab: str = "") -> str:
        if self._busy.locked() or time.monotonic() - self._last_toggle < TOGGLE_COOLDOWN:
            return "ignorado (doble clic)"
        async with self._busy:
            try:
                name = self._alias(name)
                target = await self._resolve_monitor(monitor)
                if self.state["open"] == name and self.state["monitor"] == target and (not tab or tab == self.state["tab"]):
                    return await self._close()
                return await self._open(name, target, tab)
            finally:
                self._last_toggle = time.monotonic()

    async def _close_windows(self) -> None:
        active = await asyncio.to_thread(eww.active_windows)
        ids = [wid for wid in active if wid in POPUPS or wid == CLOSER]
        if ids:
            await asyncio.to_thread(eww.close, *ids)

    async def cmd_close(self) -> str:
        async with self._busy:
            return await self._close()

    async def _close(self) -> str:
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
        if name not in active and not await asyncio.to_thread(eww.open_window, name, name, screen, None,
                                                               **self._placement(name)):
            await self.cmd_close()

    async def cmd_tab(self, tab: str) -> None:
        self.state["tab"] = tab
        self.publish(dict(self.state))

    async def cmd_confirm(self, action: str = "") -> None:
        """Paso de confirmación genérico (lo usa el menú de energía). Con teclado, la opción
        preseleccionada es «Cancelar»."""
        self.state.update(confirm=action, csel="cancel" if action else "")
        if action:
            self.state["sel"] = action
        self.publish(dict(self.state))

    def _initial_sel(self, name: str) -> str:
        if name == "power":
            return self._power_actions()[0]
        if name == "groups":  # preselecciona el grupo visible
            return str(self.wm.group)
        return ""

    # ---- selector de grupos de escritorios (modo «groups» del compositor) -----
    async def cmd_groups_nav(self, direction: str = "next") -> str:
        count = len((self.hub.get("wm") or {}).get("groups", [])) or 1
        i = int(self.state["sel"] or 0) + (-1 if direction == "prev" else 1)
        self.state["sel"] = str(i % count)
        self.publish(dict(self.state))
        return self.state["sel"]

    async def cmd_groups_select(self, number: str = "") -> str:
        """Enter (grupo marcado) o 1..N: cierra el selector y cambia a ese grupo."""
        number = number or str(int(self.state["sel"] or 0) + 1)
        await self.cmd_close()
        return await self.wm.cmd_group(number)

    async def cmd_groups_move(self, number: str = "") -> str:
        """Shift+1..N o el botón de una tarjeta: envía la ventana enfocada a ese grupo sin cerrar
        el selector (así se pueden repartir varias)."""
        number = number or str(int(self.state["sel"] or 0) + 1)
        return await self.wm.cmd_group_move(number)

    # ---- teclado del menú de energía (modo «power» del compositor) -----------
    def _power_actions(self) -> list[str]:
        can_hibernate = getattr(self.hub.sources.get("system"), "can_hibernate", False)
        return [a for a in POWER_ACTIONS if a != "hibernate" or can_hibernate]

    async def cmd_power_nav(self, direction: str = "next") -> str:
        """Tab/flechas: recorre las filas o, en la confirmación, alterna Cancelar/Sí."""
        if self.state["confirm"]:
            self.state["csel"] = "yes" if self.state["csel"] == "cancel" else "cancel"
        else:
            actions = self._power_actions()
            i = actions.index(self.state["sel"]) if self.state["sel"] in actions else -1
            i = (i + (-1 if direction == "prev" else 1)) % len(actions)
            self.state["sel"] = actions[i]
        self.publish(dict(self.state))
        return self.state["csel"] or self.state["sel"]

    async def cmd_power_select(self) -> str:
        """Enter: ejecuta la fila elegida (o pide confirmación) o la opción de la confirmación."""
        action = self.state["confirm"]
        if action:
            if self.state["csel"] == "yes":
                return await self.hub.sources["system"].cmd_power(action)
            await self.cmd_confirm()
            return "cancelado"
        action = self.state["sel"]
        if action in POWER_CONFIRM:
            await self.cmd_confirm(action)
            return f"¿{action}?"
        if action in POWER_ACTIONS:
            return await self.hub.sources["system"].cmd_power(action)
        return "nada que seleccionar"

    async def cmd_power_back(self) -> str:
        """Escape: sale de la confirmación o, si no la hay, cierra el menú."""
        if self.state["confirm"]:
            await self.cmd_confirm()
            return "cancelado"
        return await self.cmd_close()
