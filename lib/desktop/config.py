"""Carga de la configuración declarativa.

Orden de precedencia (el último gana):
  1. settings.json del repositorio (valores predeterminados)
  2. ~/.config/hyprland-desktop/settings.json (preferencias del usuario)
  3. ~/.local/state/hyprland-desktop/appearance.json (cambios hechos desde el selector visual)
"""
import json
from pathlib import Path

from . import paths


def _read_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise SystemExit(f"Error de sintaxis en {path}: línea {e.lineno}, columna {e.colno}: {e.msg}")


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(with_overlay: bool = True) -> dict:
    settings = _merge(_read_json(paths.DEFAULT_SETTINGS), _read_json(paths.USER_SETTINGS))
    if with_overlay:
        overlay = _read_json(paths.APPEARANCE_STATE)
        settings["appearance"] = _merge(settings.get("appearance", {}), overlay)
    return {k: v for k, v in settings.items() if not k.startswith("_")}


def default_appearance() -> dict:
    return load(with_overlay=False).get("appearance", {})


def write_json(path: Path, data) -> None:
    """Escritura atómica."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def read_state(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def set_appearance(key: str, value) -> None:
    overlay = _read_json(paths.APPEARANCE_STATE)
    overlay[key] = value
    write_json(paths.APPEARANCE_STATE, overlay)


def reset_appearance() -> None:
    paths.APPEARANCE_STATE.unlink(missing_ok=True)


def themes() -> dict:
    """Temas disponibles: los del repositorio y los añadidos por el usuario en ~/.config/hyprland-desktop/themes."""
    found = {}
    order = ["mocha", "macchiato", "frappe", "latte", "mono", "mono-light", "gruvbox-dark", "gruvbox-light", "nordic", "tokyonight"]
    for directory in (paths.THEMES_DIR, paths.USER_THEMES_DIR):
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("*.json")):
            data = _read_json(f)
            if "palette" in data:
                found[f.stem] = data
    return dict(sorted(found.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 99, kv[0])))


def default_browser() -> str:
    """Id del .desktop del navegador predeterminado del sistema (p. ej. 'brave-browser'), o ''."""
    import subprocess
    try:
        out = subprocess.run(["xdg-settings", "get", "default-web-browser"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return out.removesuffix(".desktop")


def app_command(settings: dict, name: str) -> str:
    """Comando de settings.apps.<name>; "default" en `browser` = navegador predeterminado."""
    value = settings.get("apps", {}).get(name, name)
    if name == "browser" and value == "default":
        desktop = default_browser()
        return f"gtk-launch {desktop}" if desktop else "xdg-open https://"
    return value


def resolve_app(settings: dict, command: str) -> str:
    """'@terminal' -> comando configurado en settings.apps."""
    if command.startswith("@"):
        return app_command(settings, command[1:])
    return command
