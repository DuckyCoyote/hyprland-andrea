"""Tema `appearance`: estado del selector visual (temas, acentos, fuentes, tamaños).

Los cambios se guardan en ~/.local/state/hyprland-desktop/appearance.json (persisten entre
reinicios), se regeneran los archivos derivados y se recargan Eww, el compositor y kitty.
"""
import asyncio

from .. import config, eww, render
from ..daemon import Source

INT_KEYS = {"font_size": (8, 24), "radius": (0, 24), "spacing": (2, 20), "border_width": (0, 4)}
BOOL_KEYS = {"transparency", "shadows", "animations"}
ACCENTS = ["mauve", "lavender", "blue", "sapphire", "sky", "teal", "green", "yellow", "peach", "maroon", "red", "pink", "flamingo", "rosewater"]


class AppearanceSource(Source):
    topic = "appearance"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.fonts: list[str] = []

    async def start(self) -> None:
        self.fonts = await asyncio.to_thread(render.font_families)
        await self.apply(reload_all=False)

    def _publish(self) -> None:
        ctx = render.context()
        themes = []
        for tid, t in config.themes().items():
            p = t["palette"]
            themes.append({"id": tid, "name": t["name"].replace("Catppuccin ", ""), "variant": t.get("variant", "dark"),
                           "bg": p["base"], "fg": p["text"], "c1": p["red"], "c2": p["mauve"], "c3": p["blue"],
                           "selected": tid == ctx["theme_id"]})
        ap = ctx["ap"]
        self.publish({
            **{k: ap.get(k) for k in ("font_family", "font_size", "radius", "spacing", "border_width", "opacity")},
            **{k: bool(render._bool(ap.get(k))) for k in BOOL_KEYS},
            "theme": ctx["theme_id"], "accent": ctx["accent_name"],
            "themes": themes,
            "accents": [{"name": a, "hex": ctx["pal"][a], "selected": a == ctx["accent_name"]} for a in ACCENTS if a in ctx["pal"]],
            "fonts": self.fonts or [ap.get("font_family", "")],
        })

    async def apply(self, reload_all: bool = True) -> list:
        ctx, changed = await asyncio.to_thread(render.write_all)
        self._publish()
        if not changed:
            return []
        render.log_changes(changed)
        if reload_all:
            if any(p.suffix == ".scss" for p in changed):
                await asyncio.to_thread(eww.reload)
            if any(p.suffix == ".lua" for p in changed):
                await self.hub.sources["wm"].wm.reload()
        await asyncio.to_thread(render.reload_external, ctx, changed)
        return changed

    # ---- órdenes -------------------------------------------------------------
    async def cmd_set(self, key: str, value: str) -> str:
        current = config.load().get("appearance", {})
        if key in INT_KEYS:
            lo, hi = INT_KEYS[key]
            val = max(lo, min(hi, int(round(float(value)))))
        elif key in BOOL_KEYS:
            val = (not render._bool(current.get(key))) if value == "toggle" else render._bool(value)
        elif key == "opacity":
            val = max(0.5, min(1.0, float(value) / 100 if float(value) > 1 else float(value)))
        elif key == "theme":
            if value not in config.themes():
                return f"tema desconocido: {value}"
            val = value
        elif key == "font_family":
            # el combo de Eww emite un valor vacío al crearse: se ignora
            if not value.strip() or (self.fonts and value not in self.fonts):
                return "fuente ignorada"
            val = value
        elif key == "accent":
            if value not in ACCENTS:
                return f"acento desconocido: {value}"
            val = value
        elif key == "icon_theme":
            val = value
        else:
            return f"clave no soportada: {key}"
        if current.get(key) == val:
            return "sin cambios"
        config.set_appearance(key, val)
        await self.apply()
        return f"{key} = {val}"

    async def cmd_reset(self) -> str:
        config.reset_appearance()
        await self.apply()
        return "apariencia restaurada a los valores predeterminados"

    async def cmd_apply(self) -> str:
        changed = await self.apply()
        return f"{len(changed)} archivos regenerados"
