"""Tema `apps`: aplicaciones instaladas para el lanzador.

Lee los .desktop de $XDG_DATA_HOME y $XDG_DATA_DIRS, resuelve iconos con el tema de iconos
del usuario (GTK) y mantiene historial de uso (Recientes / frecuencia) y favoritas.
La búsqueda mientras se escribe se hace en Eww con jq sobre esta lista (sin procesos).
"""
import asyncio
import os
import shlex
import threading
import time
from pathlib import Path

from .. import config, paths
from ..daemon import Source
from ..util import run_sync, spawn_detached, terminal_command

# Categoría del mockup -> categorías freedesktop
CATEGORIES = [
    ("all", "Todas", "󰀻"),
    ("favorites", "Favoritas", "󰋑"),
    ("recent", "Recientes", "󰥔"),
    ("system", "Sistema", "󰒓"),
    ("development", "Desarrollo", "󰅩"),
    ("multimedia", "Multimedia", "󰕧"),
    ("internet", "Internet", "󰖟"),
    ("office", "Oficina", "󰈙"),
    ("games", "Juegos", "󰊴"),
    ("settings", "Configuración", "󰒓"),
]
FDO = {
    "system": {"System", "Monitor", "TerminalEmulator", "FileManager", "Utility", "Accessories"},
    "development": {"Development", "IDE", "TextEditor"},
    "multimedia": {"AudioVideo", "Audio", "Video", "Graphics", "Player"},
    "internet": {"Network", "WebBrowser", "Email", "Chat", "InstantMessaging"},
    "office": {"Office", "Education", "Science"},
    "games": {"Game"},
    "settings": {"Settings", "DesktopSettings", "HardwareSettings", "PackageManager"},
}
FIELD_CODES = ("%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%i", "%c", "%k", "%v", "%m")


def _data_dirs() -> list[Path]:
    home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    dirs = [home] + [Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    return [d / "applications" for d in dirs if (d / "applications").is_dir()]


def _parse_desktop(path: Path, lang: str) -> dict | None:
    entry, section = {}, None
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith("["):
                section = line
                continue
            if section != "[Desktop Entry]" or "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            entry[k.strip()] = v.strip()
    except OSError:
        return None
    if entry.get("Type") != "Application" or entry.get("NoDisplay") == "true" or entry.get("Hidden") == "true":
        return None
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").split(":")
    if entry.get("OnlyShowIn") and not set(entry["OnlyShowIn"].strip(";").split(";")) & set(desktop):
        return None
    if entry.get("NotShowIn") and set(entry["NotShowIn"].strip(";").split(";")) & set(desktop):
        return None
    if "Exec" not in entry:
        return None

    def loc(key):
        for k in (f"{key}[{lang}]", f"{key}[{lang.split('_')[0]}]", key):
            if entry.get(k):
                return entry[k]
        return ""

    return {"name": loc("Name"), "generic": loc("GenericName"), "comment": loc("Comment"),
            "keywords": loc("Keywords"), "icon": entry.get("Icon", ""), "exec": entry["Exec"],
            "terminal": entry.get("Terminal") == "true", "categories": entry.get("Categories", "").strip(";").split(";"),
            "tryexec": entry.get("TryExec", "")}


def window_icon_names() -> dict[str, str]:
    """Clase de ventana (en minúsculas) -> nombre de icono, a partir de los .desktop.

    Usa StartupWMClass, el nombre del archivo (org.kde.dolphin -> también «dolphin») y el
    ejecutable. Incluye entradas NoDisplay: muchas apps se identifican solo por ellas.
    """
    names: dict[str, str] = {}
    for d in reversed(_data_dirs()):  # el usuario tiene prioridad: se escribe al final
        for path in d.glob("*.desktop"):
            fields = {}
            try:
                for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if raw.startswith("[") and raw.strip() != "[Desktop Entry]" and fields:
                        break
                    if "=" in raw and not raw.startswith("#"):
                        k, v = raw.split("=", 1)
                        fields.setdefault(k.strip(), v.strip())
            except OSError:
                continue
            icon = fields.get("Icon", "")
            if not icon:
                continue
            stem = path.stem.lower()
            keys = {stem, stem.rsplit(".", 1)[-1]}
            if fields.get("StartupWMClass"):
                keys.add(fields["StartupWMClass"].lower())
            exe = fields.get("Exec", "").split(" ", 1)[0]
            if exe:
                keys.add(Path(exe).name.lower())
            for k in keys:
                names[k] = icon
    return names


_GTK_LOCK = threading.Lock()  # GtkIconTheme no es seguro entre hilos


class IconResolver:
    def __init__(self) -> None:
        with _GTK_LOCK:
            self._init()

    def _init(self) -> None:
        self.theme = None
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
            self.theme = Gtk.IconTheme.new()
            name = config.load().get("appearance", {}).get("icon_theme") or self._system_theme()
            if name:
                self.theme.set_custom_theme(name)
        except Exception as e:
            from ..util import log
            log(f"iconos: no se pudo cargar el tema de iconos GTK: {e!r}")
            self.theme = None

    @staticmethod
    def _system_theme() -> str:
        code, out = run_sync("gsettings", "get", "org.gnome.desktop.interface", "icon-theme")
        return out.strip().strip("'") if code == 0 else ""

    def lookup(self, icon: str, size: int = 48) -> str:
        if not icon:
            icon = "application-x-executable"
        if icon.startswith("/"):
            return icon if Path(icon).is_file() else ""
        if self.theme:
            with _GTK_LOCK:
                for name in (icon, icon.lower(), "application-x-executable"):
                    info = self.theme.lookup_icon(name, size, 0)
                    if info and info.get_filename():
                        return info.get_filename()
        for ext in ("png", "svg", "xpm"):
            p = Path("/usr/share/pixmaps") / f"{icon}.{ext}"
            if p.is_file():
                return str(p)
        return ""


class AppsSource(Source):
    topic = "apps"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.apps: dict[str, dict] = {}
        self.signature = None

    async def start(self) -> None:
        await self.scan()

    def _signature(self):
        return tuple((str(d), d.stat().st_mtime) for d in _data_dirs())

    async def scan(self, force: bool = False) -> None:
        sig = self._signature()
        if not force and sig == self.signature:
            self._publish()
            return
        self.signature = sig
        self.apps = await asyncio.to_thread(self._scan_sync)
        self._publish()

    def _scan_sync(self) -> dict:
        lang = (os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "en").split(".")[0]
        icons = IconResolver()
        apps = {}
        for directory in reversed(_data_dirs()):  # los directorios del usuario tienen prioridad
            for f in directory.rglob("*.desktop"):
                app_id = str(f.relative_to(directory)).replace("/", "-")
                info = _parse_desktop(f, lang)
                if not info:
                    apps.pop(app_id, None)
                    continue
                if info["tryexec"] and not (Path(info["tryexec"]).is_file() or run_sync("sh", "-c", f"command -v {shlex.quote(info['tryexec'])}")[0] == 0):
                    continue
                cats = {key for key, fdo in FDO.items() if fdo & set(info["categories"])}
                apps[app_id] = {
                    "id": app_id, "name": info["name"], "exec": info["exec"], "terminal": info["terminal"],
                    "icon": icons.lookup(info["icon"]), "cats": sorted(cats),
                    "search": " ".join([info["name"], info["generic"], info["keywords"], info["comment"], app_id]).lower(),
                }
        return apps

    def _publish(self) -> None:
        history = config.read_state(paths.LAUNCH_HISTORY, {})
        favorites = set(config.read_state(paths.UI_STATE, {}).get("favorites", []))
        items = []
        for a in self.apps.values():
            h = history.get(a["id"], {})
            cats = list(a["cats"]) + ["all"] + (["favorites"] if a["id"] in favorites else []) + (["recent"] if h else [])
            items.append({"id": a["id"], "name": a["name"], "icon": a["icon"], "search": a["search"],
                          "cats": "," + ",".join(cats) + ",", "fav": a["id"] in favorites,
                          "count": h.get("count", 0), "last": h.get("last", 0)})
        items.sort(key=lambda a: (-a["count"], a["name"].lower()))
        recent = sorted((a for a in items if a["last"]), key=lambda a: -a["last"])[:12]
        self.publish({"apps": items, "recent": [a["id"] for a in recent],
                      "categories": [{"id": c, "label": l, "glyph": g} for c, l, g in CATEGORIES]})

    # ---- órdenes -------------------------------------------------------------
    async def cmd_rescan(self) -> None:
        await self.scan(force=True)

    async def cmd_refresh(self) -> None:
        await self.scan()

    async def cmd_launch(self, app_id: str = "") -> str:
        app = self.apps.get(app_id)
        if not app:
            return f"aplicación desconocida: {app_id}"
        cmd = shlex.join(t.replace("%%", "%") for t in shlex.split(app["exec"]) if t not in FIELD_CODES)
        if app["terminal"]:
            cmd = terminal_command(config.load()["apps"]["terminal"], cmd)
        spawn_detached(cmd)
        history = config.read_state(paths.LAUNCH_HISTORY, {})
        h = history.get(app_id, {"count": 0})
        history[app_id] = {"count": h["count"] + 1, "last": time.time()}
        config.write_json(paths.LAUNCH_HISTORY, history)
        await self.hub.execute(["popup", "close"])
        self._publish()
        return app["name"]

    async def cmd_favorite(self, app_id: str) -> None:
        state = config.read_state(paths.UI_STATE, {})
        favs = set(state.get("favorites", []))
        favs ^= {app_id}
        state["favorites"] = sorted(favs)
        config.write_json(paths.UI_STATE, state)
        self._publish()
