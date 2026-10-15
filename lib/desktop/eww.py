"""Cliente mínimo de Eww. Es el único módulo que invoca el binario `eww`."""
import json
import os
import subprocess

from . import paths
from .util import debug, log

EWW = os.environ.get("DESKTOP_EWW", "eww")


def _cmd(*args: str) -> list[str]:
    return [EWW, "-c", str(paths.EWW_DIR), *args]


def call(*args: str, timeout: float = 10) -> tuple[int, str]:
    try:
        p = subprocess.run(_cmd(*args), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        log("eww no está instalado")
        return 127, ""
    except subprocess.TimeoutExpired:
        log(f"eww {' '.join(args)}: tiempo agotado")
        return 124, ""
    if p.returncode != 0:
        debug(f"eww {' '.join(args)} -> {p.stderr.strip()}")
    return p.returncode, (p.stdout + p.stderr).strip()


def running() -> bool:
    return call("ping", timeout=2)[0] == 0


def start_daemon() -> None:
    if running():
        return
    # Los widgets invocan `desktopctl` y `desktop-sub` por nombre: los ponemos en el PATH de Eww.
    env = {**os.environ, "PATH": f"{paths.ROOT / 'bin'}:{os.environ.get('PATH', '/usr/bin')}"}
    # En primer plano (sin daemonizar) para conservar su registro: errores de widgets y bloqueos
    paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(paths.CACHE_DIR / "eww.log", "w") as logfile:
        subprocess.Popen(_cmd("daemon", "--no-daemonize"), stdin=subprocess.DEVNULL, stdout=logfile,
                         stderr=subprocess.STDOUT, start_new_session=True, env=env)
    for _ in range(50):
        if running():
            return
        import time
        time.sleep(0.1)
    log("eww daemon no respondió")


def update(**values) -> None:
    if not values:
        return
    args = [f"{k}={v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}" for k, v in values.items()]
    call("update", *args)


def open_window(window: str, window_id: str, screen: str | int | None, args: dict | None = None) -> bool:
    cmd = ["open", window, "--id", window_id]
    if screen is not None:
        cmd += ["--screen", str(screen)]
    for k, v in (args or {}).items():
        cmd += ["--arg", f"{k}={v}"]
    code, out = call(*cmd)
    if code != 0:
        log(f"no se pudo abrir {window_id}: {out}")
    return code == 0


def close(*window_ids: str) -> None:
    if window_ids:
        call("close", *window_ids)


def active_windows() -> dict[str, str]:
    """{id: nombre_de_ventana} (vacío si Eww no responde; ver active_windows_or_none)."""
    return active_windows_or_none() or {}


def active_windows_or_none() -> dict[str, str] | None:
    """Como active_windows, pero None si Eww no respondió (p. ej. en plena recarga): así no se
    confunde «no hay ventanas» con «no lo sé» y no se abren barras duplicadas."""
    code, out = call("active-windows")
    if code != 0:
        return None
    result = {}
    for line in out.splitlines():
        if ": " in line:
            wid, name = line.split(": ", 1)
            result[wid.strip()] = name.strip()
    return result


def reload() -> None:
    call("reload", timeout=20)


def close_all() -> None:
    call("close-all")


def restart_daemon() -> None:
    """Reinicia el daemon de Eww: única forma de eliminar ventanas huérfanas que Eww ya no controla
    o de recuperarlo si se colgó (en ese caso `eww kill` no responde y se termina el proceso)."""
    import time
    call("kill", timeout=3)
    subprocess.run(["pkill", "-f", f"{EWW} -c {paths.EWW_DIR} daemon"], stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    subprocess.run(["pkill", "-9", "-f", f"{EWW} -c {paths.EWW_DIR} "], stderr=subprocess.DEVNULL)
    start_daemon()
