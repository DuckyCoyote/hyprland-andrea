"""Tema `switcher`: selector de ventanas abiertas (Alt+Tab).

Lista todas las ventanas (también las minimizadas), la usada más recientemente primero, y
preselecciona la anterior. El teclado lo captura el compositor con el modo «switcher»
(config/hypr/modules/keybinds.lua): Tab/flechas llaman a `next`/`prev`, Enter a `select` y
Escape a `popup close`. Elegir una ventana la enfoca en su monitor y espacio de trabajo.
"""
from ..daemon import Source
from .wm import ID_STRIDE

MAX_ITEMS = 14


class SwitcherSource(Source):
    topic = "switcher"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.items: list[dict] = []
        self.index = 0

    async def start(self) -> None:
        self._publish()

    @property
    def wm(self):
        return self.hub.sources["wm"]

    def _publish(self) -> None:
        self.publish({"items": [{**it, "selected": i == self.index} for i, it in enumerate(self.items)],
                      "index": self.index})

    async def _load(self) -> None:
        monitors = {m["name"]: m for m in self.wm.monitors}
        items = []
        for c in (await self.wm.wm.clients())[:MAX_ITEMS]:
            mon = monitors.get(c["monitor"], {})
            if c["minimized"]:
                where = "Minimizada"
            else:
                base = mon.get("index", 0) * ID_STRIDE
                slot = c["workspace"] - base if base < c["workspace"] <= base + ID_STRIDE else c["workspace"]
                where = f"Escritorio {slot} · Monitor {mon.get('index', 0) + 1}"
            items.append({"i": len(items), "address": c["address"], "class": c["class"],
                          "title": c["title"] or c["class"], "where": where, "minimized": c["minimized"],
                          "icon": await self.wm.window_icon(c["class"]) if c["class"] else ""})
        self.items = items
        self.index = 1 if len(items) > 1 else 0

    # ---- órdenes -------------------------------------------------------------
    async def cmd_open(self, monitor: str = "focused") -> str:
        popup = self.hub.sources["popup"]
        if popup.state["open"] == "switcher":  # Alt+Tab con el selector abierto: siguiente
            return await self.cmd_next()
        await self._load()
        if not self.items:
            return "no hay ventanas abiertas"
        self._publish()
        return await popup.cmd_open("switcher", monitor)

    async def cmd_next(self) -> str:
        if self.items:
            self.index = (self.index + 1) % len(self.items)
            self._publish()
        return str(self.index)

    async def cmd_prev(self) -> str:
        if self.items:
            self.index = (self.index - 1) % len(self.items)
            self._publish()
        return str(self.index)

    async def cmd_select(self, index: str = "") -> str:
        if index != "":
            self.index = int(index)
        if not 0 <= self.index < len(self.items):
            return "nada que seleccionar"
        target = self.items[self.index]
        await self.hub.sources["popup"].cmd_close()
        await self.wm.wm.focus_window(target["address"])
        return target["title"]
