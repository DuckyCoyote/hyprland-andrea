"""Tema `media`: reproductores MPRIS mediante playerctl.

Un único `playerctl --all-players --follow` notifica cualquier cambio de cualquier
reproductor. Selección del reproductor mostrado: el elegido por el usuario si sigue
existiendo; si no, el que esté reproduciendo; si no, el último que cambió.
"""
import asyncio
import hashlib
import time
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from .. import paths
from ..daemon import Source
from ..util import Debouncer, have, run, stream_lines

SEP = "\x1f"
FIELDS = ["player", "status", "title", "artist", "album", "art", "length"]
FORMAT = SEP.join("{{%s}}" % f for f in ["playerName", "status", "title", "artist", "album", "mpris:artUrl", "mpris:length"])

PLAYER_ICONS = {"spotify": "", "firefox": "󰈹", "chromium": "", "chrome": "", "brave": "󰖟",
                "mpv": "", "vlc": "󰕼", "kdeconnect": "󰄜", "plasma-browser-integration": "󰖟"}


class MediaSource(Source):
    topic = "media"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.players: dict[str, dict] = {}
        self.selected = ""
        self._refresh = Debouncer(0.1, self.refresh_all)
        self.cover_dir = paths.CACHE_DIR / "covers"

    async def start(self) -> None:
        if not have("playerctl"):
            self.publish({"available": False, "error": "playerctl no está instalado"})
            return
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        await self.refresh_all()
        await stream_lines(["playerctl", "--all-players", "--follow", "metadata", "--format", FORMAT],
                           self._on_line, name="playerctl")

    async def _on_line(self, line: str) -> None:
        # Una línea vacía indica que un reproductor desapareció: re-listamos todo.
        if not line.strip(SEP).strip():
            self._refresh()
            return
        info = dict(zip(FIELDS, line.split(SEP)))
        name = info.get("player", "")
        if name:
            prev = self.players.get(name, {})
            self.players[name] = {**prev, **info, "changed": time.monotonic()}
            if prev.get("art") != info.get("art"):
                self.players[name]["cover"] = await self._cover(info.get("art", ""))
            await self._publish()

    async def refresh_all(self) -> None:
        code, out, _ = await run("playerctl", "--list-all")
        names = [n for n in out.split() if n] if code == 0 else []
        for gone in set(self.players) - set(names):
            del self.players[gone]
        for name in names:
            c, line, _ = await run("playerctl", "-p", name, "metadata", "--format", FORMAT)
            if c == 0 and line.strip():
                info = dict(zip(FIELDS, line.rstrip("\n").split(SEP)))
                prev = self.players.get(name, {})
                self.players[name] = {**prev, **info, "changed": prev.get("changed", 0)}
                if prev.get("art") != info.get("art") or "cover" not in prev:
                    self.players[name]["cover"] = await self._cover(info.get("art", ""))
        await self._publish()

    def _current(self) -> str:
        if self.selected in self.players:
            return self.selected
        playing = [n for n, p in self.players.items() if p.get("status") == "Playing"]
        pool = playing or list(self.players)
        return max(pool, key=lambda n: self.players[n].get("changed", 0)) if pool else ""

    async def _publish(self) -> None:
        name = self._current()
        if not name:
            self.publish({"available": True, "active": False, "players": []})
            return
        p = self.players[name]
        # el panel lee la posición con `playerctl -p <este reproductor> position` mientras está abierto
        (paths.RUNTIME_DIR / "media-player").write_text(name)
        shuffle, loop = await asyncio.gather(run("playerctl", "-p", name, "shuffle"), run("playerctl", "-p", name, "loop"))
        try:
            length = int(p.get("length") or 0) // 1_000_000
        except ValueError:
            length = 0
        base = name.split(".")[0].lower()
        self.publish({
            "available": True, "active": True,
            "player": name, "player_label": base.capitalize(), "player_icon": PLAYER_ICONS.get(base, "󰝚"),
            "status": p.get("status", ""), "playing": p.get("status") == "Playing",
            "title": p.get("title") or "Sin título", "artist": p.get("artist") or "", "album": p.get("album") or "",
            "cover": p.get("cover", ""), "length": length, "length_str": _fmt(length),
            "shuffle_supported": shuffle[0] == 0, "shuffle": shuffle[1].strip() == "On",
            "loop_supported": loop[0] == 0, "loop": loop[1].strip() if loop[0] == 0 else "None",
            "players": [{"name": n, "label": n.split(".")[0].capitalize(),
                         "icon": PLAYER_ICONS.get(n.split(".")[0].lower(), "󰝚"), "selected": n == name}
                        for n in sorted(self.players)],
        })

    async def _cover(self, url: str) -> str:
        """Devuelve una ruta local a la carátula (descargándola a caché si es remota)."""
        if not url:
            return ""
        if url.startswith("file://"):
            return unquote(urlparse(url).path)
        if url.startswith(("http://", "https://")):
            target = self.cover_dir / (hashlib.sha1(url.encode()).hexdigest() + ".img")
            if not target.exists():
                try:
                    data = await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=8).read())
                    target.write_bytes(data)
                    _prune(self.cover_dir, keep=60)
                except Exception:
                    return ""
            return str(target)
        return ""

    # ---- órdenes -------------------------------------------------------------
    async def _ctl(self, *args: str) -> None:
        name = self._current()
        if name:
            await run("playerctl", "-p", name, *args)
            self._refresh()

    async def cmd_toggle(self) -> None:
        await self._ctl("play-pause")

    async def cmd_next(self) -> None:
        await self._ctl("next")

    async def cmd_previous(self) -> None:
        await self._ctl("previous")

    async def cmd_shuffle(self) -> None:
        await self._ctl("shuffle", "toggle")

    async def cmd_loop(self) -> None:
        data = self.hub.get("media") or {}
        nxt = {"None": "Playlist", "Playlist": "Track", "Track": "None"}.get(data.get("loop", "None"), "None")
        await self._ctl("loop", nxt)

    async def cmd_seek(self, percent: str) -> None:
        data = self.hub.get("media") or {}
        if data.get("length"):
            await self._ctl("position", str(int(float(percent) / 100 * data["length"])))

    async def cmd_select(self, name: str) -> None:
        self.selected = name
        await self._publish()

    async def cmd_cycle(self) -> None:
        names = sorted(self.players)
        if names:
            cur = self._current()
            self.selected = names[(names.index(cur) + 1) % len(names)] if cur in names else names[0]
            await self._publish()


def _fmt(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else "0:00"


def _prune(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("*.img"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[keep:]:
        f.unlink(missing_ok=True)
