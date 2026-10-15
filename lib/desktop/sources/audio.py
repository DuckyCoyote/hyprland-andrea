"""Tema `audio`: salida/entrada por defecto, volumen, silencio y dispositivos (PipeWire).

Eventos: `pactl subscribe` (servidor pipewire-pulse). Lectura: `pactl -f json`.
Acciones: `wpctl` para volumen/silencio del dispositivo por defecto y `pactl` para cambiar
el dispositivo por defecto (acepta nombres estables en lugar de ids de nodo).
"""
import asyncio
import json

from ..daemon import Source
from ..util import Debouncer, have, run, stream_lines

_ICONS_OUT = {"headphone": "󰋋", "headset": "󰋎", "hdmi": "󰡁", "bluez": "󰂯", "usb": "󰓃", "speaker": "󰓃"}
_ICONS_IN = {"bluez": "󰂯", "usb": "󰍬", "webcam": "󰄀"}


def _percent(volume: dict) -> int:
    for ch in volume.values():
        try:
            return int(str(ch.get("value_percent", "0")).rstrip("%"))
        except ValueError:
            pass
    return 0


def _describe(dev: dict) -> str:
    props = dev.get("properties", {})
    for value in (dev.get("description"), props.get("device.description"), props.get("node.nick"), props.get("device.product.name")):
        if value and value != "(null)":
            return value
    return dev.get("name", "?")


def _kind_icon(dev: dict, table: dict, default: str) -> str:
    props = dev.get("properties", {})
    hay = " ".join([dev.get("name", ""), props.get("device.form_factor", ""), props.get("device.bus", ""),
                    dev.get("active_port") or ""]).lower()
    for key, icon in table.items():
        if key in hay:
            return icon
    return default


def volume_icon(percent: int, muted: bool) -> str:
    if muted or percent == 0:
        return "󰝟"
    return "󰕿" if percent < 34 else "󰖀" if percent < 67 else "󰕾"


class AudioSource(Source):
    topic = "audio"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._refresh = Debouncer(0.05, self.refresh)

    async def start(self) -> None:
        if not have("pactl"):
            self.publish({"available": False, "error": "pactl no está instalado (paquete libpulse)"})
            return
        await self.refresh()

        async def on_event(line: str) -> None:
            if any(k in line for k in ("sink", "source", "server", "card")) and "source-output" not in line:
                self._refresh()

        await stream_lines(["pactl", "subscribe"], on_event, name="pactl subscribe")

    async def _list(self, what: str) -> list:
        code, out, _ = await run("pactl", "-f", "json", "list", what)
        try:
            return json.loads(out) if code == 0 else []
        except json.JSONDecodeError:
            return []

    async def refresh(self) -> None:
        sinks, sources, (_, dsink, _), (_, dsource, _) = await asyncio.gather(
            self._list("sinks"), self._list("sources"),
            run("pactl", "get-default-sink"), run("pactl", "get-default-source"))
        dsink, dsource = dsink.strip(), dsource.strip()
        sources = [s for s in sources if not s.get("monitor_source") and not s.get("name", "").endswith(".monitor")
                   and s.get("properties", {}).get("device.class") != "monitor"]

        def pack(devs, default, table, fallback):
            out = []
            for d in devs:
                pct, muted = _percent(d.get("volume", {})), bool(d.get("mute"))
                out.append({"name": d.get("name", ""), "description": _describe(d),
                            "port": (d.get("active_port") or ""), "volume": pct, "muted": muted,
                            "default": d.get("name") == default, "icon": _kind_icon(d, table, fallback)})
            return out

        outs = pack(sinks, dsink, _ICONS_OUT, "󰓃")
        ins = pack(sources, dsource, _ICONS_IN, "󰍬")
        sink = next((s for s in outs if s["default"]), outs[0] if outs else None)
        source = next((s for s in ins if s["default"]), ins[0] if ins else None)
        self.publish({
            "available": True,
            "has_sink": sink is not None, "has_source": source is not None,
            "sink": sink and {**sink, "glyph": volume_icon(sink["volume"], sink["muted"])},
            "source": source and {**source, "glyph": "󰍭" if source["muted"] else "󰍬"},
            "sinks": outs,
            "sources": ins,
        })

    # ---- órdenes -------------------------------------------------------------
    @staticmethod
    def _target(kind: str) -> str:
        return "@DEFAULT_AUDIO_SOURCE@" if kind in ("source", "mic", "input") else "@DEFAULT_AUDIO_SINK@"

    async def cmd_set(self, kind: str, percent: str) -> None:
        value = max(0, min(150, int(float(percent))))
        await run("wpctl", "set-volume", "-l", "1.5", self._target(kind), f"{value}%")

    async def cmd_step(self, kind: str, delta: str) -> None:
        delta = {"up": "+5", "down": "-5"}.get(delta, delta)
        sign = "+" if not delta.startswith("-") else "-"
        await run("wpctl", "set-volume", "-l", "1.0", self._target(kind), f"{delta.lstrip('+-')}%{sign}")

    async def cmd_mute(self, kind: str = "sink") -> None:
        await run("wpctl", "set-mute", self._target(kind), "toggle")

    async def cmd_default(self, kind: str, name: str) -> None:
        verb = "set-default-source" if kind in ("source", "mic", "input") else "set-default-sink"
        await run("pactl", verb, name)
