-- Espacios de trabajo por monitor (como las «tags» por pantalla de AwesomeWM):
--   monitor principal -> 1..N, segundo monitor -> 11..N+10, etc.
-- La barra de cada monitor muestra solo sus espacios.

local ctx = require("modules.ctx")
local per = ctx.S.workspaces_per_monitor or 6

for idx, name in ipairs(ctx.order) do
    local base = (idx - 1) * ctx.STRIDE
    for slot = 1, math.max(per, 9) do
        hl.workspace_rule({ workspace = tostring(base + slot), monitor = name, default = (slot == 1) })
    end
end

-- Al conectar un monitor declarado, devolvemos sus espacios (Hyprland los movió al quitarlo).
hl.on("monitor.added", function(mon)
    local name = mon and mon.name
    local idx = name and ctx.index[name]
    if idx == nil then return end
    for slot = 1, math.max(per, 9) do
        local ws = hl.get_workspace(idx * ctx.STRIDE + slot)
        if ws and ws.monitor and ws.monitor.name ~= name then
            hl.dispatch(hl.dsp.workspace.move({ workspace = idx * ctx.STRIDE + slot, monitor = name }))
        end
    end
end)
