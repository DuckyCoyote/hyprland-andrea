#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# hyprland-desktop · instalador
#
#   ./install.sh               instalación interactiva
#   ./install.sh --dry-run     muestra lo que haría sin cambiar nada
#   ./install.sh --yes         acepta las preguntas (excepto la contraseña de sudo)
#   ./install.sh --no-packages solo enlaza la configuración
#
# Garantías:
#   - Nunca instala paquetes ni sobrescribe archivos sin mostrarlo y pedir confirmación.
#   - Todo lo que reemplaza se mueve a ~/.local/state/hyprland-desktop/backups/<fecha>/
#     y se registra en un manifiesto que usa ./uninstall.sh para restaurarlo.
#   - Se puede ejecutar varias veces: lo que ya está enlazado se deja como está.
#   - No toca ~/.config/awesome ni la configuración de otros entornos.
#   - No descarga ni ejecuta scripts remotos. Los paquetes AUR se construyen con el
#     helper instalado, que muestra el PKGBUILD para revisarlo antes de compilar.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$STATE_HOME/hyprland-desktop/backups/$STAMP"
MANIFEST="$STATE_HOME/hyprland-desktop/install-manifest.tsv"

DRY=0; YES=0; PACKAGES=1
for a in "$@"; do
    case "$a" in
        --dry-run) DRY=1 ;;
        --yes|-y) YES=1 ;;
        --no-packages) PACKAGES=0 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Opción desconocida: $a" >&2; exit 2 ;;
    esac
done

c_info=$'\e[1;34m'; c_ok=$'\e[1;32m'; c_warn=$'\e[1;33m'; c_err=$'\e[1;31m'; c_off=$'\e[0m'
info() { printf '%s::%s %s\n' "$c_info" "$c_off" "$*"; }
ok()   { printf '%s ✔%s %s\n' "$c_ok" "$c_off" "$*"; }
warn() { printf '%s !%s %s\n' "$c_warn" "$c_off" "$*"; }
die()  { printf '%s ✘%s %s\n' "$c_err" "$c_off" "$*" >&2; exit 1; }
run()  { if ((DRY)); then printf '   [dry-run] %s\n' "$*"; else "$@"; fi; }
ask()  {
    ((YES)) && return 0
    local reply
    read -r -p "$1 [s/N] " reply
    [[ "$reply" =~ ^[sSyY]$ ]]
}

# ── 1. Sistema ──────────────────────────────────────────────────────────────
[[ -f /etc/arch-release ]] || grep -qiE '^(ID|ID_LIKE)=.*arch' /etc/os-release 2>/dev/null \
    || die "Este instalador es para Arch Linux y derivadas."
command -v pacman >/dev/null || die "pacman no encontrado."
. /etc/os-release
info "Sistema: ${PRETTY_NAME:-Arch Linux}"
AUR_HELPER=""
for h in paru yay; do command -v "$h" >/dev/null && { AUR_HELPER="$h"; break; }; done
info "Helper AUR: ${AUR_HELPER:-ninguno}"
[[ "$EUID" -ne 0 ]] || die "No ejecutes el instalador como root; pedirá sudo cuando haga falta."

# ── 2. Dependencias ─────────────────────────────────────────────────────────
# paquete:descripción
DEPS=(
    "hyprland:compositor"
    "xdg-desktop-portal-hyprland:portal (capturas, compartir pantalla)"
    "hyprlock:bloqueo de pantalla"
    "hypridle:gestión de inactividad"
    "eww:barra y widgets"
    "socat:suscripción de Eww al daemon de estado"
    "jq:utilidades JSON"
    "python:daemon de estado"
    "python-gobject:iconos del lanzador"
    "networkmanager:red"
    "pipewire:audio"
    "wireplumber:audio (wpctl)"
    "pipewire-pulse:audio (pactl)"
    "playerctl:multimedia MPRIS"
    "libnotify:notify-send"
    "pacman-contrib:checkupdates"
    "awww:fondo de pantalla"
    "kitty:terminal predeterminada"
    "grim:capturas"
    "slurp:selección de región"
    "wl-clipboard:portapapeles"
    "brightnessctl:brillo"
    "ttf-jetbrains-mono-nerd:fuente con iconos"
    "ttf-cascadia-code-nerd:fuente de kitty (CaskaydiaCove)"
    "xdg-user-dirs:carpetas de usuario"
)
REPO_PKGS=(); AUR_PKGS=(); UNKNOWN=()
if ((PACKAGES)); then
    info "Comprobando dependencias…"
    for entry in "${DEPS[@]}"; do
        pkg="${entry%%:*}"; why="${entry#*:}"
        if pacman -Qq "$pkg" &>/dev/null || pacman -Qqs "^${pkg}(-git)?$" &>/dev/null; then
            ok "$pkg — $why"
        elif pacman -Si "$pkg" &>/dev/null; then
            warn "$pkg — $why (falta; repositorio)"; REPO_PKGS+=("$pkg")
        elif [[ -n "$AUR_HELPER" ]]; then
            warn "$pkg — $why (falta; AUR)"; AUR_PKGS+=("$pkg")
        else
            warn "$pkg — $why (falta y no está en los repositorios)"; UNKNOWN+=("$pkg")
        fi
    done

    if ((${#REPO_PKGS[@]})); then
        echo; info "Paquetes de repositorios a instalar: ${REPO_PKGS[*]}"
        if ask "¿Instalar con 'sudo pacman -S --needed'?"; then
            run sudo pacman -S --needed "${REPO_PKGS[@]}"
        else
            warn "Omitido. Algunos componentes no funcionarán hasta instalarlos."
        fi
    fi
    if ((${#AUR_PKGS[@]})); then
        echo; info "Paquetes AUR a construir con $AUR_HELPER: ${AUR_PKGS[*]}"
        warn "Revisa el PKGBUILD que mostrará $AUR_HELPER antes de aceptar."
        if ask "¿Construir e instalar desde AUR?"; then
            run "$AUR_HELPER" -S --needed "${AUR_PKGS[@]}"
        fi
    fi
    ((${#UNKNOWN[@]})) && warn "No se pudieron resolver: ${UNKNOWN[*]}"
fi

# ── 3. Enlaces de configuración (con respaldo) ──────────────────────────────
# destino → origen en el repositorio
LINKS=(
    "$CONFIG_HOME/hypr|$ROOT/config/hypr"
    "$CONFIG_HOME/eww|$ROOT/config/eww"
    "$BIN_DIR/desktopctl|$ROOT/bin/desktopctl"
    "$BIN_DIR/desktop-sub|$ROOT/bin/desktop-sub"
)

record() { ((DRY)) || { mkdir -p "$(dirname "$MANIFEST")"; printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$MANIFEST"; }; }

backup() {  # mueve $1 al directorio de respaldo y lo anota
    local target="$1" dest="$BACKUP_DIR${1/#$HOME/}"
    run mkdir -p "$(dirname "$dest")"
    run mv "$target" "$dest"
    record "backup" "$target" "$dest"
    ok "Respaldo: $target → $dest"
}

echo; info "Enlazando configuración…"
for pair in "${LINKS[@]}"; do
    target="${pair%%|*}"; source="${pair#*|}"
    if [[ -L "$target" && "$(readlink -f "$target")" == "$(readlink -f "$source")" ]]; then
        ok "$target ya apunta al proyecto"
        continue
    fi
    if [[ -e "$target" || -L "$target" ]]; then
        warn "$target ya existe ($(file -b "$target" | cut -c1-40))"
        if ! ask "¿Respaldarlo y reemplazarlo por el enlace al proyecto?"; then
            warn "Se deja $target sin cambios"
            continue
        fi
        backup "$target"
    fi
    run mkdir -p "$(dirname "$target")"
    run ln -s "$source" "$target"
    record "link" "$target" "$source"
    ok "$target → $source"
done

# kitty: solo se añade una línea `include`, nunca se reemplaza la configuración existente
KITTY_CONF="$CONFIG_HOME/kitty/kitty.conf"
INCLUDE="include $ROOT/config/kitty/theme.conf"
if [[ -f "$KITTY_CONF" ]] && grep -qF "$INCLUDE" "$KITTY_CONF"; then
    ok "kitty ya incluye el tema"
elif [[ -f "$KITTY_CONF" ]]; then
    if ask "¿Añadir el tema al final de $KITTY_CONF (se respalda antes)?"; then
        run mkdir -p "$BACKUP_DIR"; run cp "$KITTY_CONF" "$BACKUP_DIR/kitty.conf"
        record "backup-copy" "$KITTY_CONF" "$BACKUP_DIR/kitty.conf"
        ((DRY)) || printf '\n# hyprland-desktop\n%s\n' "$INCLUDE" >> "$KITTY_CONF"
        ok "Tema añadido a kitty"
    fi
else
    run mkdir -p "$(dirname "$KITTY_CONF")"
    ((DRY)) || printf '# Creado por hyprland-desktop\n%s\nwindow_padding_width 8\nconfirm_os_window_close 0\nenable_audio_bell no\n' "$INCLUDE" > "$KITTY_CONF"
    record "created" "$KITTY_CONF" ""
    ok "Creado $KITTY_CONF"
fi

# Neovim incluido (AstroNvim + monokai-pro, dotfiles/nvim): opcional. Reemplaza ~/.config/nvim
# (con respaldo), así que nunca se acepta solo con --yes: hay que pedirlo.
NVIM_DIR="$CONFIG_HOME/nvim"
if [[ -L "$NVIM_DIR" && "$(readlink -f "$NVIM_DIR")" == "$(readlink -f "$ROOT/dotfiles/nvim")" ]]; then
    ok "$NVIM_DIR ya apunta al proyecto"
elif ((!YES)) && ask "¿Usar la configuración de Neovim incluida (AstroNvim, dotfiles/nvim)?"; then
    [[ -e "$NVIM_DIR" || -L "$NVIM_DIR" ]] && backup "$NVIM_DIR"
    run mkdir -p "$CONFIG_HOME"
    run ln -s "$ROOT/dotfiles/nvim" "$NVIM_DIR"
    record "link" "$NVIM_DIR" "$ROOT/dotfiles/nvim"
    ok "$NVIM_DIR → $ROOT/dotfiles/nvim (los plugins se instalan al abrir nvim)"
fi

# fish incluido (dotfiles/fish + starship + fastfetch): opcional y, como Neovim, nunca solo con --yes.
# Los valores privados (MINIMAX_API_KEY…) van en ~/.config/fish/conf.d/local.fish, que no está en git.
FISH_DIR="$CONFIG_HOME/fish"
if [[ -L "$FISH_DIR" && "$(readlink -f "$FISH_DIR")" == "$(readlink -f "$ROOT/dotfiles/fish")" ]]; then
    ok "$FISH_DIR ya apunta al proyecto"
elif ((!YES)) && ask "¿Usar la configuración de fish incluida (dotfiles/fish, starship, fastfetch)?"; then
    SHELL_PKGS=()
    for pkg in fish starship eza bat ugrep fastfetch expac; do
        pacman -Qq "$pkg" &>/dev/null || SHELL_PKGS+=("$pkg")
    done
    if ((${#SHELL_PKGS[@]})) && ask "¿Instalar ${SHELL_PKGS[*]} con 'sudo pacman -S --needed'?"; then
        run sudo pacman -S --needed "${SHELL_PKGS[@]}"
    fi
    # el local.fish de una configuración anterior se conserva
    OLD_LOCAL="$FISH_DIR/conf.d/local.fish"
    [[ -f "$OLD_LOCAL" && ! -L "$FISH_DIR" ]] && run cp "$OLD_LOCAL" "$ROOT/dotfiles/fish/conf.d/local.fish"
    for pair in "$FISH_DIR|$ROOT/dotfiles/fish" \
                "$CONFIG_HOME/starship.toml|$ROOT/dotfiles/starship.toml" \
                "$CONFIG_HOME/fastfetch|$ROOT/dotfiles/fastfetch"; do
        target="${pair%%|*}"; source="${pair#*|}"
        [[ -L "$target" && "$(readlink -f "$target")" == "$(readlink -f "$source")" ]] && continue
        [[ -e "$target" || -L "$target" ]] && backup "$target"
        run ln -s "$source" "$target"
        record "link" "$target" "$source"
        ok "$target → $source"
    done
    if [[ "$(getent passwd "$USER" | cut -d: -f7)" != */fish ]] && command -v fish >/dev/null \
            && ask "¿Usar fish como shell predeterminada (chsh pedirá tu contraseña)?"; then
        run chsh -s "$(command -v fish)"
    fi
fi

# Neovim: si usa monokai-pro, se añade un plugin (enlace) que sincroniza su paleta con el tema
NVIM_SPEC="$CONFIG_HOME/nvim/lua/plugins/hyprland-desktop.lua"
if [[ -L "$NVIM_SPEC" ]]; then
    ok "Neovim ya sincroniza el tema"
elif [[ -d "$CONFIG_HOME/nvim/lua/plugins" ]] && grep -rqs "monokai-pro" "$CONFIG_HOME/nvim"; then
    if ask "¿Sincronizar el tema de Neovim (monokai-pro) con el tema global?"; then
        run ln -s "$ROOT/config/nvim/hyprland-desktop.lua" "$NVIM_SPEC"
        record "link" "$NVIM_SPEC" "$ROOT/config/nvim/hyprland-desktop.lua"
        ok "Neovim seguirá el tema global (desactivable con nvim.sync_theme)"
    fi
fi

# KWallet como servicio de contraseñas (igual que en Plasma). Sin esto, fuera de Plasma D-Bus arranca
# gnome-keyring (vacío) y Brave, Teams, gh, etc. parecen haber perdido sus credenciales.
if [[ -f /usr/bin/ksecretd ]]; then
    SECRETS_SVC="$DATA_HOME/dbus-1/services/org.freedesktop.secrets.service"
    if [[ ! -e "$SECRETS_SVC" ]]; then
        run mkdir -p "$(dirname "$SECRETS_SVC")"
        ((DRY)) || printf '# hyprland-desktop: contraseñas en KWallet (como en Plasma)\n[D-BUS Service]\nName=org.freedesktop.secrets\nExec=/usr/bin/ksecretd\n' > "$SECRETS_SVC"
        record "created" "$SECRETS_SVC" ""
        ok "Servicio de contraseñas: KWallet"
    fi
    # pam_gnome_keyring (GDM y SDDM) arranca gnome-keyring con el componente secrets y se queda con
    # org.freedesktop.secrets antes que ksecretd: se deja solo con pkcs11.
    KEYRING_DROPIN="$CONFIG_HOME/systemd/user/gnome-keyring-daemon.service.d/hyprland-desktop.conf"
    if [[ -f /usr/lib/systemd/user/gnome-keyring-daemon.service && ! -e "$KEYRING_DROPIN" ]]; then
        run mkdir -p "$(dirname "$KEYRING_DROPIN")"
        ((DRY)) || printf '# hyprland-desktop: las contraseñas las da KWallet (ksecretd); gnome-keyring sin el componente secrets\n[Service]\nExecStart=\nExecStart=/usr/bin/gnome-keyring-daemon --foreground --components=pkcs11 --control-directory=%%t/keyring\n' > "$KEYRING_DROPIN"
        record "created" "$KEYRING_DROPIN" ""
        run systemctl --user daemon-reload
        ok "gnome-keyring ya no ofrece el servicio de contraseñas"
    fi
    # GDM no pasa la contraseña de inicio a KWallet (su PAM no incluye pam_kwallet5; el de SDDM sí):
    # con GDM el monedero queda cerrado y pide su contraseña. Se ofrece cambiar a SDDM.
    if [[ "$(readlink -f /etc/systemd/system/display-manager.service)" == */gdm.service ]]; then
        if [[ -f /usr/lib/systemd/system/sddm.service ]] \
                && ask "¿Cambiar el gestor de inicio de GDM a SDDM para que KWallet se abra al iniciar sesión (sudo)?"; then
            run sudo systemctl disable gdm.service
            run sudo systemctl enable sddm.service
            ok "SDDM será el gestor de inicio a partir del próximo arranque"
        else
            warn "Con GDM, KWallet pedirá su contraseña en cada sesión (instala sddm para evitarlo)"
        fi
    fi
    # Navegadores Chromium/Electron no detectan KWallet fuera de Plasma: se fuerza
    if [[ -x /usr/bin/brave ]] && ! grep -qs 'password-store' "$CONFIG_HOME/brave-flags.conf"; then
        ((DRY)) || echo '--password-store=kwallet6' >> "$CONFIG_HOME/brave-flags.conf"
        ok "Brave usará KWallet ($CONFIG_HOME/brave-flags.conf)"
    fi
    if [[ -x /usr/bin/teams-for-linux && ! -e "$CONFIG_HOME/teams-for-linux/config.json" ]]; then
        run mkdir -p "$CONFIG_HOME/teams-for-linux"
        ((DRY)) || printf '{\n  "performance": {\n    "electronCLIFlags": [["password-store", "kwallet6"]]\n  }\n}\n' > "$CONFIG_HOME/teams-for-linux/config.json"
        record "created" "$CONFIG_HOME/teams-for-linux/config.json" ""
        ok "Teams usará KWallet"
    fi
fi

# Tema de SDDM estilo GDM (config/sddm/gnome-gdm). SDDM solo lee temas de /usr/share/sddm/themes:
# se copia allí con sudo (volver a ejecutar el instalador lo actualiza).
SDDM_THEME=/usr/share/sddm/themes/gnome-gdm
if [[ -f /usr/lib/systemd/system/sddm.service ]]; then
    if [[ -d "$SDDM_THEME" ]] && diff -rq "$ROOT/config/sddm/gnome-gdm" "$SDDM_THEME" >/dev/null; then
        ok "Tema de SDDM al día"
    elif ask "¿$( [[ -d "$SDDM_THEME" ]] && echo Actualizar || echo Instalar ) el tema de SDDM estilo GDM en $SDDM_THEME (sudo)?"; then
        [[ -d "$SDDM_THEME" ]] || record "sudo-created" "$SDDM_THEME" ""
        run sudo rm -rf "$SDDM_THEME"
        run sudo cp -r "$ROOT/config/sddm/gnome-gdm" "$SDDM_THEME"
        ok "Tema de SDDM instalado (prueba: sddm-greeter-qt6 --test-mode --theme $SDDM_THEME)"
    fi
    # Tema activo: gana el último Current= (sddm.conf.d por orden alfabético y luego sddm.conf)
    current="$(cat /etc/sddm.conf.d/*.conf /etc/sddm.conf 2>/dev/null | sed -n 's/^Current=//p' | tail -1)"
    if [[ -d "$SDDM_THEME" && "$current" != "gnome-gdm" ]] \
            && ask "¿Activar el tema gnome-gdm en SDDM (ahora: ${current:-predeterminado}; sudo)?"; then
        SDDM_CONF=/etc/sddm.conf.d/zz-hyprland-desktop.conf  # «zz»: se lee después de kde_settings.conf
        if ((DRY)); then echo "   [dry-run] escribir $SDDM_CONF"; else
            printf '# hyprland-desktop: tema de la pantalla de inicio\n[Theme]\nCurrent=gnome-gdm\n' | sudo tee "$SDDM_CONF" >/dev/null
        fi
        record "sudo-created" "$SDDM_CONF" ""
        ok "SDDM usará gnome-gdm"
    fi
fi

# Configuración de usuario editable (nunca se sobrescribe)
USER_SETTINGS="$CONFIG_HOME/hyprland-desktop/settings.json"
if [[ -f "$USER_SETTINGS" ]]; then
    ok "Se conserva $USER_SETTINGS"
else
    run mkdir -p "$(dirname "$USER_SETTINGS")"
    run cp "$ROOT/settings.json" "$USER_SETTINGS"
    ok "Creado $USER_SETTINGS (edítalo y ejecuta: desktopctl apply)"
fi

# ── 4. Generación y validación ──────────────────────────────────────────────
echo; info "Generando archivos derivados de settings.json y del tema…"
run "$ROOT/bin/desktopctl" apply

echo; info "Validando…"
((DRY)) || "$ROOT/bin/desktopctl" doctor || warn "Faltan dependencias obligatorias (ver arriba)."
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR no está en tu PATH; añádelo en tu shell para usar 'desktopctl'." ;; esac

echo
ok "Instalación terminada."
echo "   · Cierra sesión y elige «Hyprland» en el gestor de inicio de sesión."
echo "   · Respaldos: $STATE_HOME/hyprland-desktop/backups/   · Restaurar: ./uninstall.sh"
