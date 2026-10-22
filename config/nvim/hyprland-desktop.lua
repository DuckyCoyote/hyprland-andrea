-- Especificación de lazy.nvim que instala hyprland-desktop en ~/.config/nvim/lua/plugins/
-- (enlace simbólico). Carga el sincronizador de tema justo después de monokai-pro.
local root = vim.fn.fnamemodify(vim.fn.resolve(debug.getinfo(1, "S").source:sub(2)), ":h")

---@type LazySpec
return {
    {
        dir = root,
        name = "hyprland-desktop-theme",
        lazy = false,
        priority = 999, -- monokai-pro usa 1000: se configura primero
        dependencies = { "loctvl842/monokai-pro.nvim" },
        config = function() require("hyprland_desktop").setup() end,
    },
    -- Colorschemes que usan tal cual los temas con "nvim": { "colorscheme": … } (lazy.nvim los
    -- carga al pedir el colorscheme)
    { "AlexvZyl/nordic.nvim", lazy = true },
}
