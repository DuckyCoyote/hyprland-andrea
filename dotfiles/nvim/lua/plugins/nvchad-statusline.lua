-- Barra de estado (statusline) con la apariencia de NvChad sobre heirline.
--
-- Estructura, de izquierda a derecha (igual que el tema "default" de NvChad):
--   [MODO][icono + archivo] rama +1 ~2 -3  ...  diagnosticos  LSP ~ servidor [carpeta] [linea/total]
--
-- Los colores se toman del colorscheme activo, así que la barra sigue combinando
-- con monokai-pro (o con el tema que se use en cada momento).

-- Glifos de Nerd Font definidos por punto de codigo para no depender de la
-- codificacion del archivo (medias circunferencias, carpeta e icono de posicion)
local sep_r = vim.fn.nr2char(0xe0b4) -- separador derecho (media circunferencia)
local sep_l = vim.fn.nr2char(0xe0b6) -- separador izquierdo (media circunferencia)
local icon_cwd = vim.fn.nr2char(0xf024b) -- carpeta del directorio de trabajo
local icon_pos = vim.fn.nr2char(0xf0c9) -- posicion del cursor
local icon_vim = vim.fn.nr2char(0xe62b) -- logo de Vim, al lado del modo

--- Normaliza un color de Neovim (número o "#rrggbb") a "#rrggbb"
---@param color string|number|nil
---@param fallback string
---@return string
local function to_hex(color, fallback)
  if type(color) == "number" then return string.format("#%06x", color) end
  if type(color) == "string" and color:match "^#%x%x%x%x%x%x$" then return color end
  return fallback
end

--- Mezcla dos colores, `alpha` es el peso del segundo
---@param c1 string|number|nil
---@param c2 string|number|nil
---@param alpha number
---@return string
local function blend(c1, c2, alpha)
  c1, c2 = to_hex(c1, "#1a1b26"), to_hex(c2, "#c0caf5")
  local function channel(i)
    local a, b = tonumber(c1:sub(i, i + 1), 16), tonumber(c2:sub(i, i + 1), 16)
    return math.floor(a + (b - a) * alpha + 0.5)
  end
  return string.format("#%02x%02x%02x", channel(2), channel(4), channel(6))
end

---@type LazySpec
return {
  {
    "AstroNvim/astroui",
    ---@type AstroUIOpts
    opts = {
      -- icono propio para el bloque de modo
      icons = { Vim = icon_vim },
      status = {
        -- nombres de los modos tal y como los muestra NvChad
        modes = {
          ["V"] = { "V-LINE", "visual" },
          ["Vs"] = { "V-LINE", "visual" },
          ["\22"] = { "V-BLOCK", "visual" }, -- <C-v>
          ["\22s"] = { "V-BLOCK", "visual" },
          ["S"] = { "S-LINE", "visual" },
          ["\19"] = { "S-BLOCK", "visual" }, -- <C-s>
          ["t"] = { "TERMINAL", "terminal" },
          ["nt"] = { "NTERMINAL", "terminal" },
        },
        -- colores extra que usan los bloques de la derecha
        colors = function(colors)
          local normal = require("astroui").get_hlgroup("Normal", { fg = colors.fg, bg = colors.bg })
          colors.lightbg = blend(colors.bg, normal.fg, 0.14)
          colors.lightbg_fg = normal.fg
          colors.cwd_accent = colors.git_removed
          colors.pos_accent = colors.git_added
          return colors
        end,
      },
    },
  },
  {
    "rebelot/heirline.nvim",
    opts = function(_, opts)
      local status = require "astroui.status"
      local get_icon = require("astroui").get_icon
      local lsp_names = status.provider.lsp_client_names { truncate = 0.25 }

      opts.statusline = {
        hl = { fg = "fg", bg = "bg" },

        -- MODO: bloque de color con el nombre del modo
        status.component.mode {
          mode_text = { icon = { kind = "Vim", padding = { right = 1 } }, padding = { left = 1, right = 1 } },
          hl = { fg = "mode_fg", bold = true },
          surround = {
            separator = { "", sep_r },
            color = function() return { main = status.hl.mode_bg(), right = "lightbg" } end,
            update = { "ModeChanged", pattern = "*:*" },
          },
        },

        -- ARCHIVO: icono + nombre sobre un fondo algo más claro
        status.component.file_info {
          file_icon = { padding = { left = 1, right = 1 } },
          filename = { fallback = "Empty" },
          filetype = false,
          file_modified = { padding = { left = 1 } },
          file_read_only = { padding = { left = 1 } },
          padding = { right = 1 },
          hl = { fg = "lightbg_fg" },
          surround = { separator = { "", sep_r }, color = { main = "lightbg", right = "bg" } },
        },

        -- GIT: rama y cambios
        status.component.git_branch {
          surround = false,
          padding = { left = 1 },
          condition = status.condition.is_git_repo,
        },
        status.component.git_diff {
          surround = false,
          condition = status.condition.git_changed,
        },

        status.component.fill(),
        status.component.cmd_info(), -- macros, búsqueda, comandos
        status.component.fill(),

        -- DIAGNÓSTICOS
        status.component.diagnostics {
          surround = false,
          padding = { right = 1 },
          condition = status.condition.has_diagnostics,
        },

        -- LSP activo
        status.component.builder {
          condition = status.condition.lsp_attached,
          {
            provider = function(self)
              local names = lsp_names(self)
              if names == "" then return "" end
              local icon = get_icon("ActiveLSP", 1)
              if vim.o.columns <= 100 then return icon .. "LSP" end
              return icon .. "LSP ~ " .. names
            end,
            update = {
              "LspAttach",
              "LspDetach",
              "BufEnter",
              "FileType",
              "VimResized",
              callback = function() vim.schedule(vim.cmd.redrawstatus) end,
            },
          },
          padding = { left = 1, right = 1 },
          hl = function() return status.hl.get_attributes "lsp" end,
        },

        -- DIRECTORIO DE TRABAJO
        {
          condition = function() return vim.o.columns > 85 end,
          update = { "DirChanged", "VimResized" },
          { provider = sep_l, hl = { fg = "cwd_accent", bg = "bg" } },
          {
            provider = function() return vim.g.icons_enabled ~= false and " " .. icon_cwd .. " " or " " end,
            hl = { fg = "bg", bg = "cwd_accent", bold = true },
          },
          {
            provider = function() return " " .. vim.fn.fnamemodify(vim.fn.getcwd(), ":t") .. " " end,
            hl = { fg = "lightbg_fg", bg = "lightbg" },
          },
        },

        -- POSICIÓN DEL CURSOR
        {
          update = { "CursorMoved", "CursorMovedI", "BufEnter", "VimResized" },
          {
            provider = sep_l,
            hl = function() return { fg = "pos_accent", bg = vim.o.columns > 85 and "lightbg" or "bg" } end,
          },
          {
            provider = function() return vim.g.icons_enabled ~= false and " " .. icon_pos .. " " or " " end,
            hl = { fg = "bg", bg = "pos_accent", bold = true },
          },
          { provider = " %l/%L ", hl = { fg = "pos_accent", bg = "lightbg", bold = true } },
        },
      }

      return opts
    end,
  },
}
