-- ─────────────────────────────────────────────────────────────────────────────
-- hyprland-desktop · Hyprland >= 0.56 (configuración Lua)
--
-- Este archivo solo carga módulos. Los valores (monitores, apps, colores, fuentes,
-- tamaños) NO se escriben aquí: vienen de generated/*.lua, que `desktopctl apply`
-- genera a partir de settings.json y del tema activo.
-- ─────────────────────────────────────────────────────────────────────────────

require("modules.env")
require("modules.monitors")
require("modules.look")
require("modules.input")
require("modules.workspaces")
require("modules.keybinds")
require("modules.rules")
require("modules.autostart")
