"""Tema `wm`: monitores, espacios de trabajo por monitor y gestión de las barras."""
import asyncio

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
        self._refresh = Debouncer(0.03, self.refresh)
        self._monitors_changed = Debouncer(0.5, self.sync_bars)

    async def start(self) -> None:
        log(f"adaptador de compositor: {self.wm.name}")
        await self.refresh()
        await asyncio.to_thread(eww.start_daemon)
        await self.sync_bars()
        await self.wm.start(self.on_change)

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

        self.publish({
            "wm": self.wm.name,
            "has_workspaces": self.wm.has_workspaces,
            "focused": next((m["name"] for m in self.monitors if m["focused"]), ""),
            "monitors": self.monitors,
            "workspaces": result,
        })

    def screen_of(self, monitor: str | None):
        for m in self.monitors:
            if m["name"] == monitor:
                return m["screen"]
        return self.monitors[0]["screen"] if self.monitors else 0

    async def sync_bars(self) -> None:
        """Abre una barra por monitor conectado y cierra las de monitores desaparecidos."""
        await self.refresh()
        bar = config.load().get("bar", {})
        default_modules = bar.get("modules", [])
        wanted = {}
        for m in self.monitors:
            modules = bar.get("per_monitor", {}).get(m["name"], default_modules)
            wanted[f"bar-{m['name']}"] = (m, "," + ",".join(modules) + ",")

        active = await asyncio.to_thread(eww.active_windows)
        current = {wid for wid, name in active.items() if name == "bar"}
        stale = current - set(wanted)
        if stale:
            await asyncio.to_thread(eww.close, *stale)
        for wid, (mon, modules) in wanted.items():
            if wid not in current:
                await asyncio.to_thread(eww.open_window, "bar", wid, mon["screen"],
                                        {"monitor": mon["name"], "modules": modules})
        self.bars = set(wanted)

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
