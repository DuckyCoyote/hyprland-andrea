#!/bin/sh
# Pasa el texto del buscador del lanzador a launcher_query sin carreras.
# Uso (onchange del input): launcher-query.sh '{}' ${EWW_CMD}
# Eww lanza un proceso por pulsación y, al escribir rápido, varios `eww update` corren a la vez y
# llegan desordenados (la búsqueda se queda con un texto viejo). Cada llamada guarda su texto y,
# por turnos (flock), publica el ÚLTIMO texto guardado, así el valor final es siempre el actual.
q="$1"; shift
dir="${XDG_RUNTIME_DIR:-/tmp/hyprland-desktop-$(id -u)}/hyprland-desktop"
mkdir -p "$dir"
printf '%s' "$q" > "$dir/launcher-query.$$" && mv -f "$dir/launcher-query.$$" "$dir/launcher-query"
exec 9>"$dir/launcher-query.lock"
flock 9
"$@" update launcher_query="$(cat "$dir/launcher-query")"
