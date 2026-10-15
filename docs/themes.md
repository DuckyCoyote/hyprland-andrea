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
- `base`/`mantle`/`crust`: fondos de mayor a menor luminosidad (en temas claros, al revés que
  el texto). `surface*`: tarjetas y bordes. `overlay*`/`subtext*`: textos secundarios.
- Los 14 colores con nombre se ofrecen como acentos en el selector.

Aparece automáticamente en el selector. Para activarlo: `desktopctl appearance set theme <archivo-sin-.json>`.

## Qué genera un tema

`lib/desktop/render.py` es el único lugar que traduce tokens a cada programa:

| Destino | Archivo generado |
|---|---|
| Eww | `config/eww/styles/tokens/_generated.scss` |
| Hyprland | `config/hypr/generated/theme.lua` |
| hyprlock | `config/hypr/hyprlock.conf` |
| kitty | `config/kitty/theme.conf` |

Para soportar otro programa (p. ej. rofi o GTK), añade una función a `render.py` y su ruta en
`targets()`.
