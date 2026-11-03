"""Tema `recon`: datos de trabajo para pentesting y bug bounty (barra «Cyber»).

- vpn: primera interfaz de túnel con IPv4 (tun*/tap*/wg*/ppp*: OpenVPN de HTB/THM, WireGuard…).
- lan: IPv4 de la interfaz de la ruta por defecto.
- target: objetivo fijado a mano (IP, CIDR o dominio, con puerto opcional) con un nombre opcional, y
  si responde: a ping, o con puerto, si el puerto acepta conexiones TCP.

Eventos: `ip monitor address route`. El objetivo se guarda en ~/.local/state/hyprland-desktop/
target.json y, en texto plano, en …/target (solo el host, para nmap y compañía) y …/target-port
(si hay puerto) para que la terminal lo lea: `set -gx TARGET (cat ~/.local/state/hyprland-desktop/target)`.
"""
import asyncio
import json
import re
import subprocess

from .. import config, paths
from ..daemon import Source
from ..util import Debouncer, have, notify, run, stream_lines

TUNNEL_PREFIXES = ("tun", "tap", "wg", "ppp")
PING_EVERY = 15  # segundos entre comprobaciones del objetivo
TARGET_STATE = paths.STATE_DIR / "target.json"
TARGET_PLAIN = paths.STATE_DIR / "target"
TARGET_PORT = paths.STATE_DIR / "target-port"
# IPv4 (con máscara opcional) o nombre de host: nunca se pasa a un shell, pero se valida igual
TARGET_RE = re.compile(r"^(\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?|[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)$")


def parse_target(text: str) -> tuple[str, str] | None:
    """(host, puerto) de «10.10.11.42», «10.10.11.42:8080», «app.htb:443», «10.10.0.0/24» o de una
    URL («https://app.example.com:8443/login» → app.example.com, 8443). None si no es válido."""
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text.strip(), flags=re.I)
    if TARGET_RE.match(text):  # IP, CIDR o dominio sin más
        return text, ""
    host_port = text.split("/")[0].split("@")[-1]  # sin ruta ni usuario:contraseña@
    host, _, port = host_port.partition(":")
    if not TARGET_RE.match(host) or (port and not (port.isdigit() and 0 < int(port) < 65536)):
        return None
    return host, port


def _ipv4(addr_info: list) -> str:
    return next((a.get("local", "") for a in addr_info if a.get("family") == "inet"), "")


class ReconSource(Source):
    topic = "recon"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self._refresh = Debouncer(0.3, self.refresh)
        self.vpn = {"active": False, "iface": "", "ip": ""}
        self.lan = {"iface": "", "ip": ""}
        self.target = config.read_state(TARGET_STATE, {})
        self.alive: bool | None = None
        self._wake = asyncio.Event()

    async def start(self) -> None:
        if not have("ip"):
            self.publish({"available": False})
            return
        await self.refresh()
        asyncio.get_running_loop().create_task(self._ping_loop())
        await stream_lines(["ip", "monitor", "address", "route"], lambda _l: self._event(), name="ip monitor")

    async def _event(self) -> None:
        self._refresh()

    async def refresh(self) -> None:
        (_, addrs, _), (_, routes, _) = await asyncio.gather(
            run("ip", "-j", "-4", "addr", "show"), run("ip", "-j", "-4", "route", "show", "default"))
        try:
            links, default = json.loads(addrs or "[]"), json.loads(routes or "[]")
        except json.JSONDecodeError:
            return
        by_name = {l.get("ifname", ""): _ipv4(l.get("addr_info", [])) for l in links}
        tun = next((n for n, ip in by_name.items() if n.startswith(TUNNEL_PREFIXES) and ip), "")
        self.vpn = {"active": bool(tun), "iface": tun, "ip": by_name.get(tun, "")}
        # con la VPN completa la ruta por defecto puede ir por el túnel: la LAN es la primera que no lo sea
        dev = next((r.get("dev", "") for r in default if not r.get("dev", "").startswith(TUNNEL_PREFIXES)), "")
        self.lan = {"iface": dev, "ip": by_name.get(dev, "")}
        self._publish()

    def _publish(self) -> None:
        t = self.target or {}
        self.publish({
            "available": True,
            "vpn": self.vpn,
            "lan": self.lan,
            "target": {"set": bool(t.get("ip")), "ip": t.get("ip", ""), "port": t.get("port", ""),
                       "addr": _addr(t), "name": t.get("name", ""),
                       "alive": self.alive is True, "checked": self.alive is not None},
        })

    async def _ping_loop(self) -> None:
        while True:
            t = self.target or {}
            ip, port = t.get("ip", "").split("/")[0], t.get("port", "")
            alive = None
            if ip and port:  # con puerto: ¿acepta conexiones? (muchas máquinas Windows no responden a ping)
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_connection(ip, int(port)), 3)
                    writer.close()
                    alive = True
                except (OSError, asyncio.TimeoutError):
                    alive = False
            elif ip and have("ping"):
                code, _, _ = await run("ping", "-c", "1", "-W", "2", ip, timeout=5)
                alive = code == 0
            if alive is not None and alive != self.alive:
                    self.alive = alive
                    self._publish()
            self._wake.clear()
            try:  # un objetivo nuevo se comprueba al momento
                await asyncio.wait_for(self._wake.wait(), PING_EVERY)
            except asyncio.TimeoutError:
                pass

    def _save_target(self, target: dict) -> None:
        self.target, self.alive = target, None
        if target:
            config.write_json(TARGET_STATE, target)
            TARGET_PLAIN.write_text(target["ip"] + "\n")
            if target.get("port"):
                TARGET_PORT.write_text(target["port"] + "\n")
            else:
                TARGET_PORT.unlink(missing_ok=True)
        else:
            for f in (TARGET_STATE, TARGET_PLAIN, TARGET_PORT):
                f.unlink(missing_ok=True)
        self._wake.set()
        self._publish()

    # ---- órdenes -------------------------------------------------------------
    async def cmd_target(self, ip: str, *name: str) -> str:
        """Fija el objetivo: `recon target 10.10.11.42[:puerto] [nombre de la máquina]`."""
        parsed = parse_target(ip)
        if not parsed:
            return f"objetivo no válido: {ip}"
        host, port = parsed
        self._save_target({"ip": host, "port": port, "name": " ".join(name).strip()[:32]})
        return f"objetivo = {_addr(self.target)}"

    async def cmd_target_paste(self) -> str:
        """Toma el objetivo del portapapeles: la primera IP o dominio que contenga, con su puerto
        si lo trae (10.10.11.42:8080, http://app.htb:3000/login…)."""
        _, text, _ = await run("wl-paste", "--no-newline", timeout=3)
        for token in re.split(r"[\s,;'\"<>()\[\]]+", text):
            parsed = parse_target(token)
            if parsed and "." in parsed[0]:
                return await self.cmd_target(parsed[0] + (f":{parsed[1]}" if parsed[1] else ""))
        notify("Objetivo", "El portapapeles no contiene una IP ni un dominio")
        return "el portapapeles no contiene una IP ni un dominio"

    async def cmd_target_clear(self) -> str:
        self._save_target({})
        return "objetivo borrado"

    async def cmd_copy(self, what: str) -> str:
        """Copia al portapapeles vpn | lan | target."""
        value = {"vpn": self.vpn.get("ip"), "lan": self.lan.get("ip"),
                 "target": _addr(self.target or {})}.get(what, "")
        if not value:
            return f"nada que copiar: {what}"
        if not have("wl-copy"):
            return "wl-copy no está instalado"
        # wl-copy se queda en segundo plano sirviendo el portapapeles: no se espera su salida
        p = subprocess.Popen(["wl-copy", "--trim-newline"], stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        p.communicate(value.encode())
        notify("Copiado", f"{what.upper()} {value}")
        return value

    async def cmd_refresh(self) -> None:
        await self.refresh()


def _addr(target: dict) -> str:
    """host[:puerto] tal como se muestra y se copia."""
    if not target.get("ip"):
        return ""
    return target["ip"] + (f":{target['port']}" if target.get("port") else "")
