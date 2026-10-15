"""Tema `network`: Ethernet/Wi-Fi/sin conexión, red activa, señal y redes disponibles.

Eventos: `nmcli monitor`. Las contraseñas nunca se guardan en el proyecto: se entregan a
NetworkManager por la entrada estándar de `nmcli --ask` y es NetworkManager quien las
almacena en su perfil de conexión (archivo de sistema legible solo por root o keyring).
"""
import asyncio

from ..daemon import Source
from ..util import Debouncer, have, log, run, split_nmcli, stream_lines

WIFI_GLYPHS = ["󰤯", "󰤟", "󰤢", "󰤥", "󰤨"]
WIFI_LOCK_GLYPHS = ["󰤬", "󰤡", "󰤤", "󰤧", "󰤪"]


def wifi_glyph(signal: int, locked: bool = False) -> str:
    table = WIFI_LOCK_GLYPHS if locked else WIFI_GLYPHS
    return table[min(4, max(0, signal // 20))]


def _secrets_missing(msg: str) -> bool:
    return "Secrets were required" in msg or "no secrets" in msg.lower() or "no-secrets" in msg


class NetworkSource(Source):
    topic = "network"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._refresh = Debouncer(0.3, self.refresh)
        self.status = ""
        self.error = ""
        self.busy = ""
        self.pending = ""  # SSID que espera contraseña
        self.scanning = False

    async def start(self) -> None:
        if not have("nmcli"):
            self.publish({"available": False, "error": "NetworkManager (nmcli) no está instalado"})
            return
        await self.refresh()
        await stream_lines(["nmcli", "monitor"], lambda _l: self._event(), name="nmcli monitor")

    async def _event(self) -> None:
        self._refresh()

    async def refresh(self) -> None:
        (_, devs, _), (_, radio, _), (_, wifi, _), (_, saved, _) = await asyncio.gather(
            run("nmcli", "-t", "-f", "TYPE,STATE,CONNECTION,DEVICE", "device"),
            run("nmcli", "radio", "wifi"),
            run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"),
            run("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"),
        )
        ethernet = wifi_dev = None
        has_wifi_hw = False
        for line in devs.splitlines():
            typ, state, conn, dev = (split_nmcli(line) + ["", "", "", ""])[:4]
            if typ == "wifi":
                has_wifi_hw = True
                if state == "connected":
                    wifi_dev = {"connection": conn, "device": dev}
            elif typ == "ethernet" and state == "connected":
                ethernet = {"connection": conn, "device": dev}

        known = {split_nmcli(l)[0] for l in saved.splitlines() if "wireless" in l}
        networks, seen, active_signal = [], set(), 0
        for line in wifi.splitlines():
            inuse, ssid, signal, security = (split_nmcli(line) + ["", "", "0", ""])[:4]
            if not ssid:
                continue
            sig = int(signal or 0)
            if inuse == "*":
                active_signal = sig
            if ssid in seen:
                continue
            seen.add(ssid)
            secure = bool(security and security != "--")
            networks.append({"ssid": ssid, "signal": sig, "secure": secure, "security": security,
                             "active": inuse == "*", "known": ssid in known,
                             "glyph": wifi_glyph(sig)})
        networks.sort(key=lambda n: (not n["active"], -n["signal"]))

        wifi_enabled = radio.strip() == "enabled"
        if ethernet:
            kind, glyph, label = "ethernet", "󰈀", "Online"
        elif wifi_dev:
            kind, glyph, label = "wifi", wifi_glyph(active_signal), "Online"
        elif has_wifi_hw and not wifi_enabled:
            kind, glyph, label = "disconnected", "󰤮", "Offline"
        else:
            kind, glyph, label = "disconnected", "󰤭", "Offline"

        self.publish({
            "available": True,
            "kind": kind, "glyph": glyph, "label": label,
            "ethernet": ethernet, "wifi": wifi_dev and {**wifi_dev, "signal": active_signal},
            "wifi_hw": has_wifi_hw, "wifi_enabled": wifi_enabled,
            "ssid": wifi_dev["connection"] if wifi_dev else "",
            "networks": networks[:12],
            "scanning": self.scanning, "busy": self.busy, "status": self.status, "error": self.error,
            "pending": self.pending,
        })

    def _set(self, status: str = "", error: str = "", busy: str = "") -> None:
        self.status, self.error, self.busy = status, error, busy
        self._refresh()

    # ---- órdenes -------------------------------------------------------------
    async def cmd_toggle_wifi(self) -> None:
        data = self.hub.get("network") or {}
        await run("nmcli", "radio", "wifi", "off" if data.get("wifi_enabled") else "on")

    async def cmd_scan(self) -> None:
        self.scanning = True
        self._refresh()
        code, _, err = await run("nmcli", "device", "wifi", "rescan", timeout=20)
        await asyncio.sleep(2.5)  # NetworkManager tarda en llenar los resultados
        self.scanning = False
        self._set(error="" if code == 0 else err.strip())

    async def cmd_connect(self, ssid: str) -> str:
        data = self.hub.get("network") or {}
        net = next((n for n in data.get("networks", []) if n["ssid"] == ssid), None)
        if net and net["known"]:
            self._set(busy=ssid, status=f"Conectando a {ssid}…")
            code, _, err = await run("nmcli", "connection", "up", "id", ssid, timeout=45)
            if code == 0:
                self._set(status=f"Conectado a {ssid}")
                return "ok"
            if _secrets_missing(err):
                # Perfil cuya contraseña guarda un agente (p. ej. KWallet de Plasma) que no corre en
                # esta sesión: NetworkManager no la obtiene. Se pide de nuevo y se recrea el perfil.
                self.pending = ssid
                self._set(status=f"Introduce la contraseña de {ssid}")
                return "password"
            self._set(error=err.strip())
            return err
        if net and net["secure"]:
            self.pending = ssid
            self._set(status=f"Introduce la contraseña de {ssid}")
            return "password"
        return await self._connect_new(ssid, None)

    async def cmd_password(self, ssid: str, password: str) -> str:
        self.pending = ""
        # Un perfil previo (olvidado a medias o con secretos de un agente ausente) haría que
        # `device wifi connect` lo reutilizara y volviera a fallar; se parte de cero.
        await self._delete_profiles(ssid)
        return await self._connect_new(ssid, password)

    async def cmd_cancel(self) -> None:
        self.pending = ""
        self._set()

    async def _connect_new(self, ssid: str, password: str | None) -> str:
        self._set(busy=ssid, status=f"Conectando a {ssid}…")
        # --ask: nmcli pide la contraseña por stdin; así no aparece en la lista de procesos.
        code, out, err = await run("nmcli", "--ask", "device", "wifi", "connect", ssid,
                                   stdin=(password + "\n") if password else "\n", timeout=60)
        if code == 0:
            self._set(status=f"Conectado a {ssid}")
            return "ok"
        msg = (err or out).strip().splitlines()[-1] if (err or out).strip() else "error desconocido"
        if _secrets_missing(msg) or "802-1x" in msg or "psk" in msg.lower():
            msg = "Contraseña incorrecta o rechazada"
            # nmcli crea un perfil aunque falle la autenticación; lo eliminamos para no dejar basura
            await self._delete_profiles(ssid)
        log(f"wifi: no se pudo conectar a {ssid}: {msg}")
        self._set(error=msg)
        return msg

    async def _delete_profiles(self, ssid: str) -> None:
        """Borra los perfiles Wi-Fi de ese SSID (el nombre del perfil puede no coincidir)."""
        _, out, _ = await run("nmcli", "-t", "-f", "UUID,TYPE", "connection", "show")
        for line in out.splitlines():
            uuid, typ = (split_nmcli(line) + ["", ""])[:2]
            if "wireless" not in typ:
                continue
            _, got, _ = await run("nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "uuid", uuid)
            if got.strip() == ssid:
                await run("nmcli", "connection", "delete", "uuid", uuid)

    async def cmd_disconnect(self) -> None:
        data = self.hub.get("network") or {}
        if data.get("wifi"):
            await run("nmcli", "device", "disconnect", data["wifi"]["device"])
        elif data.get("ethernet"):
            await run("nmcli", "device", "disconnect", data["ethernet"]["device"])

    async def cmd_editor(self) -> None:
        from ..util import spawn_detached
        spawn_detached("nm-connection-editor || kcmshell6 kcm_networkmanagement")
