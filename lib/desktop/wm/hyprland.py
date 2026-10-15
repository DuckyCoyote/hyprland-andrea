"""Adaptador para Hyprland (>= 0.56, configuración Lua; también acepta la sintaxis hyprlang).

Habla directamente con los sockets IPC (.socket.sock para consultas, .socket2.sock para
eventos) en lugar de lanzar `hyprctl` en cada evento.
"""
import asyncio
import json
import os
from pathlib import Path

from ..util import debug, have, log, run
from .base import OnChange, WindowManager

# Eventos de socket2 que cambian lo que muestra la barra
_WS_EVENTS = {"workspacev2", "createworkspacev2", "destroyworkspacev2", "moveworkspacev2",
              "openwindow", "closewindow", "movewindowv2", "renameworkspace", "activespecialv2"}
_MON_EVENTS = {"monitoraddedv2", "monitorremovedv2", "monitoradded", "monitorremoved", "configreloaded"}
_FOCUS_EVENTS = {"focusedmonv2", "activewindowv2", "windowtitlev2"}


class Hyprland(WindowManager):
    name = "hyprland"
    has_workspaces = True

    def __init__(self) -> None:
        sig = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        base = runtime / "hypr" / sig
        if not base.exists():  # versiones antiguas usaban /tmp/hypr
            base = Path("/tmp/hypr") / sig
        self.sock1 = str(base / ".socket.sock")
        self.sock2 = str(base / ".socket2.sock")
        self.urgent: set[int] = set()

    async def request(self, command: str) -> str:
        reader, writer = await asyncio.open_unix_connection(self.sock1)
        writer.write(command.encode())
        await writer.drain()
        data = await reader.read()
        writer.close()
        return data.decode(errors="replace")

    async def query(self, what: str):
        try:
            return json.loads(await self.request(f"j/{what}"))
        except (OSError, json.JSONDecodeError) as e:
            log(f"hyprland: fallo al consultar {what}: {e}")
            return []

    async def dispatch(self, lua: str, legacy: str) -> bool:
        """Intenta primero la sintaxis Lua (0.56+) y recurre a la clásica si la config es hyprlang."""
        def ok(reply: str) -> bool:
            return not (reply.startswith("error") or "Invalid" in reply or "Note:" in reply)

        reply = (await self.request(f"/dispatch {lua}")).strip()
        if ok(reply):
            return True
        reply2 = (await self.request(f"/dispatch {legacy}")).strip()
        if ok(reply2):
            return True
        log(f"hyprland dispatch falló: {reply} / {reply2}")
        return False

    async def start(self, on_change: OnChange) -> None:
        while True:
            writer = None
            try:
                # Hay que conservar `writer`: en Python >= 3.11 su recolección cierra el socket y
                # se pierden los eventos hasta reconectar (la barra se quedaba atrasada).
                reader, writer = await asyncio.open_unix_connection(self.sock2, limit=1 << 20)
                await on_change("workspaces")  # estado fresco tras (re)conectar
                while line := await reader.readline():
                    event, _, data = line.decode(errors="replace").strip().partition(">>")
                    if event == "urgent":
                        await self._mark_urgent(data)
                        await on_change("workspaces")
                    elif event in _WS_EVENTS:
                        if event == "workspacev2":
                            self.urgent.discard(_int(data.split(",")[0]))
                        await on_change("workspaces")
                    elif event in _MON_EVENTS:
                        await on_change("monitors")
                    elif event in _FOCUS_EVENTS:
                        await on_change("focus")
            except OSError as e:
                debug(f"hyprland socket2: {e}")
            finally:
                if writer:
                    writer.close()
            await asyncio.sleep(0.5)

    async def _mark_urgent(self, address: str) -> None:
        for c in await self.query("clients"):
            if c.get("address", "").removeprefix("0x") == address.removeprefix("0x"):
                self.urgent.add(c["workspace"]["id"])

    async def monitors(self) -> list[dict]:
        mons = await self.query("monitors")
        models = [m.get("model", "") for m in mons]
        out = []
        for m in mons:
            model = m.get("model", "")
            out.append({
                "name": m["name"],
                "model": model,
                # Eww (GTK) identifica monitores por modelo; si dos monitores comparten
                # modelo recurrimos al índice, que GTK ordena igual que el compositor.
                "screen": model if model and models.count(model) == 1 else m.get("id", 0),
                "description": m.get("description", ""),
                "width": m.get("width", 0), "height": m.get("height", 0),
                "refresh": round(m.get("refreshRate", 0)), "scale": m.get("scale", 1),
                "x": m.get("x", 0), "y": m.get("y", 0),
                "focused": bool(m.get("focused")),
                "active_workspace": m.get("activeWorkspace", {}).get("id"),
            })
        return out

    async def workspaces(self) -> list[dict]:
        out = []
        for w in await self.query("workspaces"):
            if w.get("id", 0) <= 0:  # especiales (scratchpads)
                continue
            out.append({"id": w["id"], "name": w.get("name", str(w["id"])), "monitor": w.get("monitor"),
                        "windows": w.get("windows", 0), "urgent": w["id"] in self.urgent})
        return out

    async def active_windows(self) -> dict[str, dict]:
        visible = {m.get("activeWorkspace", {}).get("id"): m["name"] for m in await self.query("monitors")}
        best: dict[str, dict] = {}
        for c in await self.query("clients"):
            mon = visible.get(c.get("workspace", {}).get("id"))
            if mon is None or not c.get("mapped", True) or c.get("hidden"):
                continue
            # focusHistoryID: 0 = ventana enfocada; menor = usada más recientemente
            if mon not in best or c.get("focusHistoryID", 1 << 30) < best[mon].get("focusHistoryID", 1 << 30):
                best[mon] = c
        return {mon: {"class": c.get("class") or c.get("initialClass", ""), "title": c.get("title", "")}
                for mon, c in best.items()}

    async def focus_workspace(self, workspace_id: int) -> None:
        await self.dispatch(f"hl.dsp.focus({{ workspace = {int(workspace_id)} }})", f"workspace {int(workspace_id)}")

    async def popup_mode(self, enabled: bool, mode: str = "popup") -> None:
        submap = f"hd-{mode}" if enabled else "reset"
        await self.dispatch(f'hl.dsp.submap("{submap}")', f"submap {submap}")

    async def clients(self) -> list[dict]:
        names = {m["id"]: m["name"] for m in await self.query("monitors")}
        out = []
        for c in await self.query("clients"):
            if not c.get("mapped", True) or c.get("hidden"):
                continue
            ws = c.get("workspace", {})
            out.append({
                "address": c["address"], "class": c.get("class") or c.get("initialClass", ""),
                "title": c.get("title", ""), "workspace": ws.get("id", 0), "workspace_name": ws.get("name", ""),
                "monitor": names.get(c.get("monitor"), ""), "minimized": ws.get("id", 0) < 0,
                "order": c.get("focusHistoryID", 1 << 30),
            })
        return sorted(out, key=lambda c: c["order"])

    async def focus_window(self, address: str) -> None:
        win = next((c for c in await self.clients() if c["address"] == address), None)
        if not win:
            return
        sel = f'"address:{address}"'
        if win["minimized"]:  # en el espacio especial «minimized»: traerla al espacio visible
            active = (await self.query("activeworkspace")) or {}
            await self.dispatch(f'hl.dsp.window.move({{ workspace = {int(active.get("id", 1))}, window = {sel} }})',
                                f"movetoworkspace {active.get('id', 1)},address:{address}")
        await self.dispatch(f"hl.dsp.focus({{ window = {sel} }})", f"focuswindow address:{address}")

    async def layers_per_monitor(self, namespace: str) -> dict[str, int] | None:
        layers = await self.query("layers")
        if not isinstance(layers, dict):
            return None
        return {name: sum(1 for level in mon.get("levels", {}).values()
                          for layer in level if layer.get("namespace") == namespace)
                for name, mon in layers.items()}

    async def set_cursor(self, theme: str, size: int) -> None:
        await self.request(f"/setcursor {theme} {int(size)}")

    async def reload(self) -> None:
        await self.request("/reload")

    async def logout(self) -> None:
        if have("hyprshutdown"):
            await run("hyprshutdown")
        else:
            await self.dispatch("hl.dsp.exit()", "exit")


def _int(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return 0
