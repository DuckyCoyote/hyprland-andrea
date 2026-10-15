-- Autocompletado
--   · Menú de sugerencias (blink.cmp): se recorre con Tab / Shift+Tab y Enter acepta. Las flechas
--     ya no seleccionan: mueven el cursor como siempre.
--   · GitHub Copilot: sugerencias en línea (texto atenuado) que solo se aceptan con Ctrl+Enter.
--     No entra en el menú de blink ni usa Tab. Primera vez: `:Copilot auth`.

---@type LazySpec
return {
  {
    "saghen/blink.cmp",
    opts = {
      keymap = {
        ["<Up>"] = false,
        ["<Down>"] = false,
      },
    },
  },
  {
    "zbirenbaum/copilot.lua",
    cmd = "Copilot",
    event = "InsertEnter",
    opts = {
      panel = { enabled = false },
      suggestion = {
        enabled = true,
        auto_trigger = true,
        keymap = {
          accept = "<C-CR>",
          accept_word = false,
          accept_line = false,
          next = "<M-]>",
          prev = "<M-[>",
          dismiss = "<C-]>",
        },
      },
      filetypes = { markdown = true, yaml = true, gitcommit = true },
    },
  },
}
