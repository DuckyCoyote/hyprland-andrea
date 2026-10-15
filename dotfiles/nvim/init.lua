-- This file simply bootstraps the installation of Lazy.nvim and then calls other files for execution
-- This file doesn't necessarily need to be touched, BE CAUTIOUS editing this file and proceed at your own risk.
local lazypath = vim.env.LAZY or vim.fn.stdpath "data" .. "/lazy/lazy.nvim"

if not (vim.env.LAZY or (vim.uv or vim.loop).fs_stat(lazypath)) then
  -- stylua: ignore
  local result = vim.fn.system({ "git", "clone", "--filter=blob:none", "https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath })
  if vim.v.shell_error ~= 0 then
    -- stylua: ignore
    vim.api.nvim_echo({ { ("Error cloning lazy.nvim:\n%s\n"):format(result), "ErrorMsg" }, { "Press any key to exit...", "MoreMsg" } }, true, {})
    vim.fn.getchar()
    vim.cmd.quit()
  end
end

vim.opt.rtp:prepend(lazypath)

-- validate that lazy is available
if not pcall(require, "lazy") then
  -- stylua: ignore
  vim.api.nvim_echo({ { ("Unable to load lazy from: %s\n"):format(lazypath), "ErrorMsg" }, { "Press any key to exit...", "MoreMsg" } }, true, {})
  vim.fn.getchar()
  vim.cmd.quit()
end

require "polish"
require "lazy_setup"

vim.opt.clipboard = "unnamedplus"

require('gitsigns').setup {
  signs = {
    add          = { text = '┃' },
    change       = { text = '┃' },
    delete       = { text = '_' },
    topdelete    = { text = '‾' },
    changedelete = { text = '~' },
    untracked    = { text = '┆' },
  },
  signs_staged = {
    add          = { text = '┃' },
    change       = { text = '┃' },
    delete       = { text = '_' },
    topdelete    = { text = '‾' },
    changedelete = { text = '~' },
    untracked    = { text = '┆' },
  },
  signs_staged_enable = true,
  signcolumn = true,  -- Toggle with `:Gitsigns toggle_signs`
  numhl      = false, -- Toggle with `:Gitsigns toggle_numhl`
  linehl     = false, -- Toggle with `:Gitsigns toggle_linehl`
  word_diff  = false, -- Toggle with `:Gitsigns toggle_word_diff`
  watch_gitdir = {
    follow_files = true
  },
  auto_attach = true,
  attach_to_untracked = false,
  current_line_blame = true, -- Toggle with `:Gitsigns toggle_current_line_blame`
  current_line_blame_opts = {
    virt_text = true,
    virt_text_pos = 'eol', -- 'eol' | 'overlay' | 'right_align'
    delay = 1000,
    ignore_whitespace = false,
    virt_text_priority = 100,
    use_focus = true,
  },
  current_line_blame_formatter = '<author>, <author_time:%R> - <summary>',
  sign_priority = 6,
  update_debounce = 100,
  status_formatter = nil, -- Use default
  max_file_length = 40000, -- Disable if file is longer than this (in lines)
  preview_config = {
    -- Options passed to nvim_open_win
    style = 'minimal',
    relative = 'cursor',
    row = 0,
    col = 1
  },
}

vim.keymap.set("n", "<leader>fcb", function()
          require("snacks").picker.grep({
            dirs = { vim.api.nvim_buf_get_name(0) } -- Limits the search directory to the current file path
          })
end, { desc = "Grep current buffer" })

vim.keymap.set("n", "<leader>tt", function()
  vim.cmd("t.")
end, { desc = "Duplicar línea actual" })

vim.keymap.set("x", "<leader>tt", ":t'> <CR>", {
  desc = "Duplicar selección"
})

vim.keymap.set("n", "<A-Up>", function()
  vim.cmd("m .-2")
end, { desc = "Mover línea hacia arriba" })

vim.keymap.set("n", "<A-Down>", function()
  vim.cmd("m .+1")
end, { desc = "Mover línea hacia abajo" })

vim.keymap.set("x", "<A-Up>", ":move '<-2<CR>gv-gv", {
  silent = true,
  desc = "Mover selección hacia arriba"
})

vim.keymap.set("x", "<A-Down>", ":move '>+1<CR>gv-gv", {
  silent = true,
  desc = "Mover selección hacia abajo"
})


-- Formatear todo el archivo
vim.keymap.set("n", "<leader>cf", function()
  vim.lsp.buf.format { async = true }
end, {
  silent = true,
  desc = "Formatear archivo"
})

-- Formatear selección visual
vim.keymap.set("x", "<leader>cf", function()
  vim.lsp.buf.format {
    range = {
      ["start"] = vim.api.nvim_buf_get_mark(0, "<"),
      ["end"] = vim.api.nvim_buf_get_mark(0, ">"),
    },
  }
end, {
  silent = true,
  desc = "Formatear selección"
})

vim.keymap.set("n", "<leader>js", function()
    vim.cmd("write")
    vim.cmd("botright 12split | terminal node " .. vim.fn.expand("%"))
    vim.cmd("startinsert")
end, { desc = "Run current JS file" })
