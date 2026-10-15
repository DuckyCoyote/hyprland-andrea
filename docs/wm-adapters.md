# Portar a otro compositor

Los elementos de Eww son independientes del gestor de ventanas:

- Ningún `.yuck` llama a `hyprctl` (ni a otra herramienta del compositor). Leen estado de
  `deflisten` y ejecutan `desktopctl …`.
- Las barras y popups los abre `desktopd`, no la configuración de Hyprland.
- Lo único específico de Hyprland vive en `lib/desktop/wm/hyprland.py` y en `config/hypr/`.

## La interfaz

`lib/desktop/wm/base.py` define `WindowManager`. Un adaptador implementa:

| Método | Uso |
|---|---|
| `start(on_change)` | escuchar eventos y llamar `on_change("workspaces"|"monitors"|"focus")` |
| `monitors()` | lista de monitores con `name`, `model`, `screen` (identificador para `eww --screen`), tamaño, foco y espacio activo |
| `workspaces()` | lista de espacios con `id`, `monitor`, `windows`, `urgent` |
| `focused_monitor()` | nombre del monitor enfocado (para abrir popups con atajos) |
| `focus_workspace(id)` | cambiar de espacio |
| `popup_mode(bool)` | opcional: modo de teclado donde Escape cierra popups |
| `reload()` | recargar la configuración tras cambiar de tema |
| `logout()` | cerrar la sesión |

Sin adaptador se usa la implementación base: barras en los monitores de `settings.json`,
grupo de espacios oculto y cierre de sesión con `loginctl`.

## Ejemplo: Sway

```python
# lib/desktop/wm/sway.py
import asyncio, json
from ..util import run
from .base import WindowManager

class Sway(WindowManager):
    name = "sway"
    has_workspaces = True

    async def start(self, on_change):
        proc = await asyncio.create_subprocess_exec(
            "swaymsg", "-m", "-t", "subscribe", '["workspace","output"]',
            stdout=asyncio.subprocess.PIPE)
        while line := await proc.stdout.readline():
            ev = json.loads(line)
            await on_change("monitors" if "output" in ev.get("change", "") else "workspaces")

    async def workspaces(self):
        _, out, _ = await run("swaymsg", "-t", "get_workspaces", "-r")
        return [{"id": w["num"], "name": w["name"], "monitor": w["output"],
                 "windows": 1 if w.get("focus") else 0, "urgent": w["urgent"]} for w in json.loads(out)]

    async def focus_workspace(self, workspace_id):
        await run("swaymsg", "workspace", "number", str(workspace_id))
    # monitors(), logout()… análogos con get_outputs / exit
```

Regístralo en `lib/desktop/wm/__init__.py`:

```python
("sway", lambda: bool(os.environ.get("SWAYSOCK")), lambda: __import__(...).Sway()),
```

y arranca `desktopctl start` desde la configuración del compositor. El resto (barra,
popups, temas, audio, red…) funciona sin cambios. Para fijar un adaptador, usa
`"wm": "sway"` en `settings.json`.

> El ejemplo de Sway es ilustrativo y no está probado.
