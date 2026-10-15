-- Apariencia de ventanas: todo sale del tema generado (generated/theme.lua)

local T = require("modules.ctx").T

hl.config({
    general = {
        gaps_in = T.gaps_in,
        gaps_out = T.gaps_out,
        border_size = T.border_size,
        col = {
            active_border = T.active_border,
            inactive_border = T.inactive_border,
        },
        resize_on_border = true,
        allow_tearing = false,
        layout = "master", -- como el diseño «tile» de AwesomeWM; SUPER+Espacio cambia de layout
    },

    decoration = {
        rounding = T.rounding,
        rounding_power = 2,
        active_opacity = T.active_opacity,
        inactive_opacity = T.inactive_opacity,
        shadow = {
            enabled = T.shadows,
            range = 8,
            render_power = 3,
            color = T.shadow,
        },
        blur = { enabled = false }, -- sin efectos innecesarios
    },

    animations = { enabled = T.animations },

    master = { new_status = "slave", mfact = 0.55 },
    dwindle = { preserve_split = true },

    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        background_color = T.background,
        focus_on_activate = true,
        key_press_enables_dpms = true,
        mouse_move_enables_dpms = true,
    },

    ecosystem = { no_donation_nag = true, no_update_news = true },
})

-- Animaciones cortas y suaves
hl.curve("smooth", { type = "bezier", points = { { 0.25, 1 }, { 0.5, 1 } } })
hl.curve("linear", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.animation({ leaf = "global",     enabled = true, speed = 6,   bezier = "smooth" })
hl.animation({ leaf = "windowsIn",  enabled = true, speed = 3.5, bezier = "smooth", style = "popin 90%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 2.5, bezier = "linear", style = "popin 90%" })
hl.animation({ leaf = "border",     enabled = true, speed = 4,   bezier = "smooth" })
hl.animation({ leaf = "fade",       enabled = true, speed = 3,   bezier = "smooth" })
hl.animation({ leaf = "layersIn",   enabled = true, speed = 2.5, bezier = "smooth", style = "slide top" })
hl.animation({ leaf = "layersOut",  enabled = true, speed = 2,   bezier = "linear", style = "fade" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3,   bezier = "smooth", style = "slide" })
