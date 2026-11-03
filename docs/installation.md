# Instalación

## Requisitos

- Arch Linux o derivada (probado en Garuda Linux con kernel zen).
- Repositorio `chaotic-aur` para `eww` precompilado; si no está, el instalador ofrece
  construirlo con `paru`/`yay` (que muestran el PKGBUILD antes de compilar).
- PipeWire + WirePlumber y NetworkManager (ya activos en la mayoría de instalaciones).

## Pasos

```sh
./install.sh --dry-run   # simulación: no cambia nada
./install.sh             # instalación interactiva
```

El instalador:

1. Detecta Arch y el helper AUR.
2. Comprueba las dependencias y muestra las que faltan, separadas en repositorio/AUR.
3. Pide confirmación antes de instalar (`sudo pacman -S --needed …`).
4. Enlaza `~/.config/hypr`, `~/.config/eww`, `~/.local/bin/desktopctl` y
   `~/.local/bin/desktop-sub` al repositorio. Si ya existen, **pregunta** y los mueve a
   `~/.local/state/hyprland-desktop/backups/<fecha>/`.
5. Añade una línea `include` a `kitty.conf` (o lo crea si no existe). Nunca lo reemplaza.
   Opcionalmente (solo si respondes que sí; `--yes` no lo acepta) enlaza `~/.config/nvim` a
   `dotfiles/nvim` (AstroNvim) con respaldo, y enlaza el plugin que sincroniza el tema de Neovim.
   Si SDDM está instalado, ofrece copiar el tema `config/sddm/gnome-gdm` a
   `/usr/share/sddm/themes/` y activarlo (`/etc/sddm.conf.d/zz-hyprland-desktop.conf`), con sudo.
   Tras editar el tema en el repositorio, vuelve a ejecutar el instalador para actualizar la copia.
6. Copia `settings.json` a `~/.config/hyprland-desktop/` si aún no existe (nunca lo sobrescribe).
7. Genera los archivos derivados (`desktopctl apply`) y ejecuta `desktopctl doctor`.

Puede ejecutarse varias veces: lo ya enlazado se deja igual y no se duplican líneas.
No toca `~/.config/awesome` ni la configuración de KDE.

## Primer arranque

Cierra sesión y elige **Hyprland** en SDDM. Al iniciar, Hyprland ejecuta `desktopctl start`,
que arranca el daemon de estado; este abre Eww y una barra por monitor.

Si algo no aparece:

```sh
desktopctl doctor                          # dependencias y servicios
cat ~/.cache/hyprland-desktop/desktopd.log # registro del daemon
eww -c ~/.config/eww logs                  # errores de Eww
hyprctl configerrors                       # errores de la configuración Lua
```

## Restaurar la configuración anterior

```sh
./uninstall.sh --dry-run
./uninstall.sh
```

Quita los enlaces, devuelve a su sitio los respaldos registrados en
`~/.local/state/hyprland-desktop/install-manifest.tsv` y pregunta antes de borrar tu
`settings.json`. No desinstala paquetes. KDE Plasma sigue disponible en el gestor de sesiones.

## Extras opcionales (fuentes, tema de KDE e iconos)

`install.sh` **no** instala nada de esta sección. Son pasos manuales pensados para que los siga
un agente (Claude Code) cuando se le pida: «instala los extras de docs/installation.md». Todo va
a `~/.local/share` (sin sudo) salvo los paquetes de pacman.

### Fuentes

| Fuente | Para qué | Cómo |
|---|---|---|
| JetBrainsMono Nerd Font | glifos de todas las barras, barra Cyber | `sudo pacman -S ttf-jetbrains-mono-nerd` (ya lo ofrece `install.sh`) |
| CaskaydiaCove Nerd Font | kitty | `sudo pacman -S ttf-cascadia-code-nerd` (ya lo ofrece `install.sh`) |
| Inter | barras Aqua y Platinum | `sudo pacman -S inter-font` |
| Symbols Nerd Font (opcional) | respaldo de glifos; sin ella se usa JetBrainsMono NF | `sudo pacman -S ttf-nerd-fonts-symbols` |
| Manrope | fuente de la interfaz (Configuración → Apariencia → Fuente) | incluida: `cp -r assets/fonts/Manrope ~/.local/share/fonts/` |
| ChicagoFLF | títulos de ventana del tema KDE NiceOS9 | incluida: `cp assets/fonts/ChicagoFLF/ChicagoFLF.ttf ~/.local/share/fonts/` |

Licencias de las incluidas en `assets/fonts/NOTICE.md`. Tras copiar fuentes a mano: `fc-cache -f ~/.local/share/fonts` y `desktopctl appearance rescan`
(para que aparezcan en el menú de fuentes). Comprobar con `fc-list | grep -i <nombre>`.

### Iconos: Tela-ubuntu-light

Es el tema de iconos del usuario (KDE, GTK y lanzador). De
[vinceliuice/Tela-icon-theme](https://github.com/vinceliuice/Tela-icon-theme):

```sh
git clone --depth 1 https://github.com/vinceliuice/Tela-icon-theme <carpeta-temporal>/tela
<carpeta-temporal>/tela/install.sh -d ~/.local/share/icons ubuntu   # crea Tela-ubuntu, -light y -dark
kwriteconfig6 --file kdeglobals --group Icons --key Theme Tela-ubuntu-light
# GTK: gtk-icon-theme-name=Tela-ubuntu-light en ~/.config/gtk-3.0/settings.ini (y gtk-4.0)
```

Leer el `install.sh` de Tela antes de ejecutarlo. No usar los iconos NineIcons de NiceOS9 (las
carpetas azules no le gustaron al usuario).

### Tema de KDE retro: NiceOS9 (para el tema Platinum)

[NiceOS9](https://github.com/huppiflupp/NiceOS9-theme) (KDE Store id 2354228, probado con v5.4):
decoración Aurorae ChicagoNine, esquema de color Chicago Nine Light, estilo de Plasma
`niceos9-bright` y ChicagoFLF. Afecta a Plasma **y** a las apps Qt dentro de Hyprland (Dolphin lee
`~/.config/kdeglobals`, ver `config/hypr/modules/env.lua`), sea cual sea el tema de Hyprland.

**No ejecutar su `install.sh` tal cual**: además de copiar archivos instala
`~/.config/autostart/panel-nofloat.desktop` (cambia todos los paneles de Plasma en cada inicio) y
fija el fondo de la pantalla de bloqueo. Hacerlo a mano:

1. Descargar y descomprimir `NiceOS9-<versión>.zip` de la última release en una carpeta temporal
   vacía (`<NiceOS9>` = la carpeta `NiceOS9-theme` extraída).
2. Copia de seguridad de la configuración de KDE:
   ```sh
   B=~/.local/share/niceos9/backup-$(date +%Y%m%d-%H%M%S); mkdir -p "$B"
   for f in plasma-org.kde.plasma.desktop-appletsrc plasmarc kdeglobals kwinrc kscreenlockerrc ksplashrc kcminputrc; do
     [ -f ~/.config/$f ] && cp -a ~/.config/$f "$B/"; done
   ```
   y un `restore.sh` en `$B` que copie esos archivos de vuelta a `~/.config` y borre
   `~/.cache/plasma_theme_*.kcache`.
3. Copiar componentes (sin `autostart/` ni `icons/`):
   ```sh
   L=~/.local/share
   mkdir -p $L/plasma/look-and-feel $L/plasma/desktoptheme $L/color-schemes $L/aurorae/themes $L/fonts $L/wallpapers
   for v in niceos9-dark niceos9-bright niceos9-charcoal; do
     cp -r <NiceOS9>/look-and-feel/$v $L/plasma/look-and-feel/
     cp -r <NiceOS9>/desktoptheme/$v $L/plasma/desktoptheme/
     sed -i "s|HOME_PLACEHOLDER|$HOME|g; s|PANEL_HEIGHT_PLACEHOLDER|32|g" \
       $L/plasma/look-and-feel/$v/contents/layouts/org.kde.plasma.desktop-layout.js \
       $L/plasma/look-and-feel/$v/contents/lockscreen/LockScreenUi.qml
     cp <NiceOS9>/fonts/ChicagoFLF.ttf $L/plasma/look-and-feel/$v/contents/lockscreen/
   done
   cp <NiceOS9>/color-schemes/*.colors $L/color-schemes/
   cp -r <NiceOS9>/aurorae/{ChicagoNine,ChicagoNineDark,ChicagoEight} $L/aurorae/themes/
   cp assets/fonts/ChicagoFLF/ChicagoFLF.ttf $L/fonts/ && fc-cache -f $L/fonts   # o la del zip
   cp -r <NiceOS9>/wallpapers/NiceOS9 $L/wallpapers/
   ```
4. Aplicar solo lo visual (la disposición de paneles NO se toca):
   ```sh
   plasma-apply-colorscheme ChicagoNineLight
   plasma-apply-desktoptheme niceos9-bright
   kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Fusion
   kwriteconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage niceos9-bright
   kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key library org.kde.kwin.aurorae.v2
   kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme __aurorae__svg__ChicagoNine
   ```
   Iconos: mantener Tela-ubuntu-light. Fuente de títulos: el usuario tenía
   `Inter,10,-1,5,75,0,0,0,0,0,Bold` (`[WM] activeFont`); ChicagoFLF es opcional.
   El cursor del tema (XCursor-Pro-Red) ya no viene incluido: se mantiene `breeze_cursors`.
5. La decoración de ventanas se ve al volver a entrar en Plasma. Para el panel estilo OS 9:
   Configuración del sistema → Tema global → «NiceOS9 bright» marcando «Disposición del
   escritorio» (sustituye los paneles; la copia del paso 2 los guarda).

Deshacer: `<backup>/restore.sh` y cerrar sesión de Plasma.
