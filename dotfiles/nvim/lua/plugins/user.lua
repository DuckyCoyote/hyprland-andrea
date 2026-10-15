-- if true then return {} end -- WARN: REMOVE THIS LINE TO ACTIVATE THIS FILE

-- You can also add or configure plugins by creating files in this `plugins/` folder
-- PLEASE REMOVE THE EXAMPLES YOU HAVE NO INTEREST IN BEFORE ENABLING THIS FILE
-- Here are some examples:

---@type LazySpec
return {
  -- Mostrar los errores mientras se escribe (AstroNvim los aplaza hasta volver a modo normal)
  { "AstroNvim/astrocore", opts = { diagnostics = { update_in_insert = true } } },
    {
      "codegik/claude-chat.nvim",
      cmd = { "ClaudeChat", "ClaudeChatReset", "ClaudeChatFile", "ClaudeChatContinue", "ClaudeChatSessions" },
      keys = {
        { "<leader>cai", "<cmd>ClaudeChat<cr>", desc = "Claude Chat: toggle sidebar" },
        { "<leader>af", "<cmd>ClaudeChatFile<cr>", desc = "Claude Chat: add current file" },
      },
      config = function()
        require("claude-chat").setup()
      end,
  },
  {
    "akinsho/toggleterm.nvim",
    keys = {
      {
        "<leader>xai",
        function()
          if not _G._codex_term then
            _G._codex_term = require("toggleterm.terminal").Terminal:new {
              cmd = "codex",
              direction = "vertical",
              close_on_exit = true,
              on_exit = function() _G._codex_term = nil end,
            }
          end
          _G._codex_term:toggle(80)
        end,
        desc = "Codex: toggle sidebar",
      },
    },
  },
}
