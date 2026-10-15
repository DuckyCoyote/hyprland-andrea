"""Utilidades compartidas: procesos, debounce, registro y terminal."""
import asyncio
import os
import shlex
import shutil
import subprocess
import sys
import time

DEBUG = bool(os.environ.get("DESKTOP_DEBUG"))


def log(*args) -> None:
    print(time.strftime("%H:%M:%S"), *args, file=sys.stderr, flush=True)


def debug(*args) -> None:
    if DEBUG:
        log("[debug]", *args)


def have(binary: str) -> bool:
    return shutil.which(binary) is not None


async def run(*cmd: str, timeout: float = 15, stdin: str | None = None, env: dict | None = None) -> tuple[int, str, str]:
    """Ejecuta un comando sin shell. Devuelve (código, stdout, stderr). Nunca lanza por comando ausente."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **(env or {})},
        )
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: no encontrado"
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode() if stdin is not None else None), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"{cmd[0]}: tiempo de espera agotado"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


def run_sync(*cmd: str, timeout: float = 10) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""


def spawn_detached(command: str) -> None:
    """Lanza un comando de shell totalmente desligado del daemon (no hereda su ciclo de vida)."""
    subprocess.Popen(
        ["setsid", "-f", "sh", "-c", command],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def notify(summary: str, body: str = "", urgency: str = "normal", icon: str = "") -> None:
    if have("notify-send"):
        cmd = ["notify-send", "-a", "hyprland-desktop", "-u", urgency]
        if icon:
            cmd += ["-i", icon]
        subprocess.Popen(cmd + [summary, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Cómo pasar un comando a cada terminal conocida. Por defecto se usa "-e".
_TERMINAL_EXEC = {
    "kitty": ["--class", "hd-float", "-e"],
    "alacritty": ["--class", "hd-float", "-e"],
    "foot": ["--app-id", "hd-float"],
    "wezterm": ["start", "--class", "hd-float", "--"],
    "konsole": ["-e"],
    "ghostty": ["--class=hd.float", "-e"],
}


def terminal_command(terminal: str, inner: str) -> str:
    """Construye un comando de shell que abre `inner` en una terminal interactiva flotante."""
    parts = shlex.split(terminal)
    name = os.path.basename(parts[0]) if parts else "xterm"
    args = _TERMINAL_EXEC.get(name, ["-e"])
    return shlex.join(parts + args + ["sh", "-c", inner])


class Debouncer:
    """Agrupa ráfagas de eventos en una sola ejecución de `fn`."""

    def __init__(self, delay: float, fn):
        self.delay = delay
        self.fn = fn
        self._task: asyncio.Task | None = None

    def __call__(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = asyncio.get_running_loop().create_task(self._fire())

    async def _fire(self) -> None:
        try:
            await asyncio.sleep(self.delay)
            await self.fn()
        except asyncio.CancelledError:
            pass
        except Exception as e:  # un fallo en una fuente nunca debe tumbar el daemon
            log(f"error en {getattr(self.fn, '__qualname__', self.fn)}: {e!r}")


async def stream_lines(cmd: list[str], on_line, restart_delay: float = 3.0, name: str = "") -> None:
    """Ejecuta un proceso de eventos (pactl subscribe, nmcli monitor...) y lo reinicia si muere."""
    name = name or cmd[0]
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL)
        except FileNotFoundError:
            log(f"{name}: no instalado; la fuente queda inactiva")
            return
        try:
            assert proc.stdout
            while line := await proc.stdout.readline():
                try:
                    await on_line(line.decode(errors="replace").rstrip("\n"))
                except Exception as e:
                    log(f"{name}: error procesando evento: {e!r}")
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        debug(f"{name}: proceso terminó, reinicio en {restart_delay}s")
        await asyncio.sleep(restart_delay)


def split_nmcli(line: str) -> list[str]:
    """Divide una línea de `nmcli -t` respetando los ':' escapados como '\\:'."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields
