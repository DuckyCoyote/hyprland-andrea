-- ─────────────────────────────────────────────────────────────────────────────
-- Atajos de teclado. Basados en la configuración de AwesomeWM (awesome-minimal:
-- keys/globalkeys.lua y keys/clientkeys.lua) adaptados a Hyprland.
--
-- Cada atajo se declara UNA vez en la tabla `binds` con su descripción; de aquí salen
-- tanto los binds reales como la chuleta del panel Configuración → Atajos
-- ($XDG_RUNTIME_DIR/hyprland-desktop/keybinds.json). Ver docs/keybindings.md.
-- ─────────────────────────────────────────────────────────────────────────────

local ctx = require("modules.ctx")
local S = ctx.S
local apps = S.apps or {}
local dsp = hl.dsp
local M = "SUPER"

local function exec(cmd) return dsp.exec_cmd(cmd) end
local function ctl(args) return dsp.exec_cmd(ctx.ctl(args)) end

-- Disposiciones disponibles para SUPER+Espacio (equivalente a awful.layout.inc)
local layouts = { "master", "dwindle", "scrolling" }
local function cycle_layout(step)
    return function()
        local current = hl.get_config("general.layout")
        local i = 1
        for k, v in ipairs(layouts) do if v == current then i = k end end
        local nxt = layouts[((i - 1 + step) % #layouts) + 1]
        hl.config({ general = { layout = nxt } })
        hl.notification.create({ text = "Disposición: " .. nxt, timeout = 1500 })
    end
end

-- awful.tag.incmwfact: en master ajusta la proporción; en otros layouts redimensiona la ventana
local function grow(delta)
    return function()
        if hl.get_config("general.layout") == "master" then
            hl.dispatch(dsp.layout(string.format("mfact %+.2f", delta)))
        else
            hl.dispatch(dsp.window.resize({ x = delta * 800, y = 0, relative = true }))
        end
    end
end

-- awful.tag.viewnext/viewprev: recorre los espacios del monitor actual (incluidos vacíos)
local function cycle_workspace(step)
    return function()
        local per = S.workspaces_per_monitor or 6
        local ws = hl.get_active_workspace()
        local slot = ws and ((ws.id - 1) % ctx.STRIDE) + 1 or 1
        local nxt = ((slot - 1 + step) % per) + 1
        hl.dispatch(dsp.focus({ workspace = ctx.slot_id(nxt) }))
    end
end

local screenshot = [[sh -c 'd="$(xdg-user-dir PICTURES 2>/dev/null || echo "$HOME")/Capturas"; mkdir -p "$d"; f="$d/$(date +%Y-%m-%d_%H-%M-%S).png"; ]]

-- { teclas, descripción, acción, opciones }
-- Las cadenas sueltas abren una sección (agrupan los atajos en la chuleta flotante, Super+S).
local binds = {
    "Aplicaciones",
    { M .. " + Return",        "Abrir terminal",                         exec(apps.terminal or "kitty") },
    { M .. " + B",             "Abrir navegador",                        exec(apps.browser or "firefox") },
    { M .. " + E",             "Abrir explorador de archivos",           exec(apps.file_manager or "dolphin") },
    { M .. " + R",             "Lanzador de aplicaciones",               ctl("popup toggle launcher focused") },
    { M .. " + P",             "Lanzador de aplicaciones (menubar)",     ctl("popup toggle launcher focused") },
    { M .. " + SHIFT + D",     "Lanzador de aplicaciones (rofi combi)",  ctl("popup toggle launcher focused") },

    "Paneles del entorno",
    { M .. " + W",             "Configuración (menú principal)",         ctl("popup toggle settings focused system") },
    { M .. " + S",             "Chuleta de atajos (flotante)",           ctl("popup toggle keymap focused") },
    { M .. " + SHIFT + T",     "Selector de temas y fuentes",            ctl("popup toggle settings focused appearance") },
    { M .. " + SHIFT + Q",     "Menú de energía / cerrar sesión",        ctl("popup toggle power focused") },
    { M .. " + ALT + N",       "Panel de red",                           ctl("popup toggle network focused") },
    { M .. " + ALT + A",       "Panel de audio",                         ctl("popup toggle audio focused") },
    { M .. " + ALT + M",       "Panel multimedia",                       ctl("popup toggle media focused") },
    { M .. " + ALT + U",       "Actualizaciones",                        ctl("popup toggle updates focused") },
    { M .. " + ALT + O",       "Bandeja de notificaciones",              ctl("popup toggle notifications focused") },
    { M .. " + ALT + D",       "No molestar (activar/desactivar)",       ctl("notifications dnd toggle") },
    { M .. " + CTRL + R",      "Recargar Hyprland y Eww",                exec("hyprctl reload && " .. ctx.ctl("apply")) },
    { M .. " + ALT + L",       "Bloquear pantalla",                      exec("loginctl lock-session") },

    "Espacios de trabajo",
    { M .. " + Left",          "Espacio anterior del monitor",           cycle_workspace(-1) },
    { M .. " + Right",         "Espacio siguiente del monitor",          cycle_workspace(1) },
    { M .. " + Escape",        "Volver al espacio anterior",             dsp.focus({ workspace = "previous" }) },
    { M .. " + mouse_down",    "Espacio siguiente (rueda)",              cycle_workspace(1) },
    { M .. " + mouse_up",      "Espacio anterior (rueda)",               cycle_workspace(-1) },

    "Foco y orden de ventanas",
    { M .. " + J",             "Enfocar ventana siguiente",              dsp.window.cycle_next({ next = true }) },
    { M .. " + K",             "Enfocar ventana anterior",               dsp.window.cycle_next({ next = false }) },
    { M .. " + SHIFT + J",     "Intercambiar con la siguiente",          dsp.window.swap({ next = true }) },
    { M .. " + SHIFT + K",     "Intercambiar con la anterior",           dsp.window.swap({ prev = true }) },
    { M .. " + CTRL + J",      "Enfocar monitor siguiente",              dsp.focus({ monitor = "+1" }) },
    { M .. " + CTRL + K",      "Enfocar monitor anterior",               dsp.focus({ monitor = "-1" }) },
    { M .. " + U",             "Ir a la ventana urgente",                dsp.focus({ urgent_or_last = true }) },
    { M .. " + Tab",           "Ventana enfocada anteriormente",         dsp.focus({ last = true }) },
    { M .. " + ALT + left",    "Enfocar a la izquierda",                 dsp.focus({ direction = "left" }) },
    { M .. " + ALT + right",   "Enfocar a la derecha",                   dsp.focus({ direction = "right" }) },
    { M .. " + ALT + up",      "Enfocar arriba",                         dsp.focus({ direction = "up" }) },
    { M .. " + ALT + down",    "Enfocar abajo",                          dsp.focus({ direction = "down" }) },

    "Disposición",
    { M .. " + L",             "Ampliar área maestra",                   grow(0.05),  { repeating = true } },
    { M .. " + H",             "Reducir área maestra",                   grow(-0.05), { repeating = true } },
    { M .. " + SHIFT + H",     "Añadir ventana maestra",                 dsp.layout("addmaster") },
    { M .. " + SHIFT + L",     "Quitar ventana maestra",                 dsp.layout("removemaster") },
    { M .. " + CTRL + H",      "Orientación siguiente (columnas)",       dsp.layout("orientationnext") },
    { M .. " + CTRL + L",      "Orientación anterior (columnas)",        dsp.layout("orientationprev") },
    { M .. " + space",         "Disposición siguiente",                  cycle_layout(1) },
    { M .. " + SHIFT + space", "Disposición anterior",                   cycle_layout(-1) },

    "Ventana",
    { M .. " + F",             "Pantalla completa",                      dsp.window.fullscreen({ mode = "fullscreen" }) },
    { M .. " + M",             "Maximizar / restaurar",                  dsp.window.fullscreen({ mode = "maximized" }) },
    { M .. " + SHIFT + C",     "Cerrar ventana",                         dsp.window.close() },
    { M .. " + CTRL + space",  "Alternar flotante",                      dsp.window.float({ action = "toggle" }) },
    { M .. " + CTRL + Return", "Intercambiar con la maestra",            dsp.layout("swapwithmaster") },
    { M .. " + O",             "Mover ventana al otro monitor",          dsp.window.move({ monitor = "+1" }) },
    { M .. " + T",             "Fijar encima (pin, flotantes)",          dsp.window.pin() },
    { M .. " + N",             "Minimizar",                              dsp.window.move({ workspace = "special:minimized", follow = false }) },
    { M .. " + CTRL + N",      "Mostrar minimizadas",                    dsp.workspace.toggle_special("minimized") },
    { M .. " + mouse:272",     "Mover ventana con el ratón",             dsp.window.drag(),   { mouse = true } },
    { M .. " + mouse:273",     "Redimensionar con el ratón",             dsp.window.resize(), { mouse = true } },

    "Capturas",
    { M .. " + SHIFT + S",     "Captura de una región",
        exec(screenshot .. [[grim -g "$(slurp)" "$f" && wl-copy < "$f" && notify-send -i "$f" "Captura guardada" "$f"']]) },
    { "Print",                 "Captura de pantalla completa",
        exec(screenshot .. [[grim "$f" && wl-copy < "$f" && notify-send -i "$f" "Captura guardada" "$f"']]) },

    "Multimedia", -- también funcionan con la pantalla bloqueada
    { "XF86AudioRaiseVolume",  "Subir volumen",   exec("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true } },
    { "XF86AudioLowerVolume",  "Bajar volumen",   exec("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),      { locked = true, repeating = true } },
    { "XF86AudioMute",         "Silenciar",       exec("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),     { locked = true } },
    { "XF86AudioMicMute",      "Silenciar micrófono", exec("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true } },
    { "XF86MonBrightnessUp",   "Subir brillo",    exec("brightnessctl -e4 -n2 set 5%+"), { locked = true, repeating = true } },
    { "XF86MonBrightnessDown", "Bajar brillo",    exec("brightnessctl -e4 -n2 set 5%-"), { locked = true, repeating = true } },
    { "XF86AudioPlay",         "Reproducir/pausar", ctl("media toggle"),   { locked = true } },
    { "XF86AudioPause",        "Reproducir/pausar", ctl("media toggle"),   { locked = true } },
    { "XF86AudioNext",         "Pista siguiente",   ctl("media next"),     { locked = true } },
    { "XF86AudioPrev",         "Pista anterior",    ctl("media previous"), { locked = true } },
}

-- Espacios 1..9 del monitor actual
table.insert(binds, "Espacios de trabajo")
for slot = 1, 9 do
    local key = tostring(slot)
    table.insert(binds, { M .. " + " .. key, "Ir al espacio " .. key,
        function() hl.dispatch(dsp.focus({ workspace = ctx.slot_id(slot) })) end })
    table.insert(binds, { M .. " + SHIFT + " .. key, "Mover ventana al espacio " .. key,
        function() hl.dispatch(dsp.window.move({ workspace = ctx.slot_id(slot) })) end })
    table.insert(binds, { M .. " + CTRL + " .. key, "Enviar ventana al espacio " .. key .. " (sin seguirla)",
        function() hl.dispatch(dsp.window.move({ workspace = ctx.slot_id(slot), follow = false })) end })
end

-- Registro de binds + chuleta para el panel de atajos
local function json_string(s)
    return '"' .. tostring(s):gsub('[%c"\\]', function(c) return string.format("\\u%04x", c:byte()) end) .. '"'
end

local cheat, section = {}, ""
local function add_cheat(keys, desc)
    table.insert(cheat, "{\"keys\":" .. json_string(keys) .. ",\"desc\":" .. json_string(desc)
        .. ",\"section\":" .. json_string(section) .. "}")
end
for _, b in ipairs(binds) do
    if type(b) == "string" then
        section = b
    else
        hl.bind(b[1], b[3], b[4])
        if not b[1]:find("mouse") and not b[1]:find("XF86") and not b[1]:match(" %+ %d$") then
            add_cheat((b[1]:gsub("SUPER", "Super")), b[2])
        end
    end
end
section = "Espacios de trabajo"
add_cheat("Super + 1…9", "Ir al espacio N del monitor actual")
add_cheat("Super + SHIFT + 1…9", "Mover la ventana al espacio N")
add_cheat("Super + CTRL + 1…9", "Enviar la ventana al espacio N (sin seguirla)")
section = "Multimedia"
add_cheat("Teclas multimedia", "Volumen, micrófono, brillo y reproductor")

-- Modo «popup»: mientras hay un panel abierto, Escape lo cierra (lo activa desktopd).
hl.define_submap("hd-popup", function()
    hl.bind("Escape", function()
        hl.exec_cmd(ctx.ctl("popup close"))
        hl.dispatch(dsp.submap("reset"))
    end)
end)

local runtime = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/hyprland-desktop"
os.execute("mkdir -p '" .. runtime .. "'")
local f = io.open(runtime .. "/keybinds.json", "w")
if f then
    f:write("[" .. table.concat(cheat, ",") .. "]\n")
    f:close()
end
