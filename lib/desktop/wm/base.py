"""Interfaz que debe implementar cada adaptador de gestor de ventanas.

Eww y el resto del proyecto solo conocen esta interfaz: para portar el entorno a otro
compositor (Sway, niri, river, bspwm...) basta con escribir un adaptador nuevo en este
directorio y registrarlo en wm/__init__.py. Ver docs/wm-adapters.md.
"""
import os
from typing import Awaitable, Callable

from .. import config
from ..util import run

OnChange = Callable[[str], Awaitable[None]]


class WindowManager:
    name = "generic"
    #: el adaptador entiende de espacios de trabajo (si es False la barra oculta el grupo)
    has_workspaces = False

    async def start(self, on_change: OnChange) -> None:
        """Escucha eventos del compositor y llama on_change('workspaces'|'monitors'|'focus').
        Debe ejecutarse indefinidamente. Implementación por defecto: sin eventos."""

    async def monitors(self) -> list[dict]:
        """[{name, model, width, height, refresh, scale, x, y, focused, active_workspace}]"""
        out = []
        for i, m in enumerate(config.load().get("monitors", [])):
            out.append({"name": m["name"], "model": "", "screen": i, "width": 0, "height": 0,
                        "refresh": 0, "scale": m.get("scale", 1), "x": 0, "y": 0,
                        "focused": i == 0, "active_workspace": None})
        return out

    async def workspaces(self) -> list[dict]:
        """[{id, name, monitor, windows, urgent}]"""
        return []

    async def active_windows(self) -> dict[str, dict]:
        """{monitor: {class, title}}: ventana enfocada en el espacio visible de cada monitor."""
        return {}

    async def focused_monitor(self) -> str | None:
        for m in await self.monitors():
            if m["focused"]:
                return m["name"]
        return None

    async def focus_workspace(self, workspace_id: int) -> None:
        pass

    async def popup_mode(self, enabled: bool) -> None:
        """Activa/desactiva un modo de teclado en el que Escape cierra los popups."""

    async def count_layers(self, namespace: str) -> int | None:
        """Número de superficies layer-shell con ese namespace (None si no se puede saber)."""
        return None

    async def set_cursor(self, theme: str, size: int) -> None:
        """Cambia el tema de cursor en caliente (si el compositor lo permite)."""

    async def reload(self) -> None:
        """Recarga la configuración del compositor (tras cambiar de tema)."""

    async def logout(self) -> None:
        session = os.environ.get("XDG_SESSION_ID")
        if session:
            await run("loginctl", "terminate-session", session)
        else:
            await run("loginctl", "terminate-user", os.environ.get("USER", ""))
