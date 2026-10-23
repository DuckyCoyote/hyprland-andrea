"""desktopctl: interfaz de línea de órdenes del entorno.

  desktopctl start | stop | restart     arranca/detiene el daemon (que abre Eww y las barras)
  desktopctl daemon                     ejecuta el daemon en primer plano (depuración)
  desktopctl apply                      regenera los archivos derivados de settings.json/tema
  desktopctl get <tema>                 muestra el estado JSON de un tema
  desktopctl doctor                     comprueba dependencias y servicios
  desktopctl <tema> <orden> [args…]     envía una orden al daemon, p. ej.:
      desktopctl popup toggle audio DP-1
      desktopctl audio step sink +5
      desktopctl appearance set theme latte
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time

from . import paths

DEPENDENCIES = [
    # (binario, paquete, obligatorio, para qué)
    ("Hyprland", "hyprland", True, "compositor"),
    ("eww", "eww", True, "barra y widgets"),
    ("socat", "socat", True, "suscripción de Eww al daemon"),
    ("jq", "jq", False, "utilidades de shell"),
    ("pactl", "libpulse", True, "lectura de audio"),
    ("wpctl", "wireplumber", True, "control de volumen"),
    ("nmcli", "networkmanager", True, "red"),
    ("bluetoothctl", "bluez-utils", False, "bluetooth"),
    ("playerctl", "playerctl", True, "multimedia MPRIS"),
    ("checkupdates", "pacman-contrib", True, "actualizaciones"),
    ("hyprlock", "hyprlock", True, "bloqueo"),
    ("hypridle", "hypridle", True, "inactividad"),
    ("notify-send", "libnotify", True, "notificaciones"),
    ("awww", "awww", False, "fondo de pantalla"),
    ("grim", "grim", False, "capturas"),
    ("slurp", "slurp", False, "capturas de región"),
    ("wl-copy", "wl-clipboard", False, "portapapeles"),
    ("powerprofilesctl", "power-profiles-daemon", False, "perfiles de energía"),
    ("kitty", "kitty", False, "terminal predeterminada"),
]


def _request(argv: list[str], timeout: float = 90) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(paths.socket_path("ctl")))
    except OSError:
        raise SystemExit("desktopd no está en ejecución. Inícialo con: desktopctl start")
    s.sendall((json.dumps({"argv": argv}) + "\n").encode())
    data = b""
    while chunk := s.recv(65536):
        data += chunk
    s.close()
    return json.loads(data.decode() or "{}")


def _running() -> int | None:
    try:
        pid = int((paths.RUNTIME_DIR / "desktopd.pid").read_text())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def _instance(pid: int | None = None) -> str | None:
    """HYPRLAND_INSTANCE_SIGNATURE de un proceso (o del actual)."""
    if pid is None:
        return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    try:
        env = open(f"/proc/{pid}/environ", "rb").read().split(b"\0")
    except OSError:
        return None
    for var in env:
        if var.startswith(b"HYPRLAND_INSTANCE_SIGNATURE="):
            return var.split(b"=", 1)[1].decode()
    return None


def _compositor_gone() -> bool:
    """True si la sesión de Hyprland de la que venimos ya terminó (su socket ya no existe)."""
    sig = _instance()
    return bool(sig) and not (paths.RUNTIME_HOME / "hypr" / sig / ".socket.sock").exists()


def start() -> None:
    # Al cerrar sesión, los suscriptores de la Eww saliente (desktop-sub) intentaban arrancar el
    # daemon de nuevo: quedaba uno ligado a la sesión muerta y la nueva no abría ninguna barra.
    if _compositor_gone():
        print("la sesión de Hyprland ya terminó: no se arranca desktopd")
        return
    pid = _running()
    if pid and _instance(pid) != _instance():
        print("desktopd pertenece a otra sesión de Hyprland: reiniciándolo")
        stop()
    elif pid:
        print("desktopd ya está en ejecución")
        return
    paths.ensure_dirs()
    log = open(paths.CACHE_DIR / "desktopd.log", "a")
    subprocess.Popen([sys.executable, str(paths.CTL), "daemon"], stdin=subprocess.DEVNULL,
                     stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):
        if paths.socket_path("ctl").exists():
            print("desktopd iniciado")
            return
        time.sleep(0.1)
    raise SystemExit(f"desktopd no arrancó; revisa {paths.CACHE_DIR / 'desktopd.log'}")


def stop() -> None:
    pid = _running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not _running():
                break
            time.sleep(0.1)
        print("desktopd detenido")


def get(topic: str) -> None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(str(paths.socket_path(topic)))
    except OSError:
        raise SystemExit(f"tema no disponible: {topic}")
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    print(json.dumps(json.loads(buf.split(b"\n")[0]), indent=2, ensure_ascii=False))


def apply() -> None:
    if _running():
        print(_request(["appearance", "apply"]).get("msg", ""))
        _request(["wm", "bars"])
        return
    from . import render
    ctx, changed = render.write_all()
    render.log_changes(changed)
    print(f"{len(changed)} archivos regenerados")


def doctor() -> int:
    import shutil
    missing_required = 0
    print("Dependencias:")
    for binary, pkg, required, why in DEPENDENCIES:
        ok = shutil.which(binary) is not None
        if not ok and required:
            missing_required += 1
        mark = "✔" if ok else ("✘" if required else "·")
        print(f"  {mark} {binary:<18} ({pkg}) — {why}{'' if ok or required else ' [opcional]'}")
    print("\nServicios:")
    for unit, user in (("pipewire.service", True), ("wireplumber.service", True), ("NetworkManager.service", False)):
        cmd = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
        state = subprocess.run(cmd, capture_output=True, text=True).stdout.strip() or "desconocido"
        print(f"  {'✔' if state == 'active' else '✘'} {unit:<24} {state}")
    print(f"\ndesktopd: {'en ejecución' if _running() else 'detenido'}")
    print(f"configuración de usuario: {paths.USER_SETTINGS} {'(existe)' if paths.USER_SETTINGS.exists() else '(usa valores del repositorio)'}")
    return 1 if missing_required else 0


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = argv[0]
    if cmd == "daemon":
        from .daemon import main as daemon_main
        daemon_main()
    elif cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        start()
    elif cmd == "apply":
        apply()
    elif cmd == "get" and len(argv) == 2:
        get(argv[1])
    elif cmd == "doctor":
        sys.exit(doctor())
    elif cmd == "wallpaper":
        from . import render
        render.set_wallpaper()
    else:
        reply = _request(argv)
        if reply.get("msg"):
            print(reply["msg"])
        sys.exit(0 if reply.get("ok") else 1)
