# Temas

Un tema es un JSON con la paleta completa de Catppuccin (26 colores con nombre). Los
widgets no conocen colores: usan roles semánticos (`styles/tokens/_semantic.scss`) que se
derivan de esa paleta, así que un tema nuevo no requiere tocar ningún componente.

## Crear uno

Copia un tema y cambia los valores. Puedes dejarlo en el repositorio (`themes/`) o, sin
tocar el repositorio, en `~/.config/hyprland-desktop/themes/`:

```json
{
  "name": "Mi tema",
  "variant": "dark",
  "palette": {
    "rosewater": "#…", "flamingo": "#…", "pink": "#…", "mauve": "#…", "red": "#…",
    "maroon": "#…", "peach": "#…", "yellow": "#…", "green": "#…", "teal": "#…",
    "sky": "#…", "sapphire": "#…", "blue": "#…", "lavender": "#…",
    "text": "#…", "subtext1": "#…", "subtext0": "#…",
    "overlay2": "#…", "overlay1": "#…", "overlay0": "#…",
    "surface2": "#…", "surface1": "#…", "surface0": "#…",
    "base": "#…", "mantle": "#…", "crust": "#…"
  }
}
```

- `variant`: `dark` o `light` (ajusta la preferencia de GTK y la paleta ANSI de kitty).
- `icon_palette` (opcional): id de otro tema del que tomar los colores de los iconos (clases
  `.c-*`: campana, micrófono, actualizaciones…). El tema monocromo usa `"mocha"` para que los
  iconos conserven su color.
- `kitty.text_palette` (opcional): id del tema del que kitty toma los colores del texto (primer
  plano y paleta ANSI) manteniendo los fondos propios. El monocromo usa `"mocha"`.
- `base`/`mantle`/`crust`: fondos de mayor a menor luminosidad (en temas claros, al revés que
  el texto). `surface*`: tarjetas y bordes. `overlay*`/`subtext*`: textos secundarios.
- Los 14 colores con nombre se ofrecen como acentos en el selector.

Aparece automáticamente en el selector. Para activarlo: `desktopctl appearance set theme <archivo-sin-.json>`.

## Qué genera un tema

`lib/desktop/render.py` es el único lugar que traduce tokens a cada programa:

| Destino | Archivo generado |
|---|---|
| Eww | `~/.cache/hyprland-desktop/eww/_generated.scss` (enlace en `config/eww/styles/tokens/`; fuera de la carpeta de Eww para que solo el daemon decida cuándo recargar) |
| Hyprland | `config/hypr/generated/theme.lua` |
| hyprlock | `config/hypr/hyprlock.conf` |
| kitty | `config/kitty/theme.conf` |

Para soportar otro programa (p. ej. rofi o GTK), añade una función a `render.py` y su ruta en
`targets()`.

## Kitty y Neovim

- **kitty** (`config/kitty/theme.conf`, generado): colores del tema y pestañas arriba,
  minimalistas (píldora redondeada con el número en un círculo y el nombre; activa con el acento).
  Incluye `config/kitty/keys.conf` (fijo): los atajos de awesome-minimal (ventanas con
  Ctrl+flechas, búferes F3–F6, Ctrl+Shift+Z, pestaña/ventana en el directorio actual, Alt+flechas
  por palabras, Alt+} Unicode).
- **Neovim**: `config/nvim/lua/hyprland_desktop/palette.lua` (generado) contiene una paleta para
  monokai-pro con el mismo reparto de colores que la configuración original del usuario y el
  fondo idéntico al de kitty. El plugin `config/nvim/hyprland-desktop.lua` (enlazado en
  `~/.config/nvim/lua/plugins/`) solo sustituye `override_palette`: las cursivas y demás ajustes se
  conservan, y las instancias abiertas cambian de tema al momento. Un tema con
  `"nvim": { "backgrounds_only": true }` (Mocha y el monocromo) solo cambia los fondos del editor y del
  explorador y mantiene los colores originales de Neovim. Con
  `"nvim": { "sync_theme": false }` Neovim vuelve a su tema original.
