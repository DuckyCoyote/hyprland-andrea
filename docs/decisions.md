# Decisiones técnicas y estado de validación

## Diagnóstico inicial (fase 1)

| Elemento | Detectado |
|---|---|
| Sistema | Garuda Linux (Arch), kernel 7.2.9-zen, sesión actual KDE Plasma (Wayland) |
| GPU | NVIDIA RTX 4060 (AD107), `nvidia-open-dkms` 615.78.08, `nvidia_drm.modeset=Y`, `fbdev=Y` |
| Monitores | **DP-1** LG ULTRAGEAR 1920x1080@144 (principal, x=1920) · **HDMI-A-1** Samsung C24F390 1920x1080@60 (x=0) |
| Audio | PipeWire 1.6.9 + WirePlumber 0.5.18 + pipewire-pulse |
| Red | NetworkManager con Ethernet y Wi-Fi activos |
| Teclado | `latam` |
| Hyprland en repos | 0.56.2 (`extra`) — **configuración en Lua** (`hyprland.lua`) |
| Eww en repos | 0.6.0 (`chaotic-aur`) |

Los nombres y modos de los monitores se tomaron de `kscreen-doctor` (mismos nombres DRM que
usa Hyprland). Están en `settings.json` y se pueden cambiar sin tocar código.

## Decisiones

1. **Hyprland 0.56 con Lua.** El paquete actual trae `hyprland.lua` como ejemplo y una API
   `hl.*`; la sintaxis hyprlang (`hyprland.conf`) sigue existiendo como modo heredado. Se usa Lua
   porque es el formato actual, permite funciones en los atajos (espacios por monitor, ciclo de
   layouts) y módulos con `require`. La API se verificó en el código fuente de la etiqueta
   v0.56.2 (dispatchers, reglas, eventos) y la configuración se valida con un arnés que ejecuta
   todos los módulos contra una API simulada con las 384 claves de configuración oficiales.
   hyprlock/hypridle 0.9/0.1 siguen usando hyprlang y se generan en ese formato.
2. **Controlador central de estado (`desktopd`, Python asyncio).** Un proceso escucha eventos y
   publica JSON por tema en sockets Unix; Eww se suscribe con `deflisten` + `socat`. Ventajas:
   un productor por dominio sin importar el número de monitores, cero lógica de sistema en los
   widgets, estado inmediato al reiniciar Eww, y una única CLI (`desktopctl`) para acciones.
   Bash habría obligado a muchos scripts sueltos y a analizar JSON con jq en cada evento.
3. **Abstracción del compositor** (petición añadida): Eww no conoce a Hyprland. Ver
   `docs/wm-adapters.md`.
4. **Gestor de popups** en el daemon: exclusividad, monitor correcto, cierre por clic fuera
   (capa transparente) y por Escape (submapa de Hyprland activado por el adaptador).
5. **Eww identifica monitores por modelo**, no por conector (comprobado: `--screen DP-1` falla,
   `--screen "LG ULTRAGEAR"` funciona). El adaptador traduce conector → modelo y recurre al
   índice si dos monitores comparten modelo.
6. **Sistema de temas**: paleta completa Catppuccin por tema → capa semántica SCSS → componentes.
   Un único generador (`render.py`) escribe la configuración de cada programa; los cambios del
   selector se guardan aparte (`appearance.json`) para poder restaurar los valores por defecto.
7. **Notificaciones propias** en lugar de mako: el mismo sistema visual que la barra, avisos
   arriba a la derecha bajo la barra, bandeja con historial, acciones y «no molestar».
8. **Clima con Open-Meteo**: API documentada, sin clave ni geolocalización; coordenadas en
   `settings.json`, caché en disco y datos guardados si falla la red.
9. **Actualizaciones** con `checkupdates` (no toca la base de datos del sistema) y `paru -Qua`;
   nunca se actualiza en silencio: se abre una terminal interactiva.
10. **Wi-Fi**: la contraseña se entrega a NetworkManager por la entrada estándar de
    `nmcli --ask` y no se guarda en el proyecto. Limitación de Eww: el texto del campo pasa por la
    línea de órdenes de `sh -c` durante unos milisegundos al pulsar Enter.
11. **Iconos de la barra** de gh0stzk (GPL-3.0) → el proyecto se licencia GPL-3.0.

## Estado de validación

Probado en esta máquina (sesión KDE Wayland, Eww 0.6 ejecutado localmente sin instalar):

| Componente | Estado |
|---|---|
| Daemon: temas `audio`, `network`, `system`, `updates`, `weather`, `apps`, `appearance` con datos reales | ✔ verificado |
| Barras en ambos monitores, fondo transparente, módulos por monitor | ✔ verificado |
| Popups: audio, red, actualizaciones, clima, calendario, energía, lanzador (búsqueda), configuración | ✔ verificado visualmente |
| Cambio de tema en vivo (Mocha → Latte, acento) y persistencia; restaurar predeterminados | ✔ verificado |
| Notificaciones: servidor D-Bus, avisos, bandeja, acciones devueltas a la app, no molestar | ✔ verificado (en bus de sesión privado) |
| Espacios con iconos de Andrea y grupo del reproductor | ✔ verificado con estado simulado |
| Configuración Lua de Hyprland | ✔ validada contra API simulada + código fuente 0.56.2 |
| `install.sh --dry-run` | ✔ verificado |

**Pendiente de validar en Hyprland real** (requiere instalar los paquetes e iniciar la sesión):

- Arranque de Hyprland con la configuración Lua, monitores y espacios por monitor.
- Adaptador Hyprland (eventos socket2, cambio de espacio por clic/rueda, espacios urgentes).
- Submapa de Escape, capa de cierre por clic fuera (en KDE produce un artefacto propio de KWin).
- Ciclo de disposiciones con `Super+Espacio` (`hl.config` en tiempo de ejecución).
- Reproductor con `playerctl` real (no instalado aún), bandeja del sistema (en KDE la ocupa Plasma).
- Desconexión/reconexión de monitores, suspensión, bloqueo con hyprlock, hypridle.
- Conexión a una red Wi-Fi nueva con contraseña (`nmcli --ask`).
- Cursor por hardware con NVIDIA: si hay parpadeos, añadir `cursor = { no_hardware_cursors = true }`
  en `modules/look.lua`.

## Credenciales (KWallet)

En Plasma el servicio de contraseñas (`org.freedesktop.secrets`) lo da KWallet: el PAM de SDDM
arranca `ksecretd` con la contraseña de inicio de sesión y el autoarranque `pam_kwallet_init` lo
conecta al bus. Hyprland no ejecuta ese autoarranque, así que D-Bus activaba gnome-keyring (vacío)
y Brave, Teams o `gh` parecían haber perdido sus credenciales (seguían en `kdewallet.kwl`).
Solución: `modules/autostart.lua` ejecuta `pam_kwallet_init`, el instalador registra `ksecretd`
como `org.freedesktop.secrets` para el usuario, y Brave/Teams reciben `--password-store=kwallet6`
(Chromium/Electron solo eligen KWallet por sí mismos si el escritorio se llama KDE).

Además, `pam_gnome_keyring auto_start` (en el PAM de SDDM y de GDM) arranca gnome-keyring con el
componente `secrets`, que se queda con `org.freedesktop.secrets` antes que `ksecretd` (el archivo de
servicio D-Bus solo cuenta si nadie tiene ya el nombre). gnome-keyring no se desinstala porque otros
paquetes dependen de él (`github-desktop`, `qtkeychain-qt6`): el instalador lo deja solo con `pkcs11`
(drop-in de `gnome-keyring-daemon.service`).

**GDM** no sirve: su PAM (`gdm-password`) no incluye `pam_kwallet5`, así que el monedero no recibe la
contraseña de inicio y queda cerrado. Se probó a añadirlo a `/etc/pam.d/gdm-password`, pero en vez de
mantener un PAM propio el instalador ofrece volver a **SDDM**, cuyo PAM ya lo trae.

## Shift trabada (ratón Maxxter L8 Pro)

De vez en cuando Shift se queda pulsada sin que nadie la toque (pasaba también en KDE y GNOME, así
que no es cosa de Hyprland). El receptor inalámbrico del ratón Maxxter se presenta como **Realtek L8
Pro** (USB `248a:ffe2`) y expone dos interfaces: «Realtek L8 Pro» (ratón) y «Realtek L8 Pro
Keyboard», un teclado completo con Shift incluido. Si esa interfaz envía «Shift pulsada» y nunca
«Shift suelta», el sistema la da por mantenida.

Indicios (2026-10-22): las dos veces que ocurrió, el registro del kernel muestra
`usb 1-5.3: USB disconnect` de ese receptor (01:51 y 19:05) justo antes de reiniciar, y ningún otro
dispositivo se desconectó. El otro sospechoso es el Philips SPK9304 (`1bcf:08a0`), que también
tiene interfaz de teclado.

Para comprobarlo:

- Ver qué teclas cree el kernel que están pulsadas en cada dispositivo: la ioctl `EVIOCGKEY` sobre
  `/dev/input/event*` (el usuario está en el grupo `input`). Shift izquierda es el código 42 y la
  derecha, 54.
- `journalctl -b -1 -k | grep -iE 'disconnect|248a|1bcf'` tras reiniciar por el fallo.
- Salida rápida sin reiniciar: desconectar y volver a conectar el receptor; al desaparecer el
  dispositivo se sueltan sus teclas.

Arreglo propuesto (pendiente de aplicar): que libinput ignore solo la interfaz de teclado del
receptor, con lo que el ratón sigue funcionando y vale para cualquier escritorio:

```sh
printf '%s\n' 'ACTION=="add|change", KERNEL=="event*", ATTRS{idVendor}=="248a", ATTRS{idProduct}=="ffe2", ATTRS{name}=="Realtek L8 Pro Keyboard", ENV{LIBINPUT_IGNORE_DEVICE}="1"' \
  | sudo tee /etc/udev/rules.d/90-l8pro-no-keyboard.rules
sudo udevadm control --reload && sudo udevadm trigger -s input
```

Efecto secundario posible: si los botones laterales o especiales del ratón envían teclas, dejarían
de funcionar. Para deshacerlo, borrar el archivo de la regla y repetir el `udevadm`.
