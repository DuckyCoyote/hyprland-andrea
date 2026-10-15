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
    subprocess.Popen(_cmd("daemon"), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, env=env)
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
    """{id: nombre_de_ventana}"""
    code, out = call("active-windows")
    result = {}
    if code == 0:
        for line in out.splitlines():
            if ": " in line:
                wid, name = line.split(": ", 1)
                result[wid.strip()] = name.strip()
    return result


def reload() -> None:
    call("reload")
