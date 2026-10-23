"""Generador de configuración: settings.json + tema -> archivos de cada programa.

Es el ÚNICO lugar donde los tokens de diseño se traducen a la sintaxis de cada programa.
Ningún archivo escrito a mano contiene colores, fuentes ni tamaños.

  ~/.cache/hyprland-desktop/eww/_generated.scss  tokens crudos para Eww (enlazado en config/eww/styles/tokens/)
  config/hypr/generated/theme.lua            colores/bordes/sombras para Hyprland
  config/hypr/generated/settings.lua         monitores, apps, teclado... para Hyprland
  config/hypr/hyprlock.conf, hypridle.conf   (formato hyprlang)
  config/kitty/theme.conf                    terminal (incluido desde kitty.conf)
"""
import json
import re
import shutil
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
    # Un tema puede tomar los colores de los iconos de otro (el monocromo conserva los de Mocha)
    icon_pal = themes.get(theme.get("icon_palette", ""), {}).get("palette", pal)
    # La barra y los widgets usan el tema elegido; el resto del sistema (bordes de Hyprland, kitty,
    # Neovim, GTK) puede usar otro con "system": "<tema>" (p. ej. barra clara y sistema oscuro).
    sys_id = theme.get("system") if theme.get("system") in themes else theme_id
    sys_theme = themes[sys_id]
    sys_pal = sys_theme["palette"]
    system = {"theme_id": sys_id, "theme": sys_theme, "pal": sys_pal,
              "accent": sys_pal.get(accent_name, sys_pal["mauve"]), "dark": sys_theme.get("variant", "dark") != "light"}
    return {"settings": settings, "ap": ap, "theme_id": theme_id, "theme": theme, "pal": pal, "icon_pal": icon_pal,
            "accent": pal[accent_name], "accent_name": accent_name, "dark": theme.get("variant", "dark") != "light",
            "system": system}


def system_ctx(ctx: dict) -> dict:
    """Contexto con la paleta del sistema en lugar de la de la barra."""
    return {**ctx, **ctx["system"]}


def _hex(c: str) -> str:
    return c.lstrip("#")


def window_gaps(ap: dict) -> tuple[int, int]:
    """(gaps_in, hueco) del compositor. Entre dos ventanas quedan 2 × gaps_in: ese mismo hueco se
    usa hacia los bordes de la pantalla (gaps_out) y alrededor de la barra ($window-gap)."""
    gaps_in = max(2, int(ap.get("spacing", 8)) // 2)
    return gaps_in, gaps_in * 2


# --------------------------------------------------------------------------- Eww
def eww_scss(ctx: dict) -> str:
    ap, pal = ctx["ap"], ctx["pal"]
    font = ap.get("font_family", "JetBrainsMono Nerd Font")
    opacity = float(ap.get("opacity", 0.92)) if _bool(ap.get("transparency", False)) else 1.0
    lines = [f"// {HEADER}", f"// Tema: {ctx['theme']['name']}", ""]
    lines += [f"${k}: {v};" for k, v in pal.items()]
    lines += [""] + [f"$icon-{k}: {v};" for k, v in ctx["icon_pal"].items()]
    lines += [
        "",
        f"$accent: {ctx['accent']};",
        f"$is-dark: {'true' if ctx['dark'] else 'false'};",
        f'$font-family: "{font}", "JetBrainsMono Nerd Font", "Symbols Nerd Font", monospace;',
        f"$font-size: {int(ap.get('font_size', 13))}px;",
        f"$font-weight: {int(ap.get('font_weight', 400))};",
        f"$radius: {int(ap.get('radius', 10))}px;",
        f"$spacing: {int(ap.get('spacing', 8))}px;",
        f"$window-gap: {window_gaps(ap)[1]}px;",
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
    ctx = system_ctx(ctx)
    ap, pal = ctx["ap"], ctx["pal"]
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
        "gaps_in": window_gaps(ap)[0],
        "gaps_out": window_gaps(ap)[1],
        "shadows": _bool(ap.get("shadows", True)),
        "animations": _bool(ap.get("animations", True)),
        "inactive_opacity": round(min(1.0, opacity + 0.03), 2),
        "active_opacity": 1.0,
        "font": ap.get("font_family", "JetBrainsMono Nerd Font"),
        "cursor_theme": ap.get("cursor_theme", ""),
        "cursor_size": int(ap.get("cursor_size", 24)),
    }
    return f"-- {HEADER}\nreturn {_lua(data)}\n"


def hypr_settings(ctx: dict) -> str:
    s = ctx["settings"]
    data = {
        "ctl": str(paths.CTL),
        "apps": {k: config.app_command(s, k) for k in s.get("apps", {})},
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
    ctx = system_ctx(ctx)
    p, dark = ctx["pal"], ctx["dark"]
    # Colores del texto (primer plano y paleta ANSI): un tema puede tomarlos de otro con
    # "kitty": {"text_palette": "<tema>"}; los fondos siguen siendo los del tema propio.
    tp = config.themes().get(ctx["theme"].get("kitty", {}).get("text_palette", ""), {}).get("palette", p)
    c = [tp["surface1"] if dark else tp["subtext1"], tp["red"], tp["green"], tp["yellow"], tp["blue"], tp["pink"], tp["teal"],
         tp["subtext1"] if dark else tp["surface2"],
         tp["surface2"] if dark else tp["subtext0"], tp["red"], tp["green"], tp["yellow"], tp["blue"], tp["pink"], tp["teal"],
         tp["subtext0"] if dark else tp["surface1"]]
    lines = [f"# {HEADER}",
             *_kitty_font(ctx),
             f"foreground {tp['text']}", f"background {p['base']}",
             f"selection_foreground {p['base']}", f"selection_background {p['rosewater']}",
             f"cursor {tp['rosewater']}", f"cursor_text_color {p['base']}",
             f"url_color {tp['rosewater']}", f"active_border_color {ctx['accent']}", f"inactive_border_color {p['overlay0']}",
             # Pestañas: arriba y minimalistas, cada una es una píldora redondeada con número y
             # nombre, con los colores del tema global (activa = acento, inactivas = superficie).
             "tab_bar_edge top", "tab_bar_style separator", 'tab_separator " "',
             "tab_bar_margin_width 6", "tab_bar_margin_height 4 2",
             f"tab_bar_background {p['base']}", f"tab_bar_margin_color {p['base']}",
             f"active_tab_background {p['base']}", f"inactive_tab_background {p['base']}",
             "active_tab_font_style bold", "inactive_tab_font_style normal",
             "tab_title_template " + _pill(p["surface0"], p["subtext1"], p["surface2"], p["text"]),
             # círculo del número activo: el acento aclarado (u oscurecido en temas claros)
             "active_tab_title_template " + _pill(ctx["accent"], p["crust"],
                                                  _mix(ctx["accent"], "#ffffff" if dark else "#000000", 0.45),
                                                  p["crust"]),
             "include keys.conf"]  # atajos de awesome-minimal (archivo fijo, no depende del tema)
    lines += [f"color{i} {v}" for i, v in enumerate(c)]
    shell = ctx["settings"].get("apps", {}).get("shell", "")
    if shell:
        lines.append(f"shell {shutil.which(shell) or shell}")
    return "\n".join(lines) + "\n"


TAB_TITLE_MAX = 22


def _mix(c1: str, c2: str, weight: float) -> str:
    """Mezcla dos colores #rrggbb; `weight` es la proporción del segundo."""
    a, b = (tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for c in (c1, c2))
    return "#" + "".join(f"{round(x + (y - x) * weight):02x}" for x, y in zip(a, b))


def _kitty_font(ctx: dict) -> list[str]:
    """Fuente de kitty: settings.kitty (propia, como la de Konsole) o, si no hay, la de la interfaz."""
    k = ctx["settings"].get("kitty", {})
    family = k.get("font_family") or ctx["ap"].get("font_family", "JetBrainsMono Nerd Font")
    style = k.get("font_style", "")
    lines = [f'font_family family="{family}"' + (f" style={style}" if style else "")]
    if k.get("font_size"):
        lines.append(f"font_size {k['font_size']}")
    return lines


def _pill(bg: str, fg: str, num_bg: str, num_fg: str) -> str:
    """Plantilla de título de kitty: píldora redondeada con el número dentro de un círculo de
    color contrastado y después el nombre:  (N) nombre  (extremos con glifos Nerd Font).

    El título se recorta dentro de la píldora (kitty evalúa la plantilla como una f-string de
    Python); tab_title_max_length pondría el «…» fuera, después del cierre redondeado."""
    def c(color: str) -> str:
        return "_" + color.lstrip("#")
    left, right = "\ue0b6", "\ue0b4"
    n = TAB_TITLE_MAX
    title = "{title if len(title) <= %d else title[:%d] + '…'}" % (n, n - 1)
    number = ("{fmt.fg.%s}{fmt.bg.tab}%s{fmt.fg.%s}{fmt.bg.%s}{index}{fmt.fg.%s}{fmt.bg.%s}%s"
              % (c(num_bg), left, c(num_fg), c(num_bg), c(num_bg), c(bg), right))
    return ('"%s{fmt.fg.%s}{fmt.bg.%s} %s {fmt.fg.%s}{fmt.bg.tab}%s"'
            % (number, c(fg), c(bg), title, c(bg), right))


# --------------------------------------------------------------------------- Neovim
def nvim_palette(ctx: dict) -> str:
    """Paleta para monokai-pro (override_palette) con el mismo reparto de colores que la
    configuración de Neovim del usuario y el fondo idéntico al de kitty."""
    ctx = system_ctx(ctx)
    p = ctx["pal"]
    sync = ctx["settings"].get("nvim", {}).get("sync_theme", True)
    palette = {
        "dark2": p["crust"], "dark1": p["mantle"], "background": p["base"], "text": p["text"],
        "accent1": p["red"], "accent2": p["blue"], "accent3": p["yellow"], "accent4": p["green"],
        "accent5": p["sky"], "accent6": p["mauve"],
        "dimmed1": p["overlay1"], "dimmed2": p["overlay2"], "dimmed3": p["surface1"],
        "dimmed4": p["surface1"], "dimmed5": p["mantle"],
    }
    # Un tema con "nvim": {"backgrounds_only": true} (el monocromo) solo cambia los fondos del
    # editor y del explorador; el resto de colores son los de la configuración original de Neovim.
    if ctx["theme"].get("nvim", {}).get("backgrounds_only"):
        palette = {k: palette[k] for k in ("dark2", "dark1", "background", "dimmed5")}
    data = {'enabled': bool(sync), 'theme': ctx['theme_id'], 'dark': ctx['dark'], 'palette': palette}
    # "nvim": {"colorscheme": "nordic"}: Neovim usa ese colorscheme original en vez de monokai-pro
    if ctx["theme"].get("nvim", {}).get("colorscheme"):
        data["colorscheme"] = ctx["theme"]["nvim"]["colorscheme"]
    return f"-- {HEADER}\nreturn {_lua(data)}\n"


# --------------------------------------------------------------------------- aplicar
def targets(ctx: dict) -> dict[Path, str]:
    return {
        # Fuera de la carpeta de Eww (enlazado desde styles/tokens/_generated.scss): Eww recarga
        # solo al detectar cambios en su carpeta, y esa recarga se solapaba con la del daemon.
        paths.CACHE_DIR / "eww/_generated.scss": eww_scss(ctx),
        paths.HYPR_DIR / "generated/theme.lua": hypr_theme(ctx),
        paths.HYPR_DIR / "generated/settings.lua": hypr_settings(ctx),
        paths.HYPR_DIR / "hyprlock.conf": hyprlock(ctx),
        paths.HYPR_DIR / "hypridle.conf": hypridle(ctx),
        paths.KITTY_DIR / "theme.conf": kitty(ctx),
        paths.ROOT / "config/nvim/lua/hyprland_desktop/palette.lua": nvim_palette(ctx),
    }


def _link_eww_tokens() -> None:
    link = paths.EWW_DIR / "styles/tokens/_generated.scss"
    target = paths.CACHE_DIR / "eww/_generated.scss"
    if link.is_symlink() and link.resolve() == target:
        return
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def write_all() -> tuple[dict, list[Path]]:
    """Escribe solo los archivos cuyo contenido cambió. Devuelve (contexto, cambiados)."""
    _link_eww_tokens()
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
               "prefer-dark" if ctx["system"]["dark"] else "prefer-light")
    set_wallpaper(ctx)


def wallpaper_path(ctx: dict) -> str:
    """Fondo elegido en el selector (appearance.json) o, si no, el de settings.json."""
    return ctx["ap"].get("wallpaper") or ctx["settings"].get("wallpaper", "")


def set_wallpaper(ctx: dict | None = None) -> None:
    ctx = ctx or context()
    if not have("awww"):
        return
    wall = wallpaper_path(ctx)
    if wall and Path(wall).expanduser().is_file():
        _quiet("awww", "img", str(Path(wall).expanduser()), "--transition-type", "fade", "--transition-duration", "0.6")
    else:
        _quiet("awww", "clear", _hex(ctx["system"]["pal"]["crust"]))


def font_families() -> list[str]:
    """Fuentes instaladas para la interfaz: Nerd Font primero, luego monoespaciadas y el resto.
    Se omiten las variantes de Noto por escritura, emojis y símbolos, que solo sirven de respaldo."""
    try:
        out = subprocess.run(["fc-list", ":", "family", "spacing"], capture_output=True, text=True, timeout=10).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    fams: dict[str, bool] = {}  # familia → monoespaciada
    for line in out.splitlines():
        name, _, attrs = line.partition(":")
        name = name.split(",")[0].strip()
        if not name or any(x in name for x in (" Propo", " NFP", " NFM", " Mono NF", "Symbols", "Emoji")):
            continue
        if re.match(r"Noto (Sans |Serif )?(?!Mono$)\S", name) and name not in ("Noto Sans", "Noto Serif", "Noto Sans Mono"):
            continue
        fams[name] = fams.get(name, False) or "spacing=100" in attrs
    return sorted(fams, key=lambda f: ("Nerd Font" not in f, not fams[f], f.lower()))[:80]


def log_changes(changed: list[Path]) -> None:
    for p in changed:
        shown = p.relative_to(paths.ROOT) if p.is_relative_to(paths.ROOT) else str(p).replace(str(Path.home()), "~", 1)
        log(f"actualizado: {shown}")
