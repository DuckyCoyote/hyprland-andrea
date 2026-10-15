"""Selección del adaptador de gestor de ventanas.

Para añadir un compositor: crea wm/<nombre>.py con una subclase de WindowManager y añade
una entrada a ADAPTERS con la función que detecta si está en ejecución.
"""
import os

from .base import WindowManager


def _hyprland():
    from .hyprland import Hyprland
    return Hyprland()


# (nombre, detector, constructor) — se prueba en orden
ADAPTERS = [
    ("hyprland", lambda: bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")), _hyprland),
]


def detect(preferred: str = "auto") -> WindowManager:
    for name, is_running, make in ADAPTERS:
        if preferred == name or (preferred == "auto" and is_running()):
            return make()
    return WindowManager()
