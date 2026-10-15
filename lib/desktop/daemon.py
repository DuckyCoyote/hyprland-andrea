"""desktopd: controlador central de estado.

Un único proceso recoge los eventos del sistema (compositor, PipeWire, NetworkManager,
MPRIS...) y publica el estado de cada dominio en un socket Unix por tema:

    $XDG_RUNTIME_DIR/hyprland-desktop/<tema>.sock

Conectarse a un socket de tema = suscribirse: se recibe el estado actual como una línea
JSON y después una línea por cada cambio. Eww se suscribe con `deflisten` mediante
bin/desktop-sub, de modo que hay exactamente un productor por dominio sin importar
cuántos monitores o barras existan.

Las órdenes llegan por ctl.sock como {"argv": [...]} y se responden con {"ok", "msg"}.
"""
import asyncio
import json
import os
import signal

from . import paths
from .util import log


class Source:
    """Fuente de estado. Las subclases definen `topic`, `start()` y métodos `cmd_<orden>`."""

    topic = ""

    def __init__(self, hub: "Hub") -> None:
        self.hub = hub

    async def start(self) -> None:
        """Arranque. Puede retornar enseguida o ejecutarse indefinidamente."""

    def publish(self, data) -> None:
        self.hub.publish(self.topic, data)

    def commands(self) -> dict:
        return {name[4:].replace("_", "-"): getattr(self, name) for name in dir(self) if name.startswith("cmd_")}


class Hub:
    def __init__(self) -> None:
        self.state: dict[str, str] = {}
        self.subs: dict[str, set[asyncio.StreamWriter]] = {}
        self.sources: dict[str, Source] = {}
        self.servers = []

    def add(self, source: Source) -> Source:
        self.sources[source.topic] = source
        self.subs.setdefault(source.topic, set())
        return source

    def get(self, topic: str):
        raw = self.state.get(topic)
        return json.loads(raw) if raw else None

    def publish(self, topic: str, data) -> None:
        line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if self.state.get(topic) == line:
            return  # sin cambios: no despertamos a Eww
        self.state[topic] = line
        payload = (line + "\n").encode()
        for w in list(self.subs.get(topic, ())):
            try:
                w.write(payload)
            except Exception:
                self.subs[topic].discard(w)

    async def _serve_topic(self, topic: str) -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            self.subs[topic].add(writer)
            if topic in self.state:
                writer.write((self.state[topic] + "\n").encode())
            try:
                await reader.read()  # esperamos a que el suscriptor se desconecte
            except Exception:
                pass
            finally:
                self.subs[topic].discard(writer)
                writer.close()

        path = paths.socket_path(topic)
        path.unlink(missing_ok=True)
        self.servers.append(await asyncio.start_unix_server(handler, str(path)))

    async def _serve_ctl(self) -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                req = json.loads((await reader.readline()).decode() or "{}")
                ok, msg = await self.execute(req.get("argv", []))
            except Exception as e:
                ok, msg = False, f"error interno: {e!r}"
            writer.write((json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False) + "\n").encode())
            await writer.drain()
            writer.close()

        path = paths.socket_path("ctl")
        path.unlink(missing_ok=True)
        self.servers.append(await asyncio.start_unix_server(handler, str(path)))

    async def execute(self, argv: list[str]) -> tuple[bool, str]:
        if len(argv) < 2:
            return False, "uso: <tema> <orden> [argumentos]"
        topic, cmd, args = argv[0], argv[1], argv[2:]
        source = self.sources.get(topic)
        if not source:
            return False, f"tema desconocido: {topic}"
        fn = source.commands().get(cmd)
        if not fn:
            return False, f"orden desconocida para {topic}: {cmd}. Disponibles: {', '.join(sorted(source.commands()))}"
        try:
            result = await fn(*args)
        except TypeError as e:
            return False, f"argumentos incorrectos: {e}"
        return True, "" if result is None else str(result)

    async def run(self) -> None:
        paths.ensure_dirs()
        for topic in self.sources:
            await self._serve_topic(topic)
        await self._serve_ctl()
        (paths.RUNTIME_DIR / "desktopd.pid").write_text(str(os.getpid()))
        log(f"desktopd escuchando en {paths.RUNTIME_DIR} ({', '.join(self.sources)})")

        async def guarded(source: Source) -> None:
            try:
                await source.start()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"fuente {source.topic} falló al iniciar: {e!r}")

        tasks = [asyncio.create_task(guarded(s)) for s in self.sources.values()]
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        await stop.wait()
        for t in tasks:
            t.cancel()
        for s in self.servers:
            s.close()
        for topic in [*self.sources, "ctl"]:
            paths.socket_path(topic).unlink(missing_ok=True)
        (paths.RUNTIME_DIR / "desktopd.pid").unlink(missing_ok=True)


def build_hub() -> Hub:
    from .sources import all_sources
    hub = Hub()
    for cls in all_sources():
        hub.add(cls(hub))
    return hub


def _single_instance():
    """Bloqueo exclusivo: si ya hay un desktopd (o otro arrancando a la vez), salimos."""
    import fcntl
    paths.ensure_dirs()
    lock = open(paths.RUNTIME_DIR / "desktopd.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("desktopd ya está en ejecución")
    return lock  # mantener la referencia mientras viva el proceso


def main() -> None:
    lock = _single_instance()  # noqa: F841
    # Los widgets y accesos rápidos invocan `desktopctl` por nombre.
    os.environ["PATH"] = f"{paths.ROOT / 'bin'}:{os.environ.get('PATH', '/usr/bin')}"
    asyncio.run(build_hub().run())
