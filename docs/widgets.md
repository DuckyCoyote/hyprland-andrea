# Widgets

Cada widget vive en `config/eww/widgets/<nombre>/` con su `.yuck` (estructura) y su
`.scss` (estilos). Todos usan los componentes de `config/eww/components/common.yuck` y los
tokens de `styles/tokens/` — nunca colores, fuentes ni tamaños literales.

| Widget | Ventana | Datos (tema del daemon) | Acciones (`desktopctl …`) |
|---|---|---|---|
| Barra | `bar` (una por monitor) | `wm`, `audio`, `network`, `media`, `updates`, `weather`, `system` | `wm focus/scroll`, `popup toggle …` |
| Barra «Cyber» | `bar` (`bar_style: cyber`) | `recon` (VPN, LAN, objetivo) y los de la barra | `recon target <ip> [nombre]`, `recon target-paste/target-clear`, `recon copy vpn|lan|target` |
| Barra inferior | `bar-bottom` (estilo «Inferior», `bar_style: taskbar`; la abre desktopd en lugar de `bar`) | `wm` (incluye `wm.tasks`: accesos rápidos fijados + apps abiertas), `weather` y los de la barra | `wm task <clase>`, `system quick <n>`, `popup toggle …` |
| Lanzador | `launcher` | `apps` | `apps launch/favorite/rescan` |
| Lanzador Rofi | `launcher-rofi` (`launcher_style: rofi`) | `apps` (incluye `cmd`, el programa de cada app) | `apps launch/favorite` |
| Menú de inicio | `startmenu` (con la barra inferior: Super+R y el botón de inicio lo abren en lugar del lanzador) | `apps`, `system` | `apps launch/favorite` |
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

## Barra inferior y menú de inicio

Configuración → Apariencia → Barra → «Inferior» cambia a una barra de tareas abajo (estilo
Windows 11 con islas como las cápsulas): clima y espacios compactos a la izquierda; en el centro
el botón de inicio y las apps (primero los accesos rápidos de `quick_launch`, con un punto si están
abiertos, y después el resto de apps abiertas); a la derecha reproductor, bandeja, indicadores,
fecha y hora, notificaciones y energía. Clic en una app abierta la enfoca (otro clic pasa a su
siguiente ventana); clic central en una fijada abre otra ventana.

Con este estilo los paneles se abren abajo, junto a su botón (`popup.py` pasa `--anchor`/`--pos`
a `eww open`), y el lanzador es el menú de inicio: buscador, «Fijadas» (las favoritas; clic derecho
fija o desfija), «Recientes», «Todas las apps» por letra y un pie con usuario, bloqueo,
configuración y energía.

## Barras «Aqua» y «Platinum» (macOS oscuro y Mac OS 9)

Configuración → Apariencia → Barra. Pensadas para los temas «Aqua Oscuro» y «Platinum». Ambas van
de borde a borde (anulan el margen de `.bar`) y, en lugar de los menús Archivo/Edición/Ver, muestran
entradas útiles con el mismo aspecto de menú:

- **Aqua** (`mac-dark-theme.webp`): franja fina translúcida, Inter, todo monocromo. Izquierda:
  logo de Garuda (clic: lanzador · derecho: energía), aplicación enfocada en negrita (clic: selector
  de ventanas), grupo y escritorios como entradas de menú (el activo resaltado) y lo que suena.
  Derecha: `CPU n% RAM n%` (clic: Configuración → Sistema), bandeja, actualizaciones (solo si hay),
  micrófono (solo si está abierto, en naranja como en macOS), Bluetooth, red, volumen, batería,
  buscar (lanzador), «centro de control» (notificaciones; derecho: no molestar) y fecha y hora.
- **Platinum** (`mac-retro-*.png`): gris con línea negra, negrita y resaltado invertido en azul
  Platinum. Tux arcoíris en el sitio de la manzana (`assets/icons/tux-rainbow.png`), «Ajustes»,
  grupo, escritorios y reproductor; a la derecha la hora con segundos (`platinum_clock`, solo se
  consulta con esta barra), extras y el menú de aplicaciones de OS 9 (icono + aplicación enfocada →
  selector de ventanas). Fuente: Inter en negrita.

## Barra «Cyber» (pentesting y bug bounty)

Configuración → Apariencia → Barra → «Cyber» (pensada para el tema Cyber, colores de
`cyber.png`): franja negra monoespaciada con aristas rectas y una línea de neón abajo.

- Izquierda: calavera (lanzador), espacios como celdas `01…06` y la ventana enfocada como un
  prompt `usuario@equipo ❯ app título_`.
- Centro: **objetivo** (`TARGET 10.10.11.42:8080 // nombre ●`). Admite puerto: el punto es verde
  si el puerto acepta conexiones TCP (sin puerto, si responde a ping) y rojo si no; cada 15 s.
  Clic: copiar `host[:puerto]` · clic central: tomarlo del portapapeles (la primera IP o dominio,
  con su puerto; de una URL, host y puerto) · clic derecho: borrar. Sin objetivo, el clic lo pega.
  Desde la terminal: `desktopctl recon target 10.10.11.42:8080 Nombre`.
- Derecha: **VPN** (primera interfaz `tun*`/`tap*`/`wg*`/`ppp*` con IPv4: OpenVPN de HTB/THM,
  WireGuard…) y **LAN** (interfaz de la ruta por defecto que no es túnel); clic copia la IP, clic
  derecho en la LAN abre el panel de red. Después indicadores, fecha/hora y energía.

La fuente `recon` (`lib/desktop/sources/recon.py`) escucha `ip monitor address route`. El
objetivo persiste en `~/.local/state/hyprland-desktop/target.json` y, solo la dirección, en
`~/.local/state/hyprland-desktop/target` (y el puerto en `…/target-port`), para usarlo en la shell:
`set -gx TARGET (cat ~/.local/state/hyprland-desktop/target)`.

## Estilos de lanzador

Configuración → Apariencia → Lanzador (`appearance.launcher_style`): «Cuadrícula» (`launcher`),
«Rofi» (`launcher-rofi`, como rofi.webp: secciones como iconos con la activa en verde, barra
«Sección : búsqueda» con el recuento, filas de icono + nombre + programa y la elegida en azul) o
«Inicio» (`startmenu`). Sin elegir, la barra inferior usa «Inicio» y las demás «Cuadrícula».
`desktopctl popup toggle launcher` abre siempre el estilo elegido.

Posición (`popup.py`, `_placement`): con el atajo de teclado (monitor `focused`) se abre en el
centro de la pantalla; desde el icono de la barra, pegado a él (debajo con las barras superiores,
encima y centrado con la inferior).
