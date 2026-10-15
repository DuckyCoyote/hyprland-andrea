-- Programas al iniciar la sesión.
-- La barra y los widgets NO se lanzan aquí directamente: `desktopctl start` arranca el
-- daemon de estado, que abre Eww y una barra por monitor (independiente del compositor).

local ctx = require("modules.ctx")

local function exists(path)
    local f = io.open(path, "r")
    if f then f:close() return true end
    return false
end

hl.on("hyprland.start", function()
    -- Portales y servicios D-Bus/systemd necesitan las variables de la sesión
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE HYPRLAND_INSTANCE_SIGNATURE DISPLAY")

    hl.exec_cmd(ctx.ctl("start"))
    hl.exec_cmd("sh -c 'command -v awww-daemon >/dev/null && awww-daemon & sleep 1; " .. ctx.ctl("wallpaper") .. "'")
    hl.exec_cmd("hypridle")

    -- Agente de autenticación (polkit): el que haya instalado
    if exists("/usr/lib/hyprpolkitagent/hyprpolkitagent") then
        hl.exec_cmd("/usr/lib/hyprpolkitagent/hyprpolkitagent")
    elseif exists("/usr/lib/polkit-kde-authentication-agent-1") then
        hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")
    end
    -- Las notificaciones las sirve el propio desktopd (org.freedesktop.Notifications)
end)

hl.on("hyprland.shutdown", function()
    hl.exec_cmd(ctx.ctl("stop"))
end)
