-- Sincroniza Neovim con el tema global de hyprland-desktop.
--
-- No sustituye la configuración de monokai-pro del usuario: solo cambia su paleta
-- (override_palette) con la que genera `desktopctl apply` en palette.lua, de modo que el
-- fondo de Neovim es exactamente el de kitty. Las cursivas y demás `override` se conservan.
-- Si settings.json tiene "nvim": { "sync_theme": false }, Neovim queda con su tema original.
-- Un tema con "nvim": { "colorscheme": "<nombre>" } (Nordic) usa ese colorscheme tal cual, sin
-- pasar por monokai-pro; el plugin correspondiente se declara en hyprland-desktop.lua.

local M = {}

local dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
local palette_file = dir .. "palette.lua"

local function read_palette()
    local ok, data = pcall(dofile, palette_file)
    if ok and type(data) == "table" then return data end
end

function M.apply()
    local data = read_palette()
    if not data or not data.enabled then return end
    if data.colorscheme then
        vim.o.background = data.dark and "dark" or "light"
        pcall(vim.cmd.colorscheme, data.colorscheme)
        return
    end
    local ok, config = pcall(require, "monokai-pro.config")
    if not ok then return end
    -- La paleta original del usuario se guarda una vez y se usa como base: los temas que solo
    -- cambian fondos (monocromo) conservan sus colores, el resto la sustituye por completo.
    if M.original_palette == nil then
        M.original_palette = config.get().override_palette or false
    end
    local original = M.original_palette
    local palette = data.palette
    vim.o.background = data.dark and "dark" or "light"
    config.extend({
        filter = data.dark and "pro" or "light",
        override_palette = function(filter)
            local base = original and original(filter) or {}
            return vim.tbl_extend("force", base, palette)
        end,
    })
    vim.cmd.colorscheme("monokai-pro")
    -- Las guías de sangría de snacks (SnacksIndent) enlazan con NonText, que monokai-pro pinta
    -- del color del fondo: se les da el gris de los separadores para que se vean.
    local merged = vim.tbl_extend("force", original and original(data.dark and "pro" or "light") or {}, palette)
    if merged.dimmed3 then
        vim.api.nvim_set_hl(0, "SnacksIndent", { fg = merged.dimmed3, nocombine = true })
    end
end

-- Recarga en caliente: el generador reemplaza palette.lua de forma atómica (rename),
-- por eso se vigila el directorio y no el archivo.
local function watch()
    local handle = (vim.uv or vim.loop).new_fs_event()
    if not handle then return end
    local pending = false
    handle:start(dir, {}, function(_, filename)
        if filename ~= "palette.lua" or pending then return end
        pending = true
        vim.defer_fn(function()
            pending = false
            M.apply()
        end, 150)
    end)
end

function M.setup()
    M.apply()
    watch()
end

return M
