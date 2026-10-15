-- Variables de entorno de la sesión Wayland

local T = require("modules.ctx").T

local function exists(path)
    local f = io.open(path, "r")
    if f then f:close() end
    return f ~= nil
end

-- Cursor: el elegido en Configuración → Apariencia (generated/theme.lua)
local cursor_size = tostring(T.cursor_size or 24)
hl.env("XCURSOR_SIZE", cursor_size)
hl.env("HYPRCURSOR_SIZE", cursor_size)
if T.cursor_theme and T.cursor_theme ~= "" then
    hl.env("XCURSOR_THEME", T.cursor_theme)
    hl.env("HYPRCURSOR_THEME", T.cursor_theme)
    hl.on("hyprland.start", function()
        hl.exec_cmd(string.format("hyprctl setcursor '%s' %s", T.cursor_theme, cursor_size))
    end)
end
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
-- Apps KDE/Qt (Dolphin…): con plasma-integration usan el esquema de colores, iconos y estilo de
-- ~/.config/kdeglobals (el mismo que Plasma); sin esto arrancan con el tema claro por defecto.
if exists("/usr/lib/qt6/plugins/platformthemes/KDEPlasmaPlatformTheme6.so") then
    hl.env("QT_QPA_PLATFORMTHEME", "kde")
elseif exists("/usr/bin/qt6ct") then
    hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
end
-- Menú de aplicaciones de KDE: sin él, «Abrir con» de Dolphin sale vacío fuera de Plasma
if exists("/etc/xdg/menus/plasma-applications.menu") then
    hl.env("XDG_MENU_PREFIX", "plasma-")
end
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("SDL_VIDEODRIVER", "wayland,x11")
hl.env("CLUTTER_BACKEND", "wayland")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
hl.env("MOZ_ENABLE_WAYLAND", "1")

-- NVIDIA: se detecta en tiempo de ejecución en lugar de suponerlo.
-- Probado con nvidia-open 615.x (modeset/fbdev activos por defecto). No se fuerza
-- GBM_BACKEND (provoca cierres en Firefox con drivers recientes).
local nv = io.open("/proc/driver/nvidia/version", "r")
if nv then
    nv:close()
    hl.env("LIBVA_DRIVER_NAME", "nvidia")
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    hl.env("NVD_BACKEND", "direct")
    -- El cursor por hardware de NVIDIA retiene los page-flips y las animaciones (p. ej. el
    -- deslizamiento al cambiar de espacio) se quedan congeladas hasta que algo redibuja.
    hl.config({ cursor = { no_hardware_cursors = true } })
end
