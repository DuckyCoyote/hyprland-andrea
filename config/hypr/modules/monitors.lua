-- Monitores declarados en settings.json → monitors (detectados con el hardware real).
-- Cualquier monitor no declarado se configura automáticamente a la derecha.

local ctx = require("modules.ctx")

for _, m in ipairs(ctx.S.monitors) do
    hl.monitor({
        output   = m.name,
        mode     = m.mode or "preferred",
        position = m.position or "auto",
        scale    = tostring(m.scale or 1),
    })
end

hl.monitor({ output = "", mode = "preferred", position = "auto-right", scale = "auto" })

-- El cursor empieza en el monitor principal
if ctx.order[1] then
    hl.config({ cursor = { default_monitor = ctx.order[1] } })
end
