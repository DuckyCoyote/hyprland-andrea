"""Tema `bluetooth`: adaptador (encendido, visible, buscando) y dispositivos (emparejados y cercanos).

Eventos: `gdbus monitor` sobre org.bluez (señales de propiedades; no necesita root).
Lectura y búsqueda con `bluetoothctl`; el resto de acciones, por D-Bus con `busctl`, que responde
con éxito o con un error claro (la salida de `bluetoothctl` mezcla eventos y su prompt).
El emparejamiento usa un agente NoInputNoOutput, que basta para auriculares, ratones, teclados
y altavoces; los dispositivos que exigen PIN se emparejan desde el gestor gráfico («Otras opciones»).
"""
import asyncio
import re

from ..daemon import Source
from ..util import Debouncer, have, log, run, stream_lines

# Icono de BlueZ (propiedad Icon) → glifo Nerd Font
DEVICE_GLYPHS = {
    "audio-headset": "\U000F02CB", "audio-headphones": "\U000F02CB", "audio-card": "\U000F04C3",
    "input-mouse": "\U000F037D", "input-keyboard": "\U000F030C", "input-gaming": "\U000F02B4",
    "input-tablet": "\U000F04F7", "phone": "\U000F011C", "computer": "\U000F0322",
}
DEFAULT_GLYPH = "\U000F00AF"
MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
ANSI = re.compile(r"\x1b\[[0-9;]*m|\x01|\x02")
# Errores de BlueZ más habituales → texto para el panel
BLUEZ_ERRORS = {
    "NotConnected": "el dispositivo no está conectado", "NotReady": "el adaptador no está listo",
    "in progress": "ya hay una operación en curso", "AlreadyConnected": "ya está conectado",
    "AuthenticationFailed": "autenticación rechazada", "AuthenticationCanceled": "emparejamiento cancelado",
    "ConnectionAttemptFailed": "el dispositivo no responde (¿está encendido y cerca?)",
    "page-timeout": "el dispositivo no responde (¿está encendido y cerca?)",
    "timed out": "el dispositivo no responde (¿está encendido y cerca?)", "DoesNotExist": "el dispositivo ya no existe",
}
SCAN_SECONDS = 15
CLEAR_AFTER = 6  # segundos que se ve un mensaje de estado o de error


def _props(text: str) -> dict[str, str]:
    """Pares «Clave: valor» de la salida de `bluetoothctl show/info` (la primera aparición gana)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition(": ")
        if sep and key not in out:
            out[key] = value.strip()
    return out


class BluetoothSource(Source):
    topic = "bluetooth"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._refresh = Debouncer(0.4, self.refresh)
        self.status = ""
        self.error = ""
        self.busy = ""  # MAC del dispositivo con una operación en curso
        self.scanning = False
        self._clear: asyncio.TimerHandle | None = None
        self.adapter_path = "/org/bluez/hci0"

    async def start(self) -> None:
        if not have("bluetoothctl"):
            self.publish({"available": False, "error": "BlueZ (bluetoothctl) no está instalado", "devices": []})
            return
        await self.refresh()
        if have("gdbus"):
            await stream_lines(["gdbus", "monitor", "--system", "--dest", "org.bluez"],
                               lambda _l: self._event(), name="gdbus monitor bluez")

    async def _event(self) -> None:
        self._refresh()

    async def refresh(self) -> None:
        code, show, _ = await run("bluetoothctl", "show")
        adapter = _props(show) if code == 0 and "Controller" in show else {}
        if not adapter:
            self.publish({"available": False, "error": "No hay adaptador Bluetooth", "devices": [],
                          "powered": False, "glyph": "\U000F00B2"})
            return
        _, tree, _ = await run("busctl", "--system", "--list", "tree", "org.bluez")
        self.adapter_path = next((l.strip() for l in tree.splitlines() if re.fullmatch(r"/org/bluez/hci\d+", l.strip())),
                                 self.adapter_path)
        _, listing, _ = await run("bluetoothctl", "devices")
        macs = [p[1] for p in (l.split(" ", 2) for l in listing.splitlines()) if len(p) >= 2 and MAC.match(p[1])]
        infos = await asyncio.gather(*(run("bluetoothctl", "info", m) for m in macs))
        devices = []
        for mac, (_, info, _) in zip(macs, infos):
            d = _props(info)
            name = d.get("Alias") or d.get("Name") or mac
            battery = re.search(r"\((\d+)\)", d.get("Battery Percentage", ""))
            devices.append({
                "mac": mac, "name": name, "glyph": DEVICE_GLYPHS.get(d.get("Icon", ""), DEFAULT_GLYPH),
                "paired": d.get("Paired") == "yes", "trusted": d.get("Trusted") == "yes",
                "connected": d.get("Connected") == "yes",
                "battery": int(battery.group(1)) if battery else -1,
                # los cercanos sin nombre solo muestran la MAC con guiones: se ocultan
                "named": name.replace("-", ":") != mac,
            })
        devices.sort(key=lambda x: (not x["connected"], not x["paired"], x["name"].lower()))
        powered = adapter.get("Powered") == "yes"
        connected = [d for d in devices if d["connected"]]
        glyph = "\U000F00B2" if not powered else "\U000F00B1" if connected else "\U000F00AF"
        self.publish({
            "available": True, "powered": powered, "glyph": glyph,
            "discoverable": adapter.get("Discoverable") == "yes",
            "scanning": self.scanning or adapter.get("Discovering") == "yes",
            "name": adapter.get("Alias") or adapter.get("Name", ""),
            "connected_count": len(connected),
            "connected_names": ", ".join(d["name"] for d in connected),
            "paired": [d for d in devices if d["paired"]][:12],
            "nearby": [d for d in devices if not d["paired"] and d["named"]][:12],
            "busy": self.busy, "status": self.status, "error": self.error,
        })

    def _set(self, status: str = "", error: str = "", busy: str = "") -> None:
        self.status, self.error, self.busy = status, error, busy
        self._refresh()
        # los mensajes finales (no «Conectando…» ni «Buscando…») se borran solos
        if self._clear:
            self._clear.cancel()
            self._clear = None
        if (status or error) and not busy and not self.scanning:
            self._clear = asyncio.get_running_loop().call_later(CLEAR_AFTER, self._set)

    def _device(self, mac: str) -> dict | None:
        data = self.hub.get("bluetooth") or {}
        return next((d for d in data.get("paired", []) + data.get("nearby", []) if d["mac"] == mac), None)

    def _dev_path(self, mac: str) -> str:
        return f"{self.adapter_path}/dev_{mac.replace(':', '_')}"

    async def _bus(self, verb: str, path: str, iface: str, *args: str, timeout: float = 30) -> tuple[bool, str]:
        """`busctl --system <verb> org.bluez <path> <iface> …` → (éxito, mensaje de error legible)."""
        code, _, err = await run("busctl", "--system", f"--timeout={int(timeout)}", verb, "org.bluez", path,
                                 f"org.bluez.{iface}", *args, timeout=timeout + 5)
        if code == 0:
            return True, ""
        msg = ANSI.sub("", err).strip().splitlines()[-1] if err.strip() else "error desconocido"
        msg = msg.removeprefix("Call failed: ").removeprefix("Failed to set property: ")
        return False, next((v for k, v in BLUEZ_ERRORS.items() if k.lower() in msg.lower()), msg)

    # ---- órdenes -------------------------------------------------------------
    async def cmd_toggle_power(self) -> None:
        data = self.hub.get("bluetooth") or {}
        if not data.get("powered") and have("rfkill"):
            await run("rfkill", "unblock", "bluetooth")  # bloqueado por software (modo avión)
        ok, msg = await self._bus("set-property", self.adapter_path, "Adapter1", "Powered", "b",
                                  "false" if data.get("powered") else "true")
        self._set(error="" if ok else msg)

    async def cmd_toggle_discoverable(self) -> None:
        data = self.hub.get("bluetooth") or {}
        ok, msg = await self._bus("set-property", self.adapter_path, "Adapter1", "Discoverable", "b",
                                  "false" if data.get("discoverable") else "true")
        self._set(status="" if not ok or data.get("discoverable") else f"Visible como «{data.get('name', '')}» durante 3 min",
                  error="" if ok else msg)

    async def cmd_scan(self) -> None:
        """Busca dispositivos cercanos durante unos segundos (`bluetoothctl --timeout` para el escaneo al salir)."""
        if self.scanning:
            return
        self.scanning = True
        self._set(status="Buscando dispositivos…")
        await run("bluetoothctl", "--timeout", str(SCAN_SECONDS), "scan", "on", timeout=SCAN_SECONDS + 5)
        self.scanning = False
        self._set()

    async def cmd_connect(self, mac: str) -> str:
        if not MAC.match(mac):
            return "MAC no válida"
        dev = self._device(mac) or {"name": mac, "paired": False, "trusted": False}
        self._set(busy=mac, status=f"Conectando con {dev['name']}…")
        if not dev["paired"]:
            # bluetoothctl solo aporta aquí el agente; el resultado se comprueba leyendo «Paired»
            _, out, err = await run("bluetoothctl", "--agent", "NoInputNoOutput", "pair", mac, timeout=40)
            _, info, _ = await run("bluetoothctl", "info", mac)
            if _props(info).get("Paired") != "yes":
                text = ANSI.sub("", out + err)
                msg = next((v for k, v in BLUEZ_ERRORS.items() if k.lower() in text.lower()), "el dispositivo no aceptó el emparejamiento")
                log(f"bluetooth: no se pudo emparejar {mac}: {text.strip().splitlines()[-1:] or ''}")
                self._set(error=f"No se pudo emparejar: {msg}")
                return msg
        if not dev["trusted"]:
            await self._bus("set-property", self._dev_path(mac), "Device1", "Trusted", "b", "true")  # se reconecta solo
        ok, msg = await self._bus("call", self._dev_path(mac), "Device1", "Connect", timeout=20)
        self._set(status=f"Conectado a {dev['name']}" if ok else "", error="" if ok else f"No se pudo conectar: {msg}")
        return "ok" if ok else msg

    async def cmd_disconnect(self, mac: str) -> None:
        if MAC.match(mac):
            dev = self._device(mac) or {"name": mac}
            self._set(busy=mac, status=f"Desconectando {dev['name']}…")
            ok, msg = await self._bus("call", self._dev_path(mac), "Device1", "Disconnect")
            self._set(status=f"{dev['name']} desconectado" if ok else "", error="" if ok else f"No se pudo desconectar: {msg}")

    async def cmd_forget(self, mac: str) -> None:
        if MAC.match(mac):
            dev = self._device(mac) or {"name": mac}
            ok, msg = await self._bus("call", self.adapter_path, "Adapter1", "RemoveDevice", "o", self._dev_path(mac))
            self._set(status=f"{dev['name']} olvidado" if ok else "", error="" if ok else msg)

    async def cmd_editor(self) -> None:
        from ..util import spawn_detached
        spawn_detached("blueman-manager || kcmshell6 kcm_bluetooth || systemsettings kcm_bluetooth")
