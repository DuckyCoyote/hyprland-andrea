"""Tema `appearance`: estado del selector visual (temas, acentos, fuentes, tamaños).

Los cambios se guardan en ~/.local/state/hyprland-desktop/appearance.json (persisten entre
reinicios), se regeneran los archivos derivados y se recargan Eww, el compositor y kitty.
"""
import asyncio
from pathlib import Path

from .. import config, eww, paths, previews, render
from ..daemon import Source
from ..util import Debouncer, have, run

INT_KEYS = {"font_size": (8, 24), "font_weight": (100, 900), "radius": (0, 24), "spacing": (2, 20), "border_width": (0, 4)}
BOOL_KEYS = {"transparency", "shadows", "animations"}
BAR_STYLES = {"capsules": "Cápsulas", "rectangle": "Rectángulo", "arcade": "Arcade"}
ACCENTS = ["mauve", "lavender", "blue", "sapphire", "sky", "teal", "green", "yellow", "peach", "maroon", "red", "pink", "flamingo", "rosewater"]


class AppearanceSource(Source):
    topic = "appearance"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.fonts: list[str] = []
        self.walls: list[dict] = []
        self.wall_dir = ""
        self.cursors: list[dict] = []
        self._apply_soon = Debouncer(0.5, self.apply)

    async def start(self) -> None:
        await self._scan()
        await self.apply(reload_all=False)

    async def _scan(self) -> None:
        """Relee las fuentes, la carpeta de fondos y los temas de cursor (genera miniaturas nuevas)."""
        self.fonts = await asyncio.to_thread(render.font_families)
        folder = await asyncio.to_thread(previews.wallpaper_dir, config.load())
        self.wall_dir = str(folder)
        self.walls = await asyncio.to_thread(previews.wallpapers, folder)
        self.cursors = await asyncio.to_thread(previews.cursor_themes)

    def _publish(self) -> None:
        ctx = render.context()
        themes = []
        for tid, t in config.themes().items():
            p = t["palette"]
            themes.append({"id": tid, "name": t["name"].replace("Catppuccin ", ""), "title": t["name"],
                           "variant": t.get("variant", "dark"),
                           "bg": p["base"], "fg": p["text"], "c1": p["red"], "c2": p["mauve"], "c3": p["blue"],
                           "selected": tid == ctx["theme_id"]})
        ap = ctx["ap"]
        self.publish({
            **{k: ap.get(k) for k in ("font_family", "font_size", "radius", "spacing", "border_width", "opacity")},
            "font_weight": int(ap.get("font_weight", 400)),
            **{k: bool(render._bool(ap.get(k))) for k in BOOL_KEYS},
            "theme": ctx["theme_id"], "accent": ctx["accent_name"],
            "themes": themes,
            "theme_rows": _rows(themes, 4),
            "accents": [{"name": a, "hex": ctx["pal"][a], "selected": a == ctx["accent_name"]} for a in ACCENTS if a in ctx["pal"]],
            "fonts": self.fonts or [ap.get("font_family", "")],
            "wallpaper": render.wallpaper_path(ctx),
            "wallpaper_dir": self.wall_dir,
            "wallpaper_rows": _rows([{**w, "selected": w["path"] == render.wallpaper_path(ctx)} for w in self.walls], 3),
            "bar_style": _bar_style(ap),
            "bar_styles": [{"id": k, "name": v, "selected": k == _bar_style(ap)} for k, v in BAR_STYLES.items()],
            "cursor_theme": ap.get("cursor_theme", ""),
            "cursor_size": int(ap.get("cursor_size", 24)),
            "cursor_rows": _rows([{**c, "selected": c["name"] == ap.get("cursor_theme", "")} for c in self.cursors], 3),
        })

    async def apply(self, reload_all: bool = True) -> list:
        ctx, changed = await asyncio.to_thread(render.write_all)
        self._publish()
        if not changed:
            return []
        render.log_changes(changed)
        if reload_all:
            wm = self.hub.sources["wm"]
            if any(p.name in ("theme.lua", "settings.lua") for p in changed):
                await wm.wm.reload()
            if any(p.suffix == ".scss" for p in changed):
                await wm.reload_eww()
        await asyncio.to_thread(render.reload_external, ctx, changed)
        return changed

    # ---- órdenes -------------------------------------------------------------
    async def cmd_set(self, key: str, value: str) -> str:
        current = config.load().get("appearance", {})
        if key in INT_KEYS:
            lo, hi = INT_KEYS[key]
            val = max(lo, min(hi, int(round(float(value)))))
            if key == "font_weight":  # los pesos de fuente van de 100 en 100
                val = int(round(val / 100.0)) * 100
        elif key in BOOL_KEYS:
            val = (not render._bool(current.get(key))) if value == "toggle" else render._bool(value)
        elif key == "opacity":
            val = max(0.5, min(1.0, float(value) / 100 if float(value) > 1 else float(value)))
        elif key == "theme":
            themes = config.themes()
            if value not in themes:
                return f"tema desconocido: {value}"
            val = value
            # Un tema puede traer su acento ("accent": "red" en Gruvbox); al salir de él se vuelve
            # al acento de settings.json si no se cambió entretanto.
            old_default = themes.get(current.get("theme", ""), {}).get("accent")
            if themes[value].get("accent"):
                config.set_appearance("accent", themes[value]["accent"])
            elif old_default and current.get("accent") == old_default:
                config.set_appearance("accent", config.default_appearance().get("accent", "mauve"))
        elif key == "font_family":
            # el combo de Eww emite un valor vacío al crearse: se ignora
            if not value.strip() or (self.fonts and value not in self.fonts):
                return "fuente ignorada"
            val = value
        elif key == "accent":
            if value not in ACCENTS:
                return f"acento desconocido: {value}"
            val = value
        elif key == "bar_style":
            # la barra elige su diseño en yuck según appearance.bar_style: basta con publicarlo
            if value not in BAR_STYLES:
                return f"estilo de barra desconocido: {value}"
            if _bar_style(current) == value:
                return "sin cambios"
            config.set_appearance(key, value)
            self._publish()
            return f"bar_style = {value}"
        elif key == "icon_theme":
            val = value
        elif key == "wallpaper":
            path = Path(value).expanduser()
            if not path.is_file():
                return f"no existe: {value}"
            config.set_appearance("wallpaper", str(path))
            self._publish()
            await asyncio.to_thread(render.set_wallpaper)
            return f"fondo = {path.name}"
        elif key in ("cursor_theme", "cursor_size"):
            if key == "cursor_theme" and value not in {c["name"] for c in self.cursors}:
                return f"tema de cursor desconocido: {value}"
            val = value if key == "cursor_theme" else max(16, min(64, int(float(value))))
            if current.get(key) == val:
                return "sin cambios"
            config.set_appearance(key, val)
            await self.apply()
            await self._apply_cursor()
            return f"{key} = {val}"
        else:
            return f"clave no soportada: {key}"
        if current.get(key) == val:
            return "sin cambios"
        config.set_appearance(key, val)
        # Se guarda al momento, pero se aplica una sola vez medio segundo después del último cambio:
        # arrastrar un deslizador encadenaba recargas de Eww y acababa bloqueándolo.
        self._publish()
        self._apply_soon()
        return f"{key} = {val}"

    async def _apply_cursor(self) -> None:
        ap = config.load().get("appearance", {})
        theme, size = ap.get("cursor_theme", ""), int(ap.get("cursor_size", 24))
        if not theme:
            return
        await self.hub.sources["wm"].wm.set_cursor(theme, size)
        if have("gsettings"):  # aplicaciones GTK y XWayland
            await run("gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", theme)
            await run("gsettings", "set", "org.gnome.desktop.interface", "cursor-size", str(size))

    async def cmd_rescan(self) -> str:
        await self._scan()
        self._publish()
        return f"{len(self.fonts)} fuentes, {len(self.walls)} fondos en {self.wall_dir}, {len(self.cursors)} temas de cursor"

    async def cmd_open_wallpaper_dir(self) -> None:
        from ..util import spawn_detached
        settings = config.load()
        spawn_detached(f"{config.resolve_app(settings, '@file_manager')} '{self.wall_dir}'")

    async def cmd_reset(self) -> str:
        config.reset_appearance()
        await self.apply()
        await asyncio.to_thread(render.set_wallpaper)
        return "apariencia restaurada a los valores predeterminados"

    async def cmd_apply(self) -> str:
        changed = await self.apply()
        return f"{len(changed)} archivos regenerados"


def _rows(items: list, size: int) -> list:
    """Parte una lista en filas (Eww no tiene rejilla)."""
    rows = [items[i:i + size] for i in range(0, len(items), size)]
    if rows:  # huecos invisibles para que la última fila no se estire (con todos los campos:
        # Eww evalúa las expresiones aunque el widget esté oculto y un null rompe el render)
        blank = str(paths.ASSETS_DIR / "icons" / "blank.png")
        hole = {"placeholder": True, "selected": False, "name": "", "label": "", "path": "",
                "thumb": blank, "preview": blank, "id": "", "title": "", "bg": "#000000", "c1": "#000000",
                "c2": "#000000", "c3": "#000000"}
        rows[-1] += [dict(hole) for _ in range(size - len(rows[-1]))]
    return rows


def _bar_style(ap: dict) -> str:
    style = ap.get("bar_style", "capsules")
    return style if style in BAR_STYLES else "capsules"
