"""Tema `displays`: pantallas conectadas y modo de proyección (como Win+P).

Modos:
  extend    cada pantalla con su posición de settings.json → monitors (las nuevas, a la derecha)
  mirror    las demás duplican la principal (presentaciones con proyector)
  primary   solo la principal; el resto apagadas
  external  solo las secundarias (proyector o monitor externo); la principal apagada

Además se puede apagar cualquier pantalla suelta (extend/mirror). El estado vive en
~/.local/state/hyprland-desktop/displays.json y se aplica en caliente cada vez que cambian las
pantallas o se recarga el compositor; la configuración estática de Hyprland las enciende todas,
así nunca se arranca con la única pantalla conectada apagada.
"""
import asyncio

from .. import config, paths
from ..daemon import Source
from ..util import Debouncer, log, notify

MODES = [
    {"id": "extend", "label": "Extender", "glyph": "󰍺"},
    {"id": "mirror", "label": "Duplicar", "glyph": "󰆏"},
    {"id": "primary", "label": "Solo principal", "glyph": "󰍹"},
    {"id": "external", "label": "Solo secundarias", "glyph": "󰐮"},
]
LABELS = {m["id"]: m["label"] for m in MODES}


class DisplaysSource(Source):
    topic = "displays"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.state = config.read_state(paths.DISPLAY_STATE, {})
        self.connected: set[str] | None = None
        self._lock = asyncio.Lock()
        self._changed = Debouncer(1.0, self.sync)

    @property
    def wm(self):
        return self.hub.sources["wm"].wm

    async def start(self) -> None:
        await self.sync()

    def on_monitors(self) -> None:
        """Lo llama WmSource ante cualquier cambio de pantallas o recarga del compositor."""
        self._changed()

    # ---- modelo ---------------------------------------------------------------
    def _mode(self) -> str:
        mode = self.state.get("mode", "extend")
        return mode if mode in LABELS else "extend"

    def _primary(self, outputs: list[dict]) -> str:
        names = [o["name"] for o in outputs]
        declared = [m for m in config.load().get("monitors", []) if m.get("name") in names]
        for m in declared:
            if m.get("primary"):
                return m["name"]
        if declared:
            return declared[0]["name"]
        return min(outputs, key=lambda o: (o["x"], o["y"]))["name"] if outputs else ""

    def _specs(self, outputs: list[dict], mode: str, off: set[str]) -> list[dict]:
        declared = {m["name"]: m for m in config.load().get("monitors", []) if "name" in m}
        primary = self._primary(outputs)
        specs = []
        for o in outputs:
            name, d = o["name"], declared.get(o["name"], {})
            if mode == "primary":
                state = "on" if name == primary else "off"
            elif mode == "external":
                state = "off" if name == primary or name in off else "on"
            elif name in off and (mode == "extend" or name != primary):
                state = "off"
            elif mode == "mirror" and name != primary:
                state = "mirror"
            else:
                state = "on"
            specs.append({"name": name, "state": state, "mirror": primary, "mode": d.get("mode"),
                          "position": d.get("position"), "scale": d.get("scale")})
        return specs

    def _off(self) -> set[str]:
        """Pantallas apagadas a mano (Configuración → Pantallas)."""
        return set(self.state.get("disabled", []))

    @staticmethod
    def _differs(spec: dict, out: dict) -> bool:
        if spec["state"] == "off":
            return out["enabled"]
        if spec["state"] == "mirror":
            return not out["enabled"] or out["mirror_of"] != spec["mirror"]
        return not out["enabled"] or bool(out["mirror_of"])

    def _save(self) -> None:
        config.write_json(paths.DISPLAY_STATE, self.state)

    # ---- sincronización -------------------------------------------------------
    async def sync(self) -> None:
        async with self._lock:
            await self._sync()

    async def _sync(self) -> None:
        outputs = await self.wm.outputs()
        if outputs is None:  # compositor sin gestión de salidas: solo se informa
            self.publish({"managed": False, "mode": "extend", "modes": MODES, "outputs": []})
            return
        names = {o["name"] for o in outputs}
        if self.connected is not None:
            for o in outputs:
                if o["name"] not in self.connected:
                    notify("Pantalla conectada", f"{o['model'] or o['name']}: Super+Shift+P cambia el modo "
                           "de proyección (extender, duplicar, solo una pantalla).", icon="video-display")
        self.connected = names

        mode = self._mode()
        specs = self._specs(outputs, mode, self._off())
        if not any(s["state"] == "on" for s in specs):
            # p. ej. «solo secundarias» y se desconectó el proyector: nunca dejar todo apagado
            log(f"pantallas: el modo {mode} dejaría todo apagado; se vuelve a extender")
            self.state = {"mode": "extend", "disabled": []}
            self._save()
            mode = "extend"
            specs = self._specs(outputs, mode, set())
        current = {o["name"]: o for o in outputs}
        pending = [s for s in specs if self._differs(s, current[s["name"]])]
        if pending:
            log("pantallas: " + ", ".join(f"{s['name']}={s['state']}" for s in pending))
            await self.wm.configure_outputs(pending)
            outputs = await self.wm.outputs() or outputs
        self._publish(outputs, specs, mode)

    def _publish(self, outputs: list[dict], specs: list[dict], mode: str) -> None:
        primary = self._primary(outputs)
        states = {s["name"]: s["state"] for s in specs}
        on = sum(1 for s in specs if s["state"] == "on")
        items = []
        for o in sorted(outputs, key=lambda o: (o["name"] != primary, o["x"], o["name"])):
            state = states.get(o["name"], "on")
            items.append({
                **o, "primary": o["name"] == primary, "state": state,
                "status": {"on": "Encendida", "off": "Apagada", "mirror": f"Duplica {primary}"}[state],
                "glyph": {"on": "\U000f0379", "off": "\U000f0d90", "mirror": "\U000f018f"}[state],
                # se puede apagar si queda otra encendida (en Duplicar, la principal es el origen)
                "can_toggle": state != "on" or (on > 1 and not (mode == "mirror" and o["name"] == primary)),
            })
        self.publish({"managed": True, "mode": mode, "mode_label": LABELS[mode], "modes": MODES,
                      "primary": primary, "count": len(outputs), "outputs": items})

    # ---- órdenes --------------------------------------------------------------
    async def cmd_mode(self, mode: str) -> str:
        if mode not in LABELS:
            return f"modo desconocido: {mode} ({', '.join(LABELS)})"
        outputs = await self.wm.outputs() or []
        if mode in ("mirror", "external") and len(outputs) < 2:
            return f"«{LABELS[mode]}» necesita otra pantalla conectada"
        async with self._lock:
            self.state["mode"] = mode
            self._save()
            await self._sync()
        return f"modo de proyección: {LABELS[mode]}"

    async def cmd_cycle(self) -> str:
        """Super+Shift+P: siguiente modo (con una sola pantalla no hay nada que cambiar)."""
        outputs = await self.wm.outputs() or []
        if len(outputs) < 2:
            notify("Proyección", "Solo hay una pantalla conectada", icon="video-display")
            return "una sola pantalla"
        ids = [m["id"] for m in MODES]
        mode = ids[(ids.index(self._mode()) + 1) % len(ids)]
        msg = await self.cmd_mode(mode)
        notify("Proyección", LABELS[mode], icon="video-display")
        return msg

    async def cmd_toggle(self, name: str) -> str:
        """Enciende o apaga una pantalla. Desde «solo principal/secundarias» pasa a Extender."""
        async with self._lock:
            outputs = await self.wm.outputs() or []
            if name not in {o["name"] for o in outputs}:
                return f"pantalla no conectada: {name}"
            mode = self._mode()
            states = {s["name"]: s["state"] for s in self._specs(outputs, mode, self._off())}
            states[name] = "on" if states[name] == "off" else "off"
            if mode == "mirror" and name == self._primary(outputs) and states[name] == "off":
                return "En Duplicar la principal es el origen: no se puede apagar"
            if not any(s == "on" for s in states.values()):
                return "Debe quedar al menos una pantalla encendida"
            if mode in ("primary", "external"):
                mode = "extend"
            self.state = {"mode": mode, "disabled": sorted(n for n, s in states.items() if s == "off")}
            self._save()
            await self._sync()
        return f"{name}: {'encendida' if states[name] != 'off' else 'apagada'}"
