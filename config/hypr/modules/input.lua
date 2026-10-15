-- Teclado y ratón (settings.json → keyboard / input)

local S = require("modules.ctx").S
local kb, inp = S.keyboard or {}, S.input or {}

hl.config({
    input = {
        kb_layout = kb.layout or "us",
        kb_variant = kb.variant or "",
        kb_options = kb.options or "",
        numlock_by_default = true,
        follow_mouse = 1,
        sensitivity = inp.sensitivity or 0,
        natural_scroll = inp.natural_scroll or false,
        touchpad = { natural_scroll = inp.natural_scroll or false, tap_to_click = true },
    },
})
