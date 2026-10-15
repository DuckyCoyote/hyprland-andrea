"""Generador de configuración: settings.json + tema -> archivos de cada programa.

Es el ÚNICO lugar donde los tokens de diseño se traducen a la sintaxis de cada programa.
Ningún archivo escrito a mano contiene colores, fuentes ni tamaños.

  config/eww/styles/tokens/_generated.scss   tokens crudos para Eww
  config/hypr/generated/theme.lua            colores/bordes/sombras para Hyprland
  config/hypr/generated/settings.lua         monitores, apps, teclado... para Hyprland
  config/hypr/hyprlock.conf, hypridle.conf   (formato hyprlang)
  config/kitty/theme.conf                    terminal (incluido desde kitty.conf)
"""
import json
import subprocess
from pathlib import Path

from . import config, paths
from .util import have, log

HEADER = "GENERADO por `desktopctl apply` a partir de settings.json y themes/. No editar a mano."


def _bool(v) -> bool:
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on", "sí", "si")


def context() -> dict:
    settings = config.load()
    themes = config.themes()
    ap = settings.get("appearance", {})
    theme_id = ap.get("theme", "mocha") if ap.get("theme") in themes else "mocha"
    theme = themes.get(theme_id) or next(iter(themes.values()))
    pal = theme["palette"]
    accent_name = ap.get("accent", "mauve") if ap.get("accent") in pal else "mauve"
    return {"settings": settings, "ap": ap, "theme_id": theme_id, "theme": theme, "pal": pal,
            "accent": pal[accent_name], "accent_name": accent_name, "dark": theme.get("variant", "dark") != "light"}


def _hex(c: str) -> str:
    return c.lstrip("#")


# --------------------------------------------------------------------------- Eww
def eww_scss(ctx: dict) -> str:
    ap, pal = ctx["ap"], ctx["pal"]
    font = ap.get("font_family", "JetBrainsMono Nerd Font")
    opacity = float(ap.get("opacity", 0.92)) if _bool(ap.get("transparency", False)) else 1.0
    lines = [f"// {HEADER}", f"// Tema: {ctx['theme']['name']}", ""]
    lines += [f"${k}: {v};" for k, v in pal.items()]
    lines += [
        "",
        f"$accent: {ctx['accent']};",
        f"$is-dark: {'true' if ctx['dark'] else 'false'};",
        f'$font-family: "{font}", "JetBrainsMono Nerd Font", "Symbols Nerd Font", monospace;',
        f"$font-size: {int(ap.get('font_size', 13))}px;",
        f"$radius: {int(ap.get('radius', 10))}px;",
        f"$spacing: {int(ap.get('spacing', 8))}px;",
        f"$border-width: {int(ap.get('border_width', 1))}px;",
        f"$surface-opacity: {opacity:.2f};",
        f"$shadows: {'true' if _bool(ap.get('shadows', True)) else 'false'};",
        f"$anim-duration: {'150ms' if _bool(ap.get('animations', True)) else '0ms'};",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- Hyprland
def _lua(value, indent: int = 0) -> str:
    pad = "    " * (indent + 1)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "{}"
        return "{\n" + "".join(f"{pad}{_lua(v, indent + 1)},\n" for v in value) + "    " * indent + "}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        body = ""
        for k, v in value.items():
            key = k if k.isidentifier() else f"[{json.dumps(k)}]"
            body += f"{pad}{key} = {_lua(v, indent + 1)},\n"
        return "{\n" + body + "    " * indent + "}"
    return "nil"


def hypr_theme(ctx: dict) -> str:
    ap, pal = ctx["ap"], ctx["pal"]
    spacing = int(ap.get("spacing", 8))
    opacity = float(ap.get("opacity", 0.92)) if _bool(ap.get("transparency", False)) else 1.0
    data = {
        "name": ctx["theme_id"],
        "dark": ctx["dark"],
        "active_border": f"rgb({_hex(ctx['accent'])})",
        "inactive_border": f"rgb({_hex(pal['surface0'])})",
        "urgent_border": f"rgb({_hex(pal['red'])})",
        "shadow": f"rgba({_hex(pal['crust'])}aa)",
        "background": f"rgb({_hex(pal['base'])})",
        "rounding": int(ap.get("radius", 10)),
        "border_size": 2,
        "gaps_in": max(2, spacing // 2),
        "gaps_out": spacing + 2,
        "shadows": _bool(ap.get("shadows", True)),
        "animations": _bool(ap.get("animations", True)),
        "inactive_opacity": round(min(1.0, opacity + 0.03), 2),
        "active_opacity": 1.0,
        "font": ap.get("font_family", "JetBrainsMono Nerd Font"),
    }
    return f"-- {HEADER}\nreturn {_lua(data)}\n"


def hypr_settings(ctx: dict) -> str:
    s = ctx["settings"]
    data = {
        "ctl": str(paths.CTL),
        "apps": s.get("apps", {}),
        "monitors": s.get("monitors", []),
        "workspaces_per_monitor": int(s.get("workspaces", {}).get("per_monitor", 6)),
        "keyboard": s.get("keyboard", {}),
        "input": s.get("input", {}),
    }
    return f"-- {HEADER}\nreturn {_lua(data)}\n"


def hyprlock(ctx: dict) -> str:
    pal, ap = ctx["pal"], ctx["ap"]
    font = ap.get("font_family", "JetBrainsMono Nerd Font")
    rgb = lambda c: f"rgb({_hex(c)})"
    return f"""# {HEADER}
general {{
    hide_cursor = true
}}

background {{
    monitor =
    path = screenshot
    blur_passes = 3
    blur_size = 6
    color = {rgb(pal['base'])}
}}

label {{
    monitor =
    text = $TIME
    color = {rgb(pal['text'])}
    font_size = 88
    font_family = {font}
    position = 0, 160
    halign = center
    valign = center
}}

label {{
    monitor =
    text = cmd[update:60000] LC_TIME=$LANG date +"%A, %d de %B"
    color = {rgb(pal['subtext0'])}
    font_size = 20
    font_family = {font}
    position = 0, 70
    halign = center
    valign = center
}}

input-field {{
    monitor =
    size = 320, 56
    outline_thickness = 2
    rounding = {int(ap.get('radius', 10)) * 2}
    outer_color = {rgb(ctx['accent'])}
    inner_color = {rgb(pal['surface0'])}
    font_color = {rgb(pal['text'])}
    check_color = {rgb(pal['yellow'])}
    fail_color = {rgb(pal['red'])}
    capslock_color = {rgb(pal['peach'])}
    font_family = {font}
    placeholder_text = <i>Contraseña…</i>
    fail_text = <b>$FAIL</b> ($ATTEMPTS)
    fade_on_empty = false
    dots_center = true
    position = 0, -40
    halign = center
    valign = center
}}
"""


def hypridle(ctx: dict) -> str:
    idle = ctx["settings"].get("idle", {})
    lock, off, sleep = (int(idle.get(k, 0)) for k in ("lock_minutes", "screen_off_minutes", "suspend_minutes"))
    out = f"""# {HEADER}
general {{
    lock_cmd = pidof hyprlock || hyprlock
    before_sleep_cmd = loginctl lock-session
    after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms({{ action = "on" }})'
}}
"""
    if lock > 0:
        out += f"\nlistener {{\n    timeout = {lock * 60}\n    on-timeout = loginctl lock-session\n}}\n"
    if off > 0:
        out += (f"\nlistener {{\n    timeout = {off * 60}\n"
                f"    on-timeout = hyprctl dispatch 'hl.dsp.dpms({{ action = \"off\" }})'\n"
                f"    on-resume = hyprctl dispatch 'hl.dsp.dpms({{ action = \"on\" }})'\n}}\n")
    if sleep > 0:
        out += f"\nlistener {{\n    timeout = {sleep * 60}\n    on-timeout = systemctl suspend\n}}\n"
    return out


# --------------------------------------------------------------------------- kitty

def kitty(ctx: dict) -> str:
    p, dark = ctx["pal"], ctx["dark"]
    c = [p["surface1"] if dark else p["subtext1"], p["red"], p["green"], p["yellow"], p["blue"], p["pink"], p["teal"],
         p["subtext1"] if dark else p["surface2"],
         p["surface2"] if dark else p["subtext0"], p["red"], p["green"], p["yellow"], p["blue"], p["pink"], p["teal"],
         p["subtext0"] if dark else p["surface1"]]
    lines = [f"# {HEADER}",
             f"font_family {ctx['ap'].get('font_family', 'JetBrainsMono Nerd Font')}",
             f"foreground {p['text']}", f"background {p['base']}",
             f"selection_foreground {p['base']}", f"selection_background {p['rosewater']}",
             f"cursor {p['rosewater']}", f"cursor_text_color {p['base']}",
             f"url_color {p['rosewater']}", f"active_border_color {ctx['accent']}", f"inactive_border_color {p['overlay0']}",
             f"active_tab_foreground {p['crust']}", f"active_tab_background {ctx['accent']}",
             f"inactive_tab_foreground {p['text']}", f"inactive_tab_background {p['mantle']}",
             f"tab_bar_background {p['crust']}"]
    lines += [f"color{i} {v}" for i, v in enumerate(c)]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- aplicar
def targets(ctx: dict) -> dict[Path, str]:
    return {
        paths.EWW_DIR / "styles/tokens/_generated.scss": eww_scss(ctx),
        paths.HYPR_DIR / "generated/theme.lua": hypr_theme(ctx),
        paths.HYPR_DIR / "generated/settings.lua": hypr_settings(ctx),
        paths.HYPR_DIR / "hyprlock.conf": hyprlock(ctx),
        paths.HYPR_DIR / "hypridle.conf": hypridle(ctx),
        paths.KITTY_DIR / "theme.conf": kitty(ctx),
    }


def write_all() -> tuple[dict, list[Path]]:
    """Escribe solo los archivos cuyo contenido cambió. Devuelve (contexto, cambiados)."""
    ctx = context()
    changed = []
    for path, content in targets(ctx).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path.read_text(encoding="utf-8") == content:
                continue
        except FileNotFoundError:
            pass
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        changed.append(path)
    return ctx, changed


def _quiet(*cmd: str) -> None:
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def reload_external(ctx: dict, changed: list[Path]) -> None:
    """Recarga los programas que no dependen del compositor (Eww y el WM los recarga el daemon)."""
    names = {p.name for p in changed}
    if "theme.conf" in names:
        _quiet("pkill", "-USR1", "-x", "kitty")  # kitty recarga su configuración con SIGUSR1
    if have("gsettings"):
        _quiet("gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
               "prefer-dark" if ctx["dark"] else "prefer-light")
    set_wallpaper(ctx)


def set_wallpaper(ctx: dict | None = None) -> None:
    ctx = ctx or context()
    if not have("awww"):
        return
    wall = ctx["settings"].get("wallpaper", "")
    if wall and Path(wall).expanduser().is_file():
        _quiet("awww", "img", str(Path(wall).expanduser()), "--transition-type", "fade", "--transition-duration", "0.6")
    else:
        _quiet("awww", "clear", _hex(ctx["pal"]["crust"]))


def font_families() -> list[str]:
    """Fuentes monoespaciadas instaladas (las Nerd Font primero)."""
    try:
        out = subprocess.run(["fc-list", ":spacing=mono", "family"], capture_output=True, text=True, timeout=10).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    fams = set()
    for line in out.splitlines():
        name = line.split(",")[0].strip()
        if name and not any(x in name for x in (" Propo", " NFP", " NFM", " Mono NF", "Symbols")):
            fams.add(name)
    return sorted(fams, key=lambda f: ("Nerd Font" not in f, f.lower()))[:40]


def log_changes(changed: list[Path]) -> None:
    for p in changed:
        log(f"actualizado: {p.relative_to(paths.ROOT)}")
