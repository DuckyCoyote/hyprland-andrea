"""Tema `wm`: monitores, espacios de trabajo por monitor, grupos de escritorios y barras."""
import asyncio
import os
import shlex
import time

from .. import config, eww
from ..daemon import Source
from ..config import group_names
from ..util import Debouncer, log
from ..wm import detect

# Los espacios de cada monitor ocupan un bloque de ids: monitor 0 -> 1..N, monitor 1 -> 11..N+10...
# Cada grupo de escritorios repite los bloques 100 ids más arriba: grupo 2 -> 101..N+100, 111...
# config/hypr/modules/workspaces.lua y ctx.lua usan exactamente la misma regla.
ID_STRIDE = 10
GROUP_STRIDE = 100


def group_of(workspace_id: int | None) -> int:
    return workspace_id // GROUP_STRIDE if workspace_id and workspace_id > 0 else 0


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
        self._restarts: list[float] = []
        self._refresh = Debouncer(0.03, self.refresh)
        self._monitors_changed = Debouncer(0.5, self.sync_bars)
        self.group = 0
        self._last_ws: dict[tuple[int, str], int] = {}  # (grupo, monitor) -> último espacio visible
        self._switching = asyncio.Lock()

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
            await self.restart_eww()

    async def restart_eww(self) -> None:
        """Reinicio limpio de la interfaz: Eww nuevo (sin ventanas huérfanas), popups cerrados,
        teclado liberado y una barra por monitor."""
        await self.hub.sources["popup"].reset()  # libera el teclado sin esperar a Eww
        async with self.hub.eww_lock:
            await asyncio.to_thread(eww.restart_daemon)
            for _ in range(30):  # esperar a que el compositor retire las superficies viejas
                if not await self.wm.count_layers("hd-bar"):
                    break
                await asyncio.sleep(0.1)
            await self._sync_bars(retry=False)

    async def on_change(self, kind: str) -> None:
        self._refresh()
        if kind == "monitors":
            self._monitors_changed()
            self.hub.sources["displays"].on_monitors()

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
        names = group_names(settings)
        self.monitors = self.ordered_monitors(await self.wm.monitors())
        # el grupo visible es el del monitor enfocado; los demás monitores lo siguen
        focused_mon = next((m for m in self.monitors if m["focused"]), self.monitors[0] if self.monitors else None)
        group = group_of(focused_mon["active_workspace"]) if focused_mon else 0
        group = min(group, len(names) - 1)
        changed, self.group = group != self.group, group
        for m in self.monitors:
            if m["active_workspace"] and m["active_workspace"] > 0:
                self._last_ws[(group_of(m["active_workspace"]), m["name"])] = m["active_workspace"]
        # solo cuando el grupo enfocado cambia (p. ej. Alt+Tab a una ventana de otro grupo): así un
        # monitor que no pueda mostrar el grupo no provoca un bucle de cambios
        if changed and not self._switching.locked() and any(
                group_of(m["active_workspace"]) != group for m in self.monitors if m["active_workspace"]):
            asyncio.create_task(self.show_group(group))
        existing = {w["id"]: w for w in await self.wm.workspaces()}
        # iconos de las aplicaciones abiertas en cada espacio (barra «rectángulo»): uno por clase
        apps: dict[int, list[str]] = {}
        clients = await self.wm.clients()
        for c in clients:
            icon = await self.window_icon(c["class"]) if c["class"] else ""
            if icon and icon not in apps.setdefault(c["workspace"], []):
                apps[c["workspace"]].append(icon)
        result, used = {}, set()

        for index, mon in enumerate(self.monitors):
            base = group * GROUP_STRIDE + index * ID_STRIDE
            items = []
            ids = [base + slot for slot in range(1, per_monitor + 1)]
            # espacios del grupo que viven en este monitor pero fuera de su bloque (p. ej. tras
            # desconectar otro monitor)
            ids += sorted(i for i, w in existing.items()
                          if w["monitor"] == mon["name"] and i not in ids and group_of(i) == group)
            for wid in ids:
                w = existing.get(wid)
                if w and w["monitor"] != mon["name"]:
                    continue
                state = ("active" if mon["active_workspace"] == wid else
                         "urgent" if w and w["urgent"] else
                         "occupied" if w and w["windows"] > 0 else "empty")
                label = str(wid - base) if base < wid <= base + per_monitor else str(wid)
                items.append({"id": wid, "label": label, "state": state, "apps": apps.get(wid, [])[:4]})
                used.add(wid)
            mon["index"] = index
            result[mon["name"]] = items

        active = await self.wm.active_windows()
        windows = {}
        for mon in self.monitors:
            win = active.get(mon["name"]) or {}
            cls = win.get("class", "")
            name = cls.rsplit(".", 1)[-1]  # org.kde.dolphin -> Dolphin
            windows[mon["name"]] = {"class": cls, "title": win.get("title", ""),
                                    "name": name[:1].upper() + name[1:],
                                    "icon": await self.window_icon(cls) if cls else ""}

        focused = next((m["name"] for m in self.monitors if m["focused"]), "")
        groups = []
        for g, name in enumerate(names):
            wins = [c for c in clients if not c["minimized"] and group_of(c["workspace"]) == g]
            icons = []
            for c in wins:
                icon = await self.window_icon(c["class"]) if c["class"] else ""
                if icon and icon not in icons:
                    icons.append(icon)
            groups.append({"index": g, "number": g + 1, "name": name, "active": g == group,
                           "windows": len(wins), "apps": icons[:8]})
        self.publish({
            "wm": self.wm.name,
            "windows": windows,
            "tasks": await self.tasks(clients, windows.get(focused, {}).get("class", "")),
            "has_workspaces": self.wm.has_workspaces,
            "focused": focused,
            "monitors": self.monitors,
            "workspaces": result,
            "group": group,
            "group_name": names[group],
            "groups": groups,
        })

    async def tasks(self, clients: list[dict], focused_class: str) -> list[dict]:
        """Apps de la barra inferior: primero los accesos rápidos (fijados, marcados si están
        abiertos) y después el resto de apps abiertas, una por clase de ventana."""
        settings = config.load()
        by_class: dict[str, list[dict]] = {}
        for c in clients:  # ya vienen ordenadas por uso reciente
            if c["class"]:
                by_class.setdefault(c["class"], []).append(c)
        items, used = [], set()
        for q in (self.hub.get("system") or {}).get("quick_launch", []):
            key = _command_key(config.resolve_app(settings, q.get("exec", "")))
            cls = next((k for k in by_class if k not in used and _same_app(k, key)), "")
            used.add(cls)
            items.append({**q, "pinned": True, "class": cls, "count": len(by_class.get(cls, [])),
                          "focused": bool(cls) and cls == focused_class})
        for cls, wins in by_class.items():
            if cls in used:
                continue
            image = await self.window_icon(cls)
            items.append({"index": -1, "name": cls, "tooltip": wins[0]["title"] or cls, "exec": "",
                          "image": image, "glyph": "" if image else "\U000f05af", "pinned": False,
                          "class": cls, "count": len(wins), "focused": cls == focused_class})
        return items

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
        settings = config.load()
        bar = settings.get("bar", {})
        default_modules = bar.get("modules", [])
        # el estilo «Inferior» es otra ventana (anclada abajo); los demás comparten `bar`
        window = "bar-bottom" if settings.get("appearance", {}).get("bar_style") == "taskbar" else "bar"
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
        current = {wid: name for wid, name in active.items() if name in ("bar", "bar-bottom")}
        stale = {wid for wid, name in current.items() if wid not in wanted or name != window}
        if stale:
            await asyncio.to_thread(eww.close, *stale)
        for wid, (mon, modules) in wanted.items():
            if wid not in current or wid in stale:
                await asyncio.to_thread(eww.open_window, window, wid, mon["screen"],
                                        {"monitor": mon["name"], "modules": modules})
        self.bars = set(wanted)

        # Red de seguridad: si Eww dejó barras huérfanas (superficies que ya no controla) o abrió
        # alguna en otro monitor (al iniciar sesión GTK puede no conocer aún todos los monitores y
        # acababan dos barras en una pantalla y ninguna en la otra), solo reiniciarlo lo arregla.
        # Se comprueba dos veces (las superficies de una recarga tardan un instante en
        # desaparecer) y como mucho tres reinicios por minuto, para no entrar en bucle.
        if retry and await self._bars_misplaced(wanted):
            await asyncio.sleep(2)
            now = time.monotonic()
            self._restarts = [t for t in self._restarts if now - t < 60]
            if await self._bars_misplaced(wanted) and len(self._restarts) < 3:
                self._restarts.append(now)
                log("barras huérfanas o en otro monitor: reiniciando Eww")
                await asyncio.to_thread(eww.restart_daemon)
                for _ in range(30):  # esperar a que el compositor retire las superficies viejas
                    if not await self.wm.count_layers("hd-bar"):
                        break
                    await asyncio.sleep(0.1)
                await self._sync_bars(retry=len(self._restarts) < 3)
                await self.hub.sources["popup"].reset()

    async def _bars_misplaced(self, wanted: dict) -> bool:
        """True si algún monitor no tiene exactamente una barra (o sobran barras)."""
        layers = await self.wm.layers_per_monitor("hd-bar")
        if layers is None:
            return False
        monitors = {mon["name"] for mon, _ in wanted.values()}
        return (any(layers.get(name, 0) != 1 for name in monitors)
                or sum(layers.values()) > len(monitors))

    async def reload_eww(self) -> None:
        """Recarga Eww (tras regenerar estilos) y restablece barras y popup abierto."""
        # Con ventanas abiertas, `eww reload` las recrea en segundo plano y abrir otra a la vez
        # bloquea Eww: se cierran todas, se recarga sin ventanas y se vuelven a abrir.
        async with self.hub.eww_lock:
            await asyncio.to_thread(eww.close_all)
            if not await asyncio.to_thread(eww.reload):
                log("Eww no respondió tras recargar: reiniciando Eww")
                await asyncio.to_thread(eww.restart_daemon)
            await self._sync_bars()
        # el popup abierto se reabre cuando Eww ya terminó de recrear las barras: abrir una ventana
        # pesada (Configuración) justo tras recargar lo bloqueaba
        await asyncio.sleep(0.4)
        await self.hub.sources["popup"].reopen()

    # ---- grupos de escritorios ---------------------------------------------------
    def _group_target(self, group: int, mon: dict) -> int:
        """Espacio que mostrará `mon` al pasar al grupo: el último que vio ahí o el primero."""
        base = group * GROUP_STRIDE + mon["index"] * ID_STRIDE
        return self._last_ws.get((group, mon["name"]), base + 1)

    async def show_group(self, group: int, focus_ws: int | None = None) -> None:
        """Muestra el grupo en todos los monitores (cada uno en su último espacio de ese grupo).
        Las ventanas no se mueven: cada grupo conserva sus espacios y su distribución."""
        async with self._switching:
            mons = self.ordered_monitors(await self.wm.monitors())
            for index, m in enumerate(mons):
                m["index"] = index
            focused = next((m["name"] for m in mons if m["focused"]), mons[0]["name"] if mons else "")
            targets = {m["name"]: self._group_target(group, m) for m in mons}
            if focus_ws is not None:
                targets[focused] = focus_ws
            if all(m["active_workspace"] == targets[m["name"]] for m in mons):
                return
            await self.wm.show_workspaces(targets, focused)
            await asyncio.sleep(0.05)  # que lleguen los eventos antes de volver a comparar grupos
        self._refresh()

    def _parse_group(self, value: str) -> int:
        count = len(group_names(config.load()))
        if value in ("next", "prev", "down", "up"):  # up/down: rueda del ratón
            return (self.group + (1 if value in ("next", "down") else -1)) % count
        return max(0, min(int(value) - 1, count - 1))

    async def cmd_group(self, value: str = "next") -> str:
        """`wm group N|next|prev`: cambia de grupo de escritorios (N empieza en 1)."""
        group = self._parse_group(value)
        await self.show_group(group)
        return group_names(config.load())[group]

    async def cmd_group_move(self, value: str, follow: str = "") -> str:
        """`wm group-move N|next|prev [follow]`: envía la ventana enfocada al grupo N, al espacio
        que ese grupo muestra en el mismo monitor (con `follow`, también cambia al grupo)."""
        group = self._parse_group(value)
        mons = self.ordered_monitors(await self.wm.monitors())
        for index, m in enumerate(mons):
            m["index"] = index
        mon = next((m for m in mons if m["focused"]), None)
        if mon is None or group == group_of(mon["active_workspace"]):
            return "la ventana ya está en ese grupo"
        target = self._group_target(group, mon)
        await self.wm.move_active_window(target)
        if follow:
            await self.show_group(group, target)
        return f"ventana enviada a {group_names(config.load())[group]}"

    # ---- órdenes -------------------------------------------------------------
    async def cmd_focus(self, workspace_id: str) -> None:
        await self.wm.focus_workspace(int(workspace_id))

    async def cmd_task(self, cls: str) -> None:
        """Clic en una app abierta de la barra inferior: la enfoca; si ya tenía el foco, pasa a
        su siguiente ventana."""
        wins = [c for c in await self.wm.clients() if c["class"] == cls]
        if not wins:
            return
        data = self.hub.get("wm") or {}
        focused = data.get("windows", {}).get(data.get("focused", ""), {}).get("class", "")
        target = wins[1] if len(wins) > 1 and focused == cls else wins[0]
        await self.wm.focus_window(target["address"])

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

    async def cmd_reset(self) -> str:
        """Super+Ctrl+R: deja barras y widgets como recién iniciados."""
        await self.restart_eww()
        return f"interfaz reiniciada: {', '.join(sorted(self.bars))}"

    async def cmd_bars(self) -> str:
        await self.sync_bars()
        return f"barras: {', '.join(sorted(self.bars))}"

    async def cmd_logout(self) -> None:
        await self.wm.logout()

    async def cmd_reload(self) -> None:
        await self.wm.reload()


def _command_key(command: str) -> str:
    """Programa de un comando ('gtk-launch brave-browser' -> 'brave-browser', '/usr/bin/kitty -e x' -> 'kitty')."""
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if not parts:
        return ""
    word = parts[1] if parts[0] == "gtk-launch" and len(parts) > 1 else os.path.basename(parts[0])
    return word.lower().removesuffix(".desktop")


def _same_app(cls: str, key: str) -> bool:
    """¿La clase de ventana corresponde al programa? (org.kde.dolphin ~ dolphin)."""
    cls = cls.lower()
    return bool(key) and key in (cls, cls.rsplit(".", 1)[-1])
