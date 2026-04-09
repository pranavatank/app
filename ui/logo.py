"""Shared logo and icon helpers for consistent app branding."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import ctypes
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

from config import BASE_DIR

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional fallback
    Image = None


_LOGO_SOURCE_PATH = Path(BASE_DIR) / "data" / "logo.png"
_LOGO_CLEAN_PATH = Path(BASE_DIR) / "data" / "logo_clean.png"
_LOGO_ICON_PATH = Path(BASE_DIR) / "data" / "logo.ico"
_APP_USER_MODEL_ID = "PersonalFinancialManager.App"


def _asset_needs_refresh(target: Path) -> bool:
    if not target.is_file() or not _LOGO_SOURCE_PATH.is_file():
        return True
    try:
        return target.stat().st_mtime < _LOGO_SOURCE_PATH.stat().st_mtime
    except OSError:
        return True


def _is_bg_like(rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int], threshold: int = 38) -> bool:
    return (
        abs(rgb[0] - bg_rgb[0]) <= threshold
        and abs(rgb[1] - bg_rgb[1]) <= threshold
        and abs(rgb[2] - bg_rgb[2]) <= threshold
    )


def _create_transparent_logo() -> None:
    if Image is None or not _LOGO_SOURCE_PATH.is_file():
        return

    image = Image.open(_LOGO_SOURCE_PATH).convert("RGBA")
    width, height = image.size
    pix = image.load()

    corners = [
        pix[1, 1],
        pix[max(1, width - 2), 1],
        pix[1, max(1, height - 2)],
        pix[max(1, width - 2), max(1, height - 2)],
    ]
    bg_rgb = (
        sum(p[0] for p in corners) // 4,
        sum(p[1] for p in corners) // 4,
        sum(p[2] for p in corners) // 4,
    )

    remove_mask = [[False] * width for _ in range(height)]
    queue = deque()

    def enqueue_if_bg(x: int, y: int) -> None:
        if remove_mask[y][x]:
            return
        r, g, b, a = pix[x, y]
        if a == 0 or _is_bg_like((r, g, b), bg_rgb):
            remove_mask[y][x] = True
            queue.append((x, y))

    for x in range(width):
        enqueue_if_bg(x, 0)
        enqueue_if_bg(x, height - 1)
    for y in range(height):
        enqueue_if_bg(0, y)
        enqueue_if_bg(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not remove_mask[ny][nx]:
                r, g, b, a = pix[nx, ny]
                if a == 0 or _is_bg_like((r, g, b), bg_rgb):
                    remove_mask[ny][nx] = True
                    queue.append((nx, ny))

    for y in range(height):
        for x in range(width):
            if remove_mask[y][x]:
                r, g, b, _ = pix[x, y]
                pix[x, y] = (r, g, b, 0)

    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        pad = max(8, min(width, height) // 90)
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(width, bbox[2] + pad)
        bottom = min(height, bbox[3] + pad)
        image = image.crop((left, top, right, bottom))

    image.save(_LOGO_CLEAN_PATH, optimize=True)


def _create_ico() -> None:
    if Image is None:
        return
    source = _LOGO_CLEAN_PATH if _LOGO_CLEAN_PATH.is_file() else _LOGO_SOURCE_PATH
    if not source.is_file():
        return

    image = Image.open(source).convert("RGBA")
    image.save(
        _LOGO_ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def ensure_logo_assets() -> None:
    if not _LOGO_SOURCE_PATH.is_file():
        return
    try:
        if _asset_needs_refresh(_LOGO_CLEAN_PATH):
            _create_transparent_logo()
        if _asset_needs_refresh(_LOGO_ICON_PATH):
            _create_ico()
    except Exception:
        # Never block UI startup due to optional asset preprocessing.
        return


def _preferred_logo_path() -> Path:
    ensure_logo_assets()
    if _LOGO_CLEAN_PATH.is_file():
        return _LOGO_CLEAN_PATH
    return _LOGO_SOURCE_PATH


def logo_exists() -> bool:
    return _LOGO_SOURCE_PATH.is_file()


def logo_pixmap(size: int | None = None) -> QPixmap:
    if not logo_exists():
        return QPixmap()
    pixmap = QPixmap(str(_preferred_logo_path()))
    if pixmap.isNull() or not size:
        return pixmap
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def app_icon() -> QIcon:
    if not logo_exists():
        return QIcon()
    ensure_logo_assets()
    if sys.platform.startswith("win") and _LOGO_ICON_PATH.is_file():
        return QIcon(str(_LOGO_ICON_PATH))
    return QIcon(str(_preferred_logo_path()))


def set_windows_app_user_model_id() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception:
        return


def set_app_icon(app) -> None:
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)


def set_window_icon(window) -> None:
    icon = app_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)
