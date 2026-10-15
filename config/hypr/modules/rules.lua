-- Reglas de ventanas y capas

local T = require("modules.ctx").T

hl.window_rule({ name = "suppress-maximize", match = { class = ".*" }, suppress_event = "maximize" })

-- Ventanas auxiliares flotantes y centradas
hl.window_rule({
    name = "float-dialogs",
    match = { class = "^(hd-float|hd\\.float|pavucontrol|org\\.pulseaudio\\.pavucontrol|nm-connection-editor|blueman-manager|org\\.kde\\.polkit-kde-authentication-agent-1|xdg-desktop-portal-gtk|org\\.kde\\.kdeconnect.*)$" },
    float = true,
    center = true,
    size = "900 600",
})
hl.window_rule({
    name = "float-file-dialogs",
    match = { title = "^(Abrir|Guardar|Open|Save|Seleccionar|Select).*" },
    float = true,
    center = true,
})

-- Arrastres de XWayland (del ejemplo oficial)
hl.window_rule({
    name = "fix-xwayland-drags",
    match = { class = "^$", title = "^$", xwayland = true, float = true, fullscreen = false, pin = false },
    no_focus = true,
})

-- Capas de Eww: sin desenfoque; la capa de cierre de popups sin animación
hl.layer_rule({ name = "eww-bar", match = { namespace = "^hd-bar$" }, blur = false })
hl.layer_rule({ name = "eww-popup", match = { namespace = "^hd-popup$" }, blur = false,
                animation = T.animations and "slide top" or nil, no_anim = not T.animations })
hl.layer_rule({ name = "eww-closer", match = { namespace = "^hd-closer$" }, no_anim = true })
