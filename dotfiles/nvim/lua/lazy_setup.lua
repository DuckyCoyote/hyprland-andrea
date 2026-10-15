require("lazy").setup({
  {
    "AstroNvim/AstroNvim",
    version = "^6", -- Remove version tracking to elect for nightly AstroNvim
    import = "astronvim.plugins",
    opts = { -- AstroNvim options must be set here with the `import` key
      mapleader = " ", -- This ensures the leader key must be configured before Lazy is set up
      maplocalleader = ",", -- This ensures the localleader key must be configured before Lazy is set up
      icons_enabled = true, -- Set to false to disable icons (if no Nerd Font is available)
      pin_plugins = nil, -- Default will pin plugins when tracking `version` of AstroNvim, set to true/false to override
      update_notifications = true, -- Enable/disable notification about running `:Lazy update` twice to update pinned plugins
    },
  },
  {
    {
      "kndndrj/nvim-dbee",
      dependencies = {
        "MunifTanjim/nui.nvim",
      },
      build = function()
        -- Install tries to automatically detect the install method.
        -- if it fails, try calling it with one of these parameters:
        --    "curl", "wget", "bitsadmin", "go"
        require("dbee").install()
      end,
      config = function()
        require("dbee").setup(--[[optional config]])
      end,
    },
  },
  {
    "loctvl842/monokai-pro.nvim",
    lazy = false,
    priority = 1000,
    config = function()
      require("monokai-pro").setup({
        override_palette = function(filter)
          return {
            dark2 = "#101014",
            dark1 = "#16161E",
            dark3 = "#363b54",
            dark4 = "#363b54",
            background = "#1A1B26",
            text = "#C0CAF5",
            accent1 = "#f7768e",
            accent2 = "#7aa2f7",
            accent3 = "#e0af68",
            accent4 = "#9ece6a",
            accent5 = "#0DB9D7",
            accent6 = "#9d7cd8",
            dimmed1 = "#737aa2",
            dimmed2 = "#787c99",
            dimmed3 = "#363b54",
            dimmed4 = "#363b54",
            dimmed5 = "#16161e",
          }
          end,
        -- palabras clave (keywords) en cursiva: se fusiona sobre los grupos del
        -- tema, asi que conserva los colores y solo anade el atributo italic
        override = function()
          local keyword_groups = {
            -- grupos clasicos de vim
            "Keyword",
            "Statement",
            "Conditional",
            "Repeat",
            "Label",
            "Exception",
            "Include",
            "Define",
            -- grupos de treesitter
            "@keyword",
            "@keyword.conditional",
            "@keyword.coroutine",
            "@keyword.debug",
            "@keyword.directive",
            "@keyword.directive.define",
            "@keyword.exception",
            "@keyword.function",
            "@keyword.import",
            "@keyword.operator",
            "@keyword.repeat",
            "@keyword.return",
            "@keyword.storage",
            "@keyword.type",
            -- variantes por lenguaje que define el propio tema
            "@keyword.cpp",
            "@keyword.dockerfile",
            "@keyword.function.go",
            "@keyword.function.lua",
            "@keyword.lua",
            "@keyword.scss",
          }
          local highlights = {}
          for _, group in ipairs(keyword_groups) do
            highlights[group] = { italic = true }
          end
          return highlights
        end,
        })
      vim.cmd.colorscheme("monokai-pro")
    end,
  },
  {
    "lewis6991/gitsigns.nvim",
    lazy = false,
    priority = 1000

  },
  { import = "community" },
  { import = "plugins" },
} --[[@as LazySpec]], {
  -- Configure any other `lazy.nvim` configuration options here
  install = { colorscheme = { "astrotheme", "habamax" } },
  ui = { backdrop = 100 },
  performance = {
    rtp = {
      -- disable some rtp plugins, add more to your liking
      disabled_plugins = {
        "gzip",
        "netrwPlugin",
        "tarPlugin",
        "tohtml",
        "zipPlugin",
      },
    },
  },
} --[[@as LazyConfig]])
