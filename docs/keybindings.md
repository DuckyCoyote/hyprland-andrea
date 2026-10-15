# Atajos de teclado

Definidos en `config/hypr/modules/keybinds.lua` (una tabla con descripción por atajo). La
misma tabla genera la chuleta de **Configuración → Atajos** (`Super+S`).

Origen: `keys/globalkeys.lua` y `keys/clientkeys.lua` de
[awesome-minimal](https://github.com/DuckyCoyote/awesome-minimal), adaptados a Hyprland.

## Aplicaciones y paneles

| Atajo | Acción | En AwesomeWM |
|---|---|---|
| Super+Return | Terminal | igual |
| Super+B | Navegador | igual |
| Super+E | Explorador de archivos | *nuevo* |
| Super+R / Super+P / Super+Shift+D | Lanzador | prompt / menubar / rofi combi |
| Super+W | Configuración | menú principal |
| Super+S | Chuleta de atajos flotante (capa centrada, agrupada por secciones) | hotkeys_popup |
| Super+Shift+T | Selector de temas y fuentes | *nuevo* |
| Super+Shift+Q | Menú de energía (con confirmación) | salir de awesome (inmediato) |
| Super+Ctrl+R | Recargar Hyprland y Eww | awesome.restart |
| Super+Alt+L | Bloquear pantalla | *nuevo* |
| Super+Alt+N / A / M / U | Paneles de red / audio / multimedia / actualizaciones | *nuevo* |
| Super+Alt+O | Bandeja de notificaciones | *nuevo* |
| Super+Alt+D | No molestar | *nuevo* |
| Escape | Cerrar el panel abierto | — |

## Espacios de trabajo (por monitor)

| Atajo | Acción |
|---|---|
| Super+1…9 | Ir al espacio N del monitor enfocado |
| Super+Shift+1…9 | Mover la ventana al espacio N (y seguirla) |
| Super+Ctrl+1…9 | Enviar la ventana al espacio N sin seguirla |
| Super+Left / Right | Espacio anterior / siguiente del monitor |
| Super+Escape | Espacio anterior (historial) |
| Super+rueda | Recorrer espacios |

## Ventanas

| Atajo | Acción |
|---|---|
| Super+J / K | Enfocar siguiente / anterior |
| Super+Shift+J / K | Intercambiar con siguiente / anterior |
| Super+Ctrl+J / K | Enfocar monitor siguiente / anterior |
| Super+Alt+flechas | Enfocar por dirección |
| Super+U | Ir a la ventana urgente |
| Super+Tab | Ventana anterior |
| Super+F | Pantalla completa |
| Super+M | Maximizar |
| Super+Shift+C | Cerrar |
| Super+Ctrl+Space | Flotante |
| Super+Ctrl+Return | Intercambiar con la maestra |
| Super+O | Mover al otro monitor |
| Super+T | Fijar (pin) — solo ventanas flotantes |
| Super+N / Super+Ctrl+N | Minimizar / mostrar minimizadas |
| Super+arrastrar (izq./der.) | Mover / redimensionar |

## Disposición (layout)

| Atajo | Acción |
|---|---|
| Super+L / H | Ampliar / reducir el área maestra |
| Super+Shift+H / L | Añadir / quitar ventana maestra |
| Super+Ctrl+H / L | Cambiar orientación |
| Super+Space / Super+Shift+Space | master → dwindle → scrolling |

## Otros

| Atajo | Acción |
|---|---|
| Super+Shift+S | Captura de región (portapapeles + `~/Imágenes/Capturas`) |
| Impr Pant | Captura completa |
| Teclas multimedia | Volumen, micrófono, brillo, reproducción (funcionan bloqueado) |

## Conflictos y adaptaciones

- **Super+L** conserva su función de Awesome (ampliar área maestra); por eso bloquear es
  **Super+Alt+L** y no Super+L como en otros entornos.
- **Super+S** muestra la ayuda (Awesome), no el *scratchpad* del ejemplo de Hyprland.
- **Super+Ctrl+N** en Awesome «alternaba la tag»; Hyprland no tiene ventanas en varios
  espacios a la vez, así que pasa a «enviar sin seguir». **Super+Ctrl+Shift+N** (alternar
  ventana en tag) no tiene equivalente y no se asigna.
- **Super+Ctrl+M / Super+Shift+M** (maximizar vertical/horizontal) no existen en Hyprland.
- **Super+X** (prompt de Lua) no tiene equivalente.
- **Super+Shift+Q** ya no cierra la sesión al instante: abre el menú de energía, que pide
  confirmación.
- Mientras un panel está abierto, Hyprland entra en el submapa `hd-popup`: solo Escape está
  asignado (el resto de teclas llega al panel, p. ej. para escribir en el lanzador).
