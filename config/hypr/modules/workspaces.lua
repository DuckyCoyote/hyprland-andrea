-- Espacios de trabajo por monitor (como las «tags» por pantalla de AwesomeWM):
--   monitor principal -> 1..N, segundo monitor -> 11..N+10, etc.
-- La barra de cada monitor muestra solo sus espacios.
-- Grupos de escritorios: el grupo G repite todos los bloques G*100 ids más arriba
-- (101..109 en el principal, 111..119 en el segundo…).

local ctx = require("modules.ctx")
local per = ctx.S.workspaces_per_monitor or 6

for group = 0, ctx.groups - 1 do
    for idx, name in ipairs(ctx.order) do
        local base = group * ctx.GROUP_STRIDE + (idx - 1) * ctx.STRIDE
        for slot = 1, math.max(per, 9) do
            hl.workspace_rule({ workspace = tostring(base + slot), monitor = name,
                                default = (group == 0 and slot == 1) })
        end
    end
end

-- Al conectar un monitor declarado, devolvemos sus espacios (Hyprland los movió al quitarlo).
hl.on("monitor.added", function(mon)
    local name = mon and mon.name
    local idx = name and ctx.index[name]
    if idx == nil then return end
    for group = 0, ctx.groups - 1 do
        for slot = 1, math.max(per, 9) do
            local id = group * ctx.GROUP_STRIDE + idx * ctx.STRIDE + slot
            local ws = hl.get_workspace(id)
            if ws and ws.monitor and ws.monitor.name ~= name then
                hl.dispatch(hl.dsp.workspace.move({ workspace = id, monitor = name }))
            end
        end
    end
end)
