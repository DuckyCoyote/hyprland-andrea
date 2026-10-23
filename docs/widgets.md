# Widgets

Cada widget vive en `config/eww/widgets/<nombre>/` con su `.yuck` (estructura) y su
`.scss` (estilos). Todos usan los componentes de `config/eww/components/common.yuck` y los
tokens de `styles/tokens/` — nunca colores, fuentes ni tamaños literales.

| Widget | Ventana | Datos (tema del daemon) | Acciones (`desktopctl …`) |
|---|---|---|---|
| Barra | `bar` (una por monitor) | `wm`, `audio`, `network`, `media`, `updates`, `weather`, `system` | `wm focus/scroll`, `popup toggle …` |
| Lanzador | `launcher` | `apps` | `apps launch/favorite/rescan` |
| Configuración | `settings` | `appearance`, `system`, `wm` + los de audio/red | `appearance set/reset/apply`, `system …` |
| Energía | `power` | `system`, `popup.confirm` | `system power lock|suspend|hibernate|logout|reboot|poweroff` |
| Red | `network` | `network` | `network toggle-wifi/scan/connect/password/disconnect/editor` |
| Bluetooth | `bluetooth` | `bluetooth` | `bluetooth toggle-power/toggle-discoverable/scan/connect/disconnect/forget/editor` |
| Audio | `audio` | `audio` | `audio set/step/mute/default` |
| Actualizaciones | `updates` | `updates` | `updates refresh/update/changes` |
| Multimedia | `media` | `media` + `media_position` | `media toggle/next/previous/shuffle/loop/seek/select` |
| Clima | `weather` | `weather` | `weather refresh` |
| Calendario | `calendar` | reloj | — |
| Avisos | `notify_toasts` (arriba a la derecha) | `notifications.toasts` | `notifications hide/action` |
| Bandeja de notificaciones | `notifications` | `notifications.history` | `notifications dismiss/clear/dnd/action/test` |
| Bandeja del sistema | dentro de la barra (`systray`) | protocolo StatusNotifierItem | clic en los iconos |

## Notificaciones

`desktopd` implementa el servidor `org.freedesktop.Notifications` (sustituye a mako/dunst), así
los avisos usan el mismo sistema visual que la barra:

- Avisos emergentes arriba a la derecha, bajo la barra, en el monitor enfocado. Máx. 4 a la vez;
  6 s por defecto o el tiempo que pida la aplicación; las críticas no caducan.
- Clic en el aviso: acción predeterminada de la app (si la tiene); botones para el resto de
  acciones (p. ej. «Responder»). La aplicación recibe la acción por D-Bus.
- Al caducar, la notificación queda en la bandeja (campana de la barra, `Super+Alt+O`),
  con historial de las 50 últimas, descartar una a una o «Borrar todo».
- «No molestar» (clic derecho en la campana o `Super+Alt+D`) oculta los avisos que no son
  críticos; se guarda entre reinicios. Prueba: `desktopctl notifications test`.

Comportamiento común (gestor de popups, `lib/desktop/sources/popup.py`):

- Solo un popup a la vez; abrir otro cierra el anterior.
- Se abre en el monitor de la barra pulsada; con atajos, en el monitor enfocado.
- Clic fuera o Escape lo cierran. `desktopctl popup close` desde scripts.

Módulos que se ocultan solos: micrófono (sin dispositivo de entrada), batería (sin batería),
red (sin NetworkManager), reproductor (sin reproductor activo), espacios (compositor sin soporte),
clima (sin datos).

## Rendimiento

- Un único proceso (`desktopd`) produce todo el estado; Eww mantiene una conexión `socat`
  por tema (10 en total), compartida por todas las barras y popups.
- Eventos en lugar de sondeo: socket2 de Hyprland, `pactl subscribe`, `nmcli monitor`,
  `playerctl --follow`. Sondeos restantes: reloj (5 s, un `date`), posición del reproductor
  (1 s, **solo** con el panel multimedia abierto), `stat` de la base de pacman (30 s),
  clima (30 min, en caché), tiempo encendido (60 s, lectura de `/proc`).
- La búsqueda del lanzador se resuelve con `jq` dentro de Eww: no lanza procesos por tecla.
- El daemon no publica si el estado no cambió, así Eww no redibuja de más.

## Crear un widget nuevo

Ejemplo: indicador de temperatura de CPU.

1. **Datos** (si los necesita): crea `lib/desktop/sources/cputemp.py`:

   ```python
   import asyncio
   from ..daemon import Source

   class CpuTempSource(Source):
       topic = "cputemp"

       async def start(self):
           while True:
               temp = int(open("/sys/class/thermal/thermal_zone0/temp").read()) // 1000
               self.publish({"temp": temp})
               await asyncio.sleep(10)

       async def cmd_refresh(self):   # -> desktopctl cputemp refresh
           ...
   ```

   y añádela a la lista de `lib/desktop/sources/__init__.py`.
2. **Suscripción**: en `config/eww/vars.yuck`:
   `(deflisten cputemp :initial "{}" "desktop-sub cputemp")`
3. **Interfaz**: `config/eww/widgets/cputemp/cputemp.yuck` y `cputemp.scss`, usando
   componentes (`glyph`, `badge`, `card`, `popup-frame`…). Inclúyelos en `eww.yuck` y `eww.scss`.
4. **Barra**: añade `(box :visible {matches(modules, ",cputemp,")} (bar-cputemp))` en
   `widgets/bar/bar.yuck` y el nombre a `bar.modules` en `settings.json`.
5. Si es un popup: añade su nombre a `POPUPS` en `lib/desktop/sources/popup.py` y ábrelo con
   `desktopctl popup toggle cputemp ${monitor}`.

Reinicia con `desktopctl restart` y comprueba el estado con `desktopctl get cputemp`.
