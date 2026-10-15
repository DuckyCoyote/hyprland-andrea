"""Catálogos con previsualización para el selector de apariencia: fondos de pantalla y cursores.

Las miniaturas se generan una vez en ~/.cache/hyprland-desktop/thumbs (clave: ruta + fecha de
modificación) con GdkPixbuf, que ya está presente con GTK; no hace falta ImageMagick.
"""
import hashlib
import os
import re
import struct
from pathlib import Path

from . import paths
from .util import log

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".avif", ".jxl"}
THUMBS = paths.CACHE_DIR / "thumbs"


def _pixbuf():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return GdkPixbuf


def _thumb_path(src: Path, tag: str) -> Path:
    try:
        stamp = src.stat().st_mtime_ns
    except OSError:
        stamp = 0
    key = hashlib.sha1(f"{src}:{stamp}:{tag}".encode()).hexdigest()
    return THUMBS / f"{key}.png"


# --------------------------------------------------------------------------- fondos
def wallpaper_dir(settings: dict) -> Path:
    """Carpeta de fondos: settings.wallpaper_dir o <Imágenes>/Wallpapers (se crea si falta)."""
    configured = settings.get("wallpaper_dir", "")
    if configured:
        folder = Path(os.path.expandvars(configured)).expanduser()
    else:
        pictures = os.popen("xdg-user-dir PICTURES 2>/dev/null").read().strip() or str(Path.home() / "Pictures")
        folder = Path(pictures) / "Wallpapers"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"no se pudo crear la carpeta de fondos {folder}: {e}")
    return folder


def wallpapers(folder: Path, limit: int = 120) -> list[dict]:
    """[{path, name, thumb}] de las imágenes de la carpeta (y subcarpetas), ordenadas por nombre."""
    if not folder.is_dir():
        return []
    files = sorted((p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXT and p.is_file()),
                   key=lambda p: str(p).lower())[:limit]
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        thumb = _thumb_path(f, "wall-320")
        if not thumb.exists():
            try:
                pix = _pixbuf().Pixbuf.new_from_file_at_scale(str(f), 320, 180, True)
                pix.savev(str(thumb), "png", [], [])
            except Exception as e:  # imagen dañada o formato sin cargador
                log(f"miniatura fallida para {f.name}: {e}")
                continue
        out.append({"path": str(f), "name": f.stem, "thumb": str(thumb)})
    return out


# --------------------------------------------------------------------------- cursores
def _icon_dirs() -> list[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    dirs = [Path.home() / ".icons", data_home / "icons"]
    dirs += [Path(d) / "icons" for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    return dirs


def cursor_themes() -> list[dict]:
    """[{name, preview}] de los temas que contienen cursores (el primero encontrado gana)."""
    seen: dict[str, Path] = {}
    for d in _icon_dirs():
        if not d.is_dir():
            continue
        for theme in sorted(d.iterdir()):
            if theme.name not in seen and (theme / "cursors").is_dir() and theme.name != "default":
                seen[theme.name] = theme
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = []
    for name, theme in sorted(seen.items(), key=lambda kv: kv[0].lower()):
        label = re.sub(r"[-_]+", " ", name)
        label = re.sub(r"\s*cursors?$", "", label, flags=re.I).strip() or name
        out.append({"name": name, "label": label, "preview": _cursor_preview(theme)})
    return out


def _cursor_preview(theme: Path) -> str:
    for cursor in ("left_ptr", "default", "arrow", "top_left_arrow"):
        src = theme / "cursors" / cursor
        if src.exists():
            break
    else:
        return ""
    thumb = _thumb_path(src.resolve(), "cursor")
    if thumb.exists():
        return str(thumb)
    try:
        width, height, rgba = _read_xcursor(src.read_bytes(), 48)
        GdkPixbuf = _pixbuf()
        from gi.repository import GLib
        pix = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba), GdkPixbuf.Colorspace.RGB, True, 8,
                                              width, height, width * 4)
        pix.savev(str(thumb), "png", [], [])
        return str(thumb)
    except Exception as e:
        log(f"no se pudo previsualizar el cursor {theme.name}: {e}")
        return ""


def _read_xcursor(data: bytes, wanted: int) -> tuple[int, int, bytes]:
    """Lee la imagen del tamaño nominal más cercano a `wanted` de un archivo Xcursor."""
    if data[:4] != b"Xcur":
        raise ValueError("no es un archivo Xcursor")
    _, _, ntoc = struct.unpack_from("<III", data, 4)
    images = []
    for i in range(ntoc):
        kind, size, pos = struct.unpack_from("<III", data, 16 + i * 12)
        if kind == 0xFFFD0002:
            images.append((abs(size - wanted), pos))
    if not images:
        raise ValueError("sin imágenes")
    pos = min(images)[1]
    width, height = struct.unpack_from("<II", data, pos + 16)
    pixels = memoryview(data)[pos + 36: pos + 36 + width * height * 4]
    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        b, g, r, a = pixels[i * 4: i * 4 + 4]  # ARGB little-endian, premultiplicado
        if a:
            r, g, b = (min(255, c * 255 // a) for c in (r, g, b))
        rgba[i * 4: i * 4 + 4] = bytes((r, g, b, a))
    return width, height, bytes(rgba)
