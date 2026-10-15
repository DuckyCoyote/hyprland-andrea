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
