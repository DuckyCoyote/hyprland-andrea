-- Contexto compartido por todos los módulos: settings y tema generados.
-- Si faltan (primera ejecución sin `desktopctl apply`) se usan valores seguros y se avisa.

local ctx = {}

local function load(name, fallback)
    local ok, mod = pcall(require, name)
    if ok and type(mod) == "table" and next(mod) ~= nil then
        return mod
    end
    ctx.missing = true
    return fallback
end

ctx.S = load("generated.settings", {
    ctl = "desktopctl",
    apps = { terminal = "kitty", browser = "firefox", file_manager = "dolphin", editor = "code" },
    monitors = {},
    workspaces_per_monitor = 6,
    keyboard = { layout = "us" },
    input = {},
})

ctx.T = load("generated.theme", {
    active_border = "rgb(cba6f7)", inactive_border = "rgb(313244)", urgent_border = "rgb(f38ba8)",
    shadow = "rgba(11111baa)", background = "rgb(1e1e2e)", rounding = 10, border_size = 2,
    gaps_in = 4, gaps_out = 10, shadows = true, animations = true,
    active_opacity = 1.0, inactive_opacity = 1.0, font = "JetBrainsMono Nerd Font",
})

-- Orden de monitores: el principal primero y después el resto en el orden declarado.
-- lib/desktop/sources/wm.py usa exactamente el mismo orden para numerar espacios.
ctx.order = {}
for _, m in ipairs(ctx.S.monitors) do
    if m.primary then table.insert(ctx.order, m.name) end
end
for _, m in ipairs(ctx.S.monitors) do
    if not m.primary then table.insert(ctx.order, m.name) end
end
ctx.index = {}
for i, name in ipairs(ctx.order) do ctx.index[name] = i - 1 end

ctx.STRIDE = 10

--- Id del espacio `slot` (1..9) en el monitor enfocado: monitor 0 -> 1..9, monitor 1 -> 11..19…
function ctx.slot_id(slot)
    local mon = hl.get_active_monitor()
    local idx = 0
    if mon then
        idx = ctx.index[mon.name] or (#ctx.order + (mon.id or 0))
    end
    return idx * ctx.STRIDE + slot
end

function ctx.ctl(args)
    return ctx.S.ctl .. " " .. args
end

if ctx.missing then
    hl.on("hyprland.start", function()
        hl.notification.create({
            text = "hyprland-desktop: faltan archivos generados. Ejecuta «desktopctl apply».",
            timeout = 12000, color = "rgb(f38ba8)",
        })
    end)
end

return ctx
