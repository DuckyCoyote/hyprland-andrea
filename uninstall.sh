#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# hyprland-desktop · desinstalador
#
# Quita los enlaces creados por install.sh y restaura los respaldos registrados en
# ~/.local/state/hyprland-desktop/install-manifest.tsv. No desinstala paquetes ni toca
# ~/.config/hyprland-desktop (tu settings.json) salvo que lo pidas.
#
#   ./uninstall.sh [--dry-run] [--yes]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
MANIFEST="$STATE_HOME/hyprland-desktop/install-manifest.tsv"
ROOT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DRY=0; YES=0
for a in "$@"; do
    case "$a" in --dry-run) DRY=1 ;; --yes|-y) YES=1 ;; *) echo "Opción desconocida: $a" >&2; exit 2 ;; esac
done
run() { if ((DRY)); then printf '   [dry-run] %s\n' "$*"; else "$@"; fi; }
ask() { ((YES)) && return 0; local r; read -r -p "$1 [s/N] " r; [[ "$r" =~ ^[sSyY]$ ]]; }

[[ -f "$MANIFEST" ]] || { echo "No hay manifiesto de instalación ($MANIFEST). Nada que hacer."; exit 0; }

"$ROOT/bin/desktopctl" stop 2>/dev/null || true

# 1) quitar enlaces que siguen apuntando al proyecto
while IFS=$'\t' read -r kind target source; do
    [[ "$kind" == "link" ]] || continue
    if [[ -L "$target" && "$(readlink -f "$target")" == "$(readlink -f "$source")" ]]; then
        run rm "$target"; echo " ✔ Enlace eliminado: $target"
    fi
done < "$MANIFEST"

# 2) restaurar respaldos (el más reciente de cada ruta)
tac "$MANIFEST" | while IFS=$'\t' read -r kind target dest; do
    case "$kind" in
        backup)
            if [[ ! -e "$target" && -e "$dest" ]]; then
                run mkdir -p "$(dirname "$target")"; run mv "$dest" "$target"; echo " ✔ Restaurado: $target"
            fi ;;
        backup-copy)
            if [[ -e "$dest" ]] && ask "¿Restaurar $target desde el respaldo?"; then
                run cp "$dest" "$target"; echo " ✔ Restaurado: $target"
            fi ;;
        created)
            if [[ -f "$target" ]] && ask "¿Eliminar $target (creado por el instalador)?"; then
                run rm "$target"; echo " ✔ Eliminado: $target"
            fi ;;
        sudo-created)  # tema de SDDM y su configuración, fuera de $HOME
            if [[ -e "$target" ]] && ask "¿Eliminar $target (creado por el instalador; sudo)?"; then
                run sudo rm -r "$target"; echo " ✔ Eliminado: $target"
            fi ;;
    esac
done

if [[ -d "$CONFIG_HOME/hyprland-desktop" ]] && ask "¿Eliminar también tu configuración ($CONFIG_HOME/hyprland-desktop)?"; then
    run rm -r "$CONFIG_HOME/hyprland-desktop"
fi
((DRY)) || mv "$MANIFEST" "$MANIFEST.uninstalled-$(date +%Y%m%d-%H%M%S)"
echo "Listo. Los paquetes instalados no se han eliminado."
