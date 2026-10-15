"""Tema `notifications`: servidor de notificaciones (org.freedesktop.Notifications).

Sustituye a mako/dunst para que las notificaciones usen el mismo sistema visual que la barra:
- Avisos emergentes arriba a la derecha, debajo de la barra (ventana `notify_toasts`).
- Bandeja / centro de notificaciones con historial, «no molestar» y acciones (popup `notifications`).

El servidor D-Bus corre en un hilo con su propio bucle GLib (Gio); los eventos se pasan al
bucle asyncio del daemon con call_soon_threadsafe. Especificación:
https://specifications.freedesktop.org/notification-spec/latest/
"""
import asyncio
import hashlib
import threading
import time

from .. import config, eww, paths
from ..daemon import Source
from ..util import log

BUS_NAME = "org.freedesktop.Notifications"
OBJ_PATH = "/org/freedesktop/Notifications"
IFACE_XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="GetCapabilities"><arg direction="out" type="as"/></method>
    <method name="Notify">
      <arg direction="in" type="s"/><arg direction="in" type="u"/><arg direction="in" type="s"/>
      <arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="as"/>
      <arg direction="in" type="a{sv}"/><arg direction="in" type="i"/>
      <arg direction="out" type="u"/>
    </method>
    <method name="CloseNotification"><arg direction="in" type="u"/></method>
    <method name="GetServerInformation">
      <arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/>
    </method>
    <signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
    <signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
  </interface>
</node>
"""
# Motivos de cierre según la especificación
EXPIRED, DISMISSED, CLOSED_BY_CALL = 1, 2, 3
DEFAULT_TIMEOUT = 6000
MAX_TOASTS = 4
MAX_HISTORY = 50
TOASTS_WINDOW = "notify_toasts"


class NotificationsSource(Source):
    topic = "notifications"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.items: dict[int, dict] = {}       # todas (historial), por id
        self.toasts: list[int] = []            # ids visibles como aviso
        self.timers: dict[int, asyncio.TimerHandle] = {}
        self.next_id = 1
        self.dnd = bool(config.read_state(paths.UI_STATE, {}).get("dnd", False))
        self.conn = None
        self.owned = False
        self.toast_monitor = ""
        self.icon_dir = paths.CACHE_DIR / "notify-icons"
        self._icons = None

    # ---- servidor D-Bus (hilo GLib) -------------------------------------------
    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.icon_dir.mkdir(parents=True, exist_ok=True)
        self._publish()
        threading.Thread(target=self._glib_thread, name="notifications-dbus", daemon=True).start()

    def _glib_thread(self) -> None:
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib
        except Exception as e:
            log(f"notificaciones: PyGObject no disponible ({e})")
            return
        self.Gio, self.GLib = Gio, GLib
        ctx = GLib.MainContext.new()
        ctx.push_thread_default()
        node = Gio.DBusNodeInfo.new_for_xml(IFACE_XML)

        def on_bus(conn, _name):
            self.conn = conn
            conn.register_object(OBJ_PATH, node.interfaces[0], self._on_call, None, None)

        def on_acquired(_conn, _name):
            self.owned = True
            log("notificaciones: servidor activo en org.freedesktop.Notifications")
            self.loop.call_soon_threadsafe(self._publish)

        def on_lost(_conn, _name):
            self.owned = False
            log("notificaciones: el nombre D-Bus pertenece a otro daemon (¿mako, dunst o Plasma?)")
            self.loop.call_soon_threadsafe(self._publish)

        Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.REPLACE,
                         on_bus, on_acquired, on_lost)
        GLib.MainLoop.new(ctx, False).run()

    def _on_call(self, _conn, sender, _path, _iface, method, params, invocation):
        GLib = self.GLib
        if method == "GetCapabilities":
            invocation.return_value(GLib.Variant("(as)", (["body", "body-markup", "actions", "icon-static", "persistence"],)))
        elif method == "GetServerInformation":
            invocation.return_value(GLib.Variant("(ssss)", ("hyprland-desktop", "hyprland-desktop", "1.0", "1.2")))
        elif method == "CloseNotification":
            (nid,) = params.unpack()
            self.loop.call_soon_threadsafe(self._close, nid, CLOSED_BY_CALL)
            invocation.return_value(None)
        elif method == "Notify":
            app, replaces, icon, summary, body, actions, hints, timeout = params.unpack()
            nid = replaces if replaces else self._new_id()
            note = self._build(nid, app, icon, summary, body, actions, hints, timeout)
            self.loop.call_soon_threadsafe(self._add, note)
            invocation.return_value(GLib.Variant("(u)", (nid,)))

    def _new_id(self) -> int:
        nid = self.next_id
        self.next_id += 1
        return nid

    def _build(self, nid, app, icon, summary, body, actions, hints, timeout) -> dict:
        urgency = int(hints.get("urgency", 1)) if isinstance(hints.get("urgency"), int) else 1
        image = self._image(icon, hints)
        pairs = [{"key": actions[i], "label": actions[i + 1]} for i in range(0, len(actions) - 1, 2)]
        return {
            "id": nid, "app": app or "Aplicación", "summary": _wrap(_plain(summary), 32, 2),
            "body": _wrap(_plain(body), 38, 4),
            "image": image, "urgency": urgency, "time": time.strftime("%H:%M"), "ts": time.time(),
            "actions": [a for a in pairs if a["key"] != "default"],
            "has_default": any(a["key"] == "default" for a in pairs),
            "timeout": timeout, "transient": bool(hints.get("transient", False)),
            "glyph": "" if image else ("󰀦" if urgency == 2 else "󰂚"),
        }

    def _image(self, icon: str, hints: dict) -> str:
        """Ruta de imagen a partir de image-data, image-path o app_icon."""
        data = hints.get("image-data") or hints.get("image_data") or hints.get("icon_data")
        if data:
            try:
                w, h, stride, alpha, _bps, _ch, pixels = data
                raw = bytes(pixels)
                target = self.icon_dir / (hashlib.sha1(raw[:4096] + bytes(str((w, h)), "ascii")).hexdigest() + ".png")
                if not target.exists():
                    import gi
                    gi.require_version("GdkPixbuf", "2.0")
                    from gi.repository import GdkPixbuf, GLib
                    pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw), GdkPixbuf.Colorspace.RGB, alpha, 8, w, h, stride)
                    pb.savev(str(target), "png", [], [])
                return str(target)
            except Exception as e:
                log(f"notificaciones: image-data no válida ({e})")
        for candidate in (hints.get("image-path"), hints.get("image_path"), icon):
            if not candidate:
                continue
            if candidate.startswith("file://"):
                candidate = candidate[7:]
            if candidate.startswith("/"):
                return candidate
            if self._icons is None:
                from .apps import IconResolver
                self._icons = IconResolver()
            found = self._icons.lookup(candidate, 48)
            if found and not found.endswith("application-x-executable.svg"):
                return found
        return ""

    # ---- estado (bucle asyncio) ---------------------------------------------------
    def _add(self, note: dict) -> None:
        nid = note["id"]
        self.items[nid] = note
        if not (self.dnd and note["urgency"] < 2):
            if nid not in self.toasts:
                self.toasts.insert(0, nid)
            for old in self.toasts[MAX_TOASTS:]:
                self._expire_toast(old)
            timeout = note["timeout"]
            if timeout < 0:
                timeout = 0 if note["urgency"] == 2 else DEFAULT_TIMEOUT
            if nid in self.timers:
                self.timers.pop(nid).cancel()
            if timeout > 0:
                self.timers[nid] = self.loop.call_later(timeout / 1000, self._expire_toast, nid)
        # historial acotado (las transitorias no se guardan)
        if len(self.items) > MAX_HISTORY:
            for old in sorted(self.items, key=lambda i: self.items[i]["ts"])[:len(self.items) - MAX_HISTORY]:
                self.items.pop(old, None)
        self._publish()
        self.loop.create_task(self._sync_window())

    def _expire_toast(self, nid: int) -> None:
        """El aviso desaparece pero la notificación sigue en la bandeja."""
        if nid in self.toasts:
            self.toasts.remove(nid)
        self.timers.pop(nid, None)
        note = self.items.get(nid)
        if note and note["transient"]:
            self._close(nid, EXPIRED)
            return
        self._publish()
        self.loop.create_task(self._sync_window())

    def _close(self, nid: int, reason: int) -> None:
        self.items.pop(nid, None)
        if nid in self.toasts:
            self.toasts.remove(nid)
        if nid in self.timers:
            self.timers.pop(nid).cancel()
        self._emit("NotificationClosed", "(uu)", (nid, reason))
        self._publish()
        self.loop.create_task(self._sync_window())

    def _emit(self, signal: str, sig: str, args: tuple) -> None:
        if self.conn is None:
            return
        conn, GLib = self.conn, self.GLib
        conn.emit_signal(None, OBJ_PATH, BUS_NAME, signal, GLib.Variant(sig, args))

    def _publish(self) -> None:
        history = sorted(self.items.values(), key=lambda n: -n["ts"])
        self.publish({
            "server": self.owned, "dnd": self.dnd, "count": len(history),
            "toasts": [self.items[i] for i in self.toasts if i in self.items],
            "history": history,
        })

    async def _sync_window(self) -> None:
        """Abre la ventana de avisos en el monitor enfocado cuando hay avisos; la cierra si no."""
        active = await asyncio.to_thread(eww.active_windows)
        if self.toasts and TOASTS_WINDOW not in active:
            wm = self.hub.sources["wm"]
            monitor = await wm.wm.focused_monitor()
            await asyncio.to_thread(eww.open_window, TOASTS_WINDOW, TOASTS_WINDOW, wm.screen_of(monitor))
        elif not self.toasts and TOASTS_WINDOW in active:
            await asyncio.to_thread(eww.close, TOASTS_WINDOW)

    # ---- órdenes -------------------------------------------------------------
    async def cmd_dismiss(self, nid: str) -> None:
        self._close(int(nid), DISMISSED)

    async def cmd_hide(self, nid: str) -> None:
        """Quita el aviso emergente pero conserva la notificación en la bandeja."""
        self._expire_toast(int(nid))

    async def cmd_action(self, nid: str, key: str = "default") -> None:
        self._emit("ActionInvoked", "(us)", (int(nid), key))
        self._close(int(nid), DISMISSED)

    async def cmd_clear(self) -> None:
        for nid in list(self.items):
            self._close(nid, DISMISSED)

    async def cmd_dnd(self, value: str = "toggle") -> str:
        self.dnd = (not self.dnd) if value == "toggle" else value in ("on", "true", "1")
        state = config.read_state(paths.UI_STATE, {})
        state["dnd"] = self.dnd
        config.write_json(paths.UI_STATE, state)
        if self.dnd:
            for nid in list(self.toasts):
                if self.items.get(nid, {}).get("urgency", 1) < 2:
                    self._expire_toast(nid)
        self._publish()
        return "no molestar " + ("activado" if self.dnd else "desactivado")

    async def cmd_test(self) -> None:
        """Envía notificaciones de prueba (útil para verificar estilos)."""
        self._add(self._build(self._new_id(), "hyprland-desktop", "dialog-information", "Notificación de prueba",
                              "Así se ven los avisos: arriba a la izquierda, debajo de la barra.", [], {}, -1))


def _wrap(text: str, width: int, max_lines: int) -> str:
    """Parte el texto en líneas (Eww no ajusta etiquetas de forma fiable dentro de cajas)."""
    import textwrap
    lines = []
    for paragraph in text.splitlines() or [""]:
        lines += textwrap.wrap(paragraph, width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return "\n".join(lines).strip()


def _plain(text: str) -> str:
    """Quita el marcado básico permitido por la especificación (b, i, u, a, img)."""
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")
