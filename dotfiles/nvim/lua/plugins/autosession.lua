-- Restaurar automaticamente el estado del editor de cada carpeta.
--
-- AstroNvim ya guarda una sesion por directorio de trabajo al salir (resession,
-- opcion `sessions.autosave.cwd`, activada por defecto), pero cargarla es manual
-- con <Leader>S. Este archivo la carga sola al abrir `nvim` en esa carpeta.
--
-- Solo se restaura si se abre `nvim` sin argumentos: si abres `nvim archivo.lua`
-- o le pasas texto por una tuberia, se comporta como siempre.
--
-- Atajos utiles que ya trae AstroNvim:
--   <Leader>SS  guardar la sesion de esta carpeta     <Leader>S.  cargarla
--   <Leader>Ss  guardar una sesion con nombre         <Leader>Sf  cargar una sesion
--   <Leader>Sl  cargar la ultima sesion               <Leader>SD  borrar una dirsession

---@type LazySpec
return {
  {
    "AstroNvim/astrocore",
    ---@type AstroCoreOpts
    opts = {
      sessions = {
        autosave = {
          last = true, -- guardar siempre la ultima sesion
          cwd = true, -- guardar ademas una sesion por carpeta
        },
        ignore = {
          -- carpetas en las que no guardar sesion (se comparan tal cual, sin subcarpetas)
          dirs = { "~", "/tmp" },
          filetypes = { "gitcommit", "gitrebase" },
          buftypes = {},
        },
      },
      autocmds = {
        restore_dirsession = {
          {
            event = "StdinReadPre",
            desc = "Marcar que nvim se abrio con entrada por stdin",
            callback = function() vim.g.started_with_stdin = true end,
          },
          {
            event = "VimEnter",
            desc = "Restaurar la sesion de la carpeta actual al abrir nvim sin argumentos",
            nested = true,
            callback = function()
              if vim.fn.argc(-1) > 0 or vim.g.started_with_stdin then return end
              local cwd = vim.uv.cwd()
              -- respetar la misma lista de carpetas ignoradas que se usa al guardar,
              -- para no restaurar sesiones viejas de carpetas que ya no se guardan
              for _, dir in ipairs(vim.tbl_get(require("astrocore").config, "sessions", "ignore", "dirs") or {}) do
                if vim.fn.expand(dir) == cwd then return end
              end
              -- si la carpeta no tiene sesion guardada no pasa nada: sigue el dashboard
              pcall(function() require("resession").load(cwd, { dir = "dirsession", silence_errors = true }) end)
            end,
          },
        },
      },
    },
  },
}
