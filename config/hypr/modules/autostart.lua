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
    -- Portales y servicios D-Bus/systemd necesitan las variables de la sesión. Las de Qt, cursor y
    -- menú también: las apps que se abren vía D-Bus/systemd (p. ej. Gwenview desde Dolphin) no
    -- heredan el entorno de Hyprland y arrancaban con el tema claro.
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP "
        .. "XDG_SESSION_TYPE XDG_SESSION_DESKTOP HYPRLAND_INSTANCE_SIGNATURE DISPLAY "
        .. "QT_QPA_PLATFORM QT_QPA_PLATFORMTHEME QT_WAYLAND_DISABLE_WINDOWDECORATION XDG_MENU_PREFIX "
        .. "XCURSOR_THEME XCURSOR_SIZE HYPRCURSOR_THEME HYPRCURSOR_SIZE GDK_BACKEND")

    -- KWallet como en Plasma: pam_kwallet_init conecta ksecretd (que recibió la contraseña al
    -- iniciar sesión) al bus. Sin esto D-Bus arrancaba gnome-keyring, vacío, y Brave, Teams o gh
    -- parecían haber perdido sus credenciales. Ver docs/decisions.md.
    if exists("/usr/lib/pam_kwallet_init") then
        hl.exec_cmd("/usr/lib/pam_kwallet_init")
    end

    hl.exec_cmd(ctx.ctl("start"))
    hl.exec_cmd("sh -c 'command -v awww-daemon >/dev/null && awww-daemon & sleep 1; " .. ctx.ctl("wallpaper") .. "'")
    hl.exec_cmd("hypridle")

    -- Iluminación RGB: perfil «blue» de OpenRGB (azul puro en RAM y placa). Sin servidor:
    -- el cliente detecta los dispositivos (~10 s), aplica el perfil y termina.
    if exists(os.getenv("HOME") .. "/.config/OpenRGB/profiles/blue.json") then
        hl.exec_cmd("openrgb --noautoconnect --profile blue")
    end

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
