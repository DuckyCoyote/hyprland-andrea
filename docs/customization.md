# Personalización

Todo se configura en **un único archivo**: `~/.config/hyprland-desktop/settings.json`
(los valores que no definas se toman de `settings.json` del repositorio). Tras editarlo:

```sh
desktopctl apply
```

| Sección | Qué controla |
|---|---|
| `apps` | terminal, navegador, explorador, editor (los usan atajos y accesos `@terminal`…); `shell`: intérprete con el que abre kitty (por defecto `fish`); `browser: "default"` usa el navegador predeterminado del sistema (`xdg-settings`) |
| `quick_launch` | accesos rápidos de la barra (orden, icono, comando, tooltip) |
| `monitors` | salida, modo, posición, escala, `primary` |
| `wallpaper` / `wallpaper_dir` | fondo inicial y carpeta que lee el selector de fondos (vacío = `~/Imágenes/Wallpapers`). El fondo y el cursor elegidos en Configuración → Apariencia se guardan en `appearance.json` y persisten entre sesiones |
| `nvim.sync_theme` | Neovim (monokai-pro) sigue el tema global con el fondo de kitty; `false` = tema original de Neovim |
| `bar.modules` / `bar.per_monitor` | qué grupos muestra la barra y en qué monitor (`window` = icono de la ventana enfocada, junto a los accesos rápidos tras un separador) |
| `workspaces.per_monitor` | número de espacios visibles por monitor |
| `keyboard`, `input` | distribución, variante, sensibilidad, desplazamiento natural |
| `weather` | ciudad y coordenadas (sin geolocalización), unidades, frecuencia |
| `updates` | frecuencia de comprobación y helper AUR (`auto`, `paru`, `yay`, `none`) |
| `idle` | minutos para bloquear, apagar pantalla y suspender (0 = nunca) |
| `wallpaper` | ruta de imagen; vacío = color sólido del tema |
| `appearance` | tema, acento, fuente, tamaño, radio, espaciado, transparencia, sombras, animaciones |
| `popups.close_on_click_outside` | cerrar paneles al hacer clic fuera |

## Accesos rápidos

```json
{ "name": "Spotify", "icon": "theme:spotify-client", "exec": "spotify", "tooltip": "Música" }
```

`icon` admite `assets:archivo.png` (en `assets/icons/`), `theme:nombre` (tema de iconos del
sistema), una ruta absoluta o un glifo Nerd Font. `exec` admite `@terminal`, `@browser`… para
reutilizar `apps`.

## Monitores

Los valores iniciales se detectaron del hardware real (DP-1 1920x1080@144 principal,
HDMI-A-1 1920x1080@60 a la izquierda). Para un monitor nuevo no hace falta nada: se configura
solo a la derecha. Para fijarlo, añádelo a `monitors`. `hyprctl monitors` lista los nombres.

Cada monitor tiene su bloque de espacios: el principal 1–9, el segundo 11–19, etc. `Super+N`
siempre va al espacio N **del monitor enfocado**, como las tags por pantalla de AwesomeWM.

## Apariencia en vivo

El selector visual (`Super+Shift+T` o clic derecho en el botón del lanzador) cambia tema,
acento, fuente, tamaños y efectos al instante. Los cambios se guardan en
`~/.local/state/hyprland-desktop/appearance.json` y tienen prioridad sobre `settings.json`;
«Restaurar valores predeterminados» borra ese archivo. Desde la terminal:

```sh
desktopctl appearance set theme frappe
desktopctl appearance set accent teal
desktopctl appearance set font_size 14
desktopctl appearance set animations toggle
desktopctl appearance reset
```

Se actualizan Eww, Hyprland (bordes, radio, huecos, sombras, animaciones), hyprlock,
kitty (recarga en vivo) y la preferencia clara/oscura de GTK.
