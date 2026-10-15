"""Rutas del proyecto y directorios XDG. Ningún otro módulo construye rutas a mano."""
import os
from pathlib import Path

APP = "hyprland-desktop"

# Raíz del repositorio (lib/desktop/paths.py -> ../../)
ROOT = Path(__file__).resolve().parents[2]


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else Path.home() / fallback


CONFIG_HOME = _xdg("XDG_CONFIG_HOME", ".config")
STATE_HOME = _xdg("XDG_STATE_HOME", ".local/state")
CACHE_HOME = _xdg("XDG_CACHE_HOME", ".cache")
RUNTIME_HOME = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/{APP}-{os.getuid()}")

# Configuración del usuario (editable) y estado persistente (gestionado por la app)
USER_CONFIG_DIR = CONFIG_HOME / APP
USER_SETTINGS = USER_CONFIG_DIR / "settings.json"
USER_THEMES_DIR = USER_CONFIG_DIR / "themes"
STATE_DIR = STATE_HOME / APP
APPEARANCE_STATE = STATE_DIR / "appearance.json"
LAUNCH_HISTORY = STATE_DIR / "launch-history.json"
UI_STATE = STATE_DIR / "ui.json"
CACHE_DIR = CACHE_HOME / APP
RUNTIME_DIR = RUNTIME_HOME / APP

# Archivos del repositorio
DEFAULT_SETTINGS = ROOT / "settings.json"
THEMES_DIR = ROOT / "themes"
ASSETS_DIR = ROOT / "assets"
EWW_DIR = ROOT / "config" / "eww"
HYPR_DIR = ROOT / "config" / "hypr"
KITTY_DIR = ROOT / "config" / "kitty"
CTL = ROOT / "bin" / "desktopctl"
SUB = ROOT / "bin" / "desktop-sub"


def socket_path(name: str) -> Path:
    return RUNTIME_DIR / f"{name}.sock"


def ensure_dirs() -> None:
    for d in (STATE_DIR, CACHE_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
