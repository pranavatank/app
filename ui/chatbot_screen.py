"""
ui/chatbot_screen.py - Local Ollama chatbot dialog — modern AI chat UI.
"""

import json
import os
from pathlib import Path
from urllib import error as url_error
from urllib import request as url_request

import re

from PyQt6.QtCore import (
    QObject, Qt, QThread, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QFont, QColor, QPainter
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget, QFileDialog,
)

from engines.statement_parser import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_KEEP_ALIVE,
    DEFAULT_OLLAMA_MODEL,
    is_ollama_available,
    mark_ollama_model_used,
    ollama_keep_alive_value,
    unload_ollama_model,
)
from ui.theme import Theme, ThemeManager
from ui.icons import icon as app_icon, set_btn_icon, is_available as icons_available


# ── Typing animation dots widget ─────────────────────────────────────────────

class _TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self._dots = [0.3, 0.3, 0.3]
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(180)

    def _tick(self):
        self._phase = (self._phase + 1) % 6
        self._dots = [0.3, 0.3, 0.3]
        if self._phase < 3:
            self._dots[self._phase] = 1.0
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(Theme.PRIMARY)
        r = 5
        gap = 7
        x0 = 6
        y = self.height() // 2
        for i, alpha in enumerate(self._dots):
            color.setAlphaF(alpha)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(x0 + i * (r * 2 + gap), y - r, r * 2, r * 2)
        p.end()


# ── Chat input ────────────────────────────────────────────────────────────────

class ChatInput(QPlainTextEdit):
    send_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


# ── Workers ───────────────────────────────────────────────────────────────────

class OllamaChatWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, messages: list[dict[str, str]]):
        super().__init__()
        self.messages = messages
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.keep_alive = ollama_keep_alive_value(os.getenv("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE))
        self.timeout_seconds = float(os.getenv("OLLAMA_CHAT_TIMEOUT_SECONDS", "120"))

    def run(self):
        payload = {
            "model": self.model,
            "prompt": self._build_prompt(),
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        req = url_request.Request(
            url=f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with url_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            mark_ollama_model_used()
        except url_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            self.failed.emit(f"Ollama HTTP {exc.code}: {detail or ''}")
            return
        except (url_error.URLError, TimeoutError) as exc:
            self.failed.emit(f"Could not reach Ollama: {exc}")
            return
        except json.JSONDecodeError:
            self.failed.emit("Ollama returned an unreadable response.")
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        content = str(body.get("response") or "").strip()
        if content:
            self.finished.emit(content)
        else:
            self.failed.emit("The model returned an empty response.")

    def _build_prompt(self) -> str:
        lines = [
            "You are a helpful local assistant inside a personal finance desktop app.",
            "Answer naturally and clearly. Use markdown formatting (bold, lists, "
            "fenced ``` code blocks ```, headings) where it helps readability. "
            "Do not mention cloud services unless asked.",
            "",
            "Conversation:",
        ]
        for item in self.messages[-20:]:
            role = "User" if item.get("role") == "user" else "Assistant"
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        lines.append("Assistant:")
        return "\n".join(lines)


class OllamaModelStopWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_ENDPOINT)

    def run(self):
        ok = unload_ollama_model(model=self.model, endpoint=self.endpoint, timeout=5.0)
        if ok:
            self.finished.emit()
        else:
            self.failed.emit("Could not unload the model (it may already be stopped).")


class OllamaModelStartWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.keep_alive = ollama_keep_alive_value(os.getenv("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE))
        self.timeout_seconds = float(os.getenv("OLLAMA_START_TIMEOUT_SECONDS", "180"))

    def run(self):
        payload = {"model": self.model, "prompt": "", "stream": False, "keep_alive": self.keep_alive}
        req = url_request.Request(
            url=f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with url_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp.read()
            mark_ollama_model_used()
        except url_error.HTTPError as exc:
            self.failed.emit(f"Ollama HTTP {exc.code}")
            return
        except (url_error.URLError, TimeoutError) as exc:
            self.failed.emit(f"Could not reach Ollama: {exc}")
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(f"{self.model} is running.")


# ── File type accent colors (shared by pending-file pills and sent-message chips)

_EXT_COLORS = {
    "pdf":  "#F87171", "csv": "#34D399", "xlsx": "#34D399",
    "xls":  "#34D399", "png": "#A78BFA", "jpg":  "#A78BFA",
    "jpeg": "#A78BFA", "txt": "#60A5FA", "json": "#FBBF24",
}


def _ext_icon_name(ext: str) -> str:
    if ext == "pdf":
        return "import_pdf"
    if ext == "json":
        return "import_json"
    return "basic_info"


# ── File attachment pill (pending, in the input bar) ─────────────────────────

class _FilePill(QFrame):
    removed = pyqtSignal(str)   # emits the path

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        name = Path(path).name
        ext = Path(path).suffix.lstrip(".").lower()
        color = _EXT_COLORS.get(ext, Theme.PRIMARY)

        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE_ALT};
                border: 1px solid {color}55;
                border-radius: 14px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(6)

        icon_lbl = QLabel()
        if icons_available():
            icon_lbl.setPixmap(app_icon(_ext_icon_name(ext), color=color, size=13).pixmap(13, 13))
        else:
            icon_lbl.setText(ext.upper()[:4] or "FILE")
            icon_lbl.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 800;")
        icon_lbl.setStyleSheet(icon_lbl.styleSheet() + " background: transparent; border: none;")
        lay.addWidget(icon_lbl)

        name_lbl = QLabel(name if len(name) <= 20 else name[:18] + "…")
        name_lbl.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(name_lbl)

        rm = QPushButton()
        rm.setFixedSize(16, 16)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        if icons_available():
            rm.setIcon(app_icon("close", color=Theme.TEXT_MUTED, size=11))
        else:
            rm.setText("x")
        rm.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; }"
        )
        rm.clicked.connect(lambda: self.removed.emit(self.path))
        lay.addWidget(rm)


# ── Markdown → HTML helper ───────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """Markdown → HTML for assistant replies: bold, italic, inline code,
    fenced ``` code blocks ```, blockquotes, numbered & bullet lists, headings."""
    # Pull out fenced code blocks first so their contents are never touched
    # by inline/list/heading formatting, then splice back in as placeholders.
    code_blocks: list[str] = []

    def _stash_code_block(match: "re.Match") -> str:
        lang = (match.group(1) or "").strip()
        body = match.group(2)
        body_escaped = (body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        label = (
            f'<div style="color:{Theme.TEXT_MUTED};font-size:10px;'
            f'padding:4px 10px 0 10px;letter-spacing:0.5px;">{lang.upper()}</div>'
            if lang else ""
        )
        block = (
            f'<div style="background:{Theme.SURFACE_ALT};border:1px solid {Theme.BORDER};'
            f'border-radius:8px;margin:6px 0;">{label}'
            f'<pre style="margin:0;padding:8px 10px;font-family:Consolas,\'Courier New\',monospace;'
            f'font-size:12px;white-space:pre-wrap;">{body_escaped}</pre></div>'
        )
        code_blocks.append(block)
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r"```(\w*)\n(.*?)```", _stash_code_block, text, flags=re.DOTALL)

    lines = text.split("\n")
    html_lines = []
    in_list = False
    list_tag = ""

    def close_list():
        nonlocal in_list, list_tag
        if in_list:
            html_lines.append(f"</{list_tag}>")
            in_list = False
            list_tag = ""

    def inline(s: str) -> str:
        # Escape HTML entities first
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold **text** or __text__
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__(.+?)__", r"<b>\1</b>", s)
        # Italic *text* or _text_
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        s = re.sub(r"(?<![_])_([^_]+)_(?![_])", r"<i>\1</i>", s)
        # Inline code `code`
        s = re.sub(r"`([^`]+)`", rf'<code style="background:{Theme.SURFACE_ALT};padding:1px 4px;border-radius:3px;">\1</code>', s)
        return s

    for line in lines:
        # Restored code-block placeholder
        m0 = re.match(r"^\x00CODEBLOCK(\d+)\x00$", line.strip())
        if m0:
            close_list()
            html_lines.append(code_blocks[int(m0.group(1))])
            continue
        # Blockquote
        m = re.match(r"^>\s?(.*)", line)
        if m:
            close_list()
            html_lines.append(
                f'<p style="margin:4px 0;padding:4px 10px;border-left:3px solid {Theme.PRIMARY};'
                f'color:{Theme.TEXT_SECONDARY};">{inline(m.group(1))}</p>'
            )
            continue
        # Numbered list
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            if not in_list or list_tag != "ol":
                close_list()
                html_lines.append("<ol style='margin:4px 0 4px 18px; padding:0;'>")
                in_list = True; list_tag = "ol"
            html_lines.append(f"<li>{inline(m.group(2))}</li>")
            continue
        # Bullet list
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            if not in_list or list_tag != "ul":
                close_list()
                html_lines.append("<ul style='margin:4px 0 4px 18px; padding:0;'>")
                in_list = True; list_tag = "ul"
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue
        # Heading ### / ## / #
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            close_list()
            lvl = len(m.group(1))
            sizes = {1: "15px", 2: "14px", 3: "13px"}
            html_lines.append(f'<p style="margin:6px 0 2px 0;"><b><span style="font-size:{sizes[lvl]};">{inline(m.group(2))}</span></b></p>')
            continue
        # Blank line
        close_list()
        if line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p style='margin:2px 0;'>{inline(line)}</p>")

    close_list()
    return "".join(html_lines)


# ── Message bubble ────────────────────────────────────────────────────────────

class _Bubble(QFrame):
    """Single chat message bubble."""
    def __init__(self, role: str, text: str, muted: bool = False,
                 attachments: list[str] | None = None, parent=None):
        super().__init__(parent)
        is_user = role == "user"

        if is_user:
            bg     = Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.PRIMARY_GRADIENT_END, diagonal=True)
            fg     = "#FFFFFF"
            border = "transparent"
        elif muted:
            bg     = Theme.SURFACE_ALT
            fg     = Theme.TEXT_MUTED
            border = Theme.DIVIDER
        else:
            bg     = Theme.SURFACE
            fg     = Theme.TEXT_PRIMARY
            border = Theme.BORDER

        radius_tail = "18px 18px 4px 18px" if is_user else "18px 18px 18px 4px"
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {border};"
            f" border-radius: {radius_tail}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        # Attachments inside bubble (user side)
        if attachments:
            att_row = QHBoxLayout()
            att_row.setSpacing(6)
            for path in attachments:
                pill = _AttachmentPreview(path)
                att_row.addWidget(pill)
            att_row.addStretch()
            lay.addLayout(att_row)

        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        lbl.setOpenExternalLinks(True)
        if is_user:
            # User bubbles: plain text (no markdown needed)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lbl.setText(text)
        else:
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setText(
                f'<span style="color:{fg};font-size:13px;line-height:1.6;">'
                + _md_to_html(text)
                + "</span>"
            )
        lbl.setStyleSheet(f"background: transparent; border: none; color: {fg};")
        lay.addWidget(lbl)

        # Shadow only on AI bubble
        if not is_user and not muted:
            try:
                self.setGraphicsEffect(Theme.shadow_card())
            except Exception:
                pass


class _AttachmentPreview(QFrame):
    """Compact file badge shown inside a sent message bubble (always on the
    user's gradient bubble, so white-on-translucent is theme-independent)."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        name = Path(path).name
        ext  = Path(path).suffix.lstrip(".").lower()
        self.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.15); "
            "border: 1px solid rgba(255,255,255,0.35); border-radius: 10px; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(7, 3, 8, 3)
        lay.setSpacing(5)
        icon_lbl = QLabel()
        if icons_available():
            icon_lbl.setPixmap(app_icon(_ext_icon_name(ext), color="#FFFFFF", size=12).pixmap(12, 12))
        else:
            icon_lbl.setText(ext.upper()[:4] or "FILE")
            icon_lbl.setStyleSheet("color: #FFFFFF; font-size: 9px; font-weight: 800;")
        icon_lbl.setStyleSheet(icon_lbl.styleSheet() + " background: transparent; border: none;")
        lay.addWidget(icon_lbl)
        nl = QLabel(name if len(name) <= 18 else name[:16] + "…")
        nl.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 11px; background: transparent; border: none;")
        lay.addWidget(nl)


# ── Avatar ────────────────────────────────────────────────────────────────────

class _Avatar(QLabel):
    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._role = role
        self._apply_style()

    def _apply_style(self):
        if self._role == "user":
            self.setStyleSheet(
                f"background: {Theme.SURFACE_ALT}; border-radius: 16px;"
                f" border: 1.5px solid {Theme.BORDER};"
            )
            if icons_available():
                self.setPixmap(app_icon("person", color=Theme.PRIMARY, size=16).pixmap(16, 16))
            else:
                self.setText("U")
        else:
            self.setStyleSheet(
                f"background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.HERO_GRADIENT_END, diagonal=True)};"
                f" border-radius: 16px; border: none;"
            )
            if icons_available():
                self.setPixmap(app_icon("bot", color="#FFFFFF", size=17).pixmap(17, 17))
            else:
                self.setText("AI")
                self.setStyleSheet(self.styleSheet() + " color: white; font-size: 11px; font-weight: 900;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


# ── Main dialog ───────────────────────────────────────────────────────────────

class LocalChatbotDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model    = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_ENDPOINT)
        self.messages: list[dict[str, str]] = []
        self._thread: QThread | None = None
        self._worker: OllamaChatWorker | None = None
        self._start_thread: QThread | None = None
        self._start_worker: OllamaModelStartWorker | None = None
        self._stop_thread: QThread | None = None
        self._stop_worker: OllamaModelStopWorker | None = None
        self._thinking_row: QWidget | None = None
        self._pending_files: list[str] = []   # files waiting to be sent

        self.setWindowTitle("AI Financial Assistant")
        self.setMinimumSize(720, 580)
        self.resize(860, 660)
        self._build_ui()
        self._refresh_status()
        self._add_message(
            "assistant",
            "Hello! I'm your local AI financial assistant. Ask me anything about your finances, "
            "upload statements or documents, and I'll help you analyse them.",
            remember=False,
        )
        # This dialog is cached and reused across the app's lifetime (created
        # once by dashboard_screen.py, then shown/hidden) rather than rebuilt
        # per open, so it needs its own live-theme listener.
        ThemeManager.register_on_change(self.refresh_theme)

    # ── UI build ─────────────────────────────────────────────────────────────

    def _dialog_bg_css(self) -> str:
        return f"QDialog {{ background-color: {Theme.BG}; }}"

    def refresh_theme(self, *_args):
        """Registered directly with ThemeManager (this dialog is cached and
        long-lived on the dashboard, not part of the page stack, so it can't
        rely on dashboard_screen.py's page-refresh loop) — re-applies every
        inline style built once at construction."""
        self.setStyleSheet(self._dialog_bg_css())
        if hasattr(self, "_header_frame"):
            self._header_frame.setStyleSheet(self._header_css())
        if hasattr(self, "_avatar_badge"):
            if icons_available():
                self._avatar_badge.setPixmap(app_icon("bot", color="#FFFFFF", size=20).pixmap(20, 20))
        if hasattr(self, "run_model_btn"):
            self.run_model_btn.setStyleSheet(self._run_model_btn_css())
        if hasattr(self, "scroll"):
            self.scroll.setStyleSheet(self._chat_area_css())
        if hasattr(self, "chat_host"):
            self.chat_host.setStyleSheet(f"background: {Theme.BG};")
        if hasattr(self, "_input_panel"):
            self._input_panel.setStyleSheet(self._input_panel_css())
        if hasattr(self, "_input_bar"):
            self._input_bar.setStyleSheet(self._input_bar_css())
        if hasattr(self, "attach_btn"):
            self.attach_btn.setStyleSheet(self._icon_btn_css())
            if icons_available():
                self.attach_btn.setIcon(app_icon("attach", color=Theme.TEXT_SECONDARY, size=18))
        if hasattr(self, "input_box"):
            self.input_box.setStyleSheet(self._input_box_css())
        if hasattr(self, "send_btn"):
            self._update_send_btn_state()
        if hasattr(self, "_hint_lbl"):
            self._hint_lbl.setStyleSheet(self._hint_css())
        self._refresh_status()

    def _build_ui(self):
        self.setStyleSheet(self._dialog_bg_css())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        root.addWidget(self._make_chat_area(), stretch=1)
        root.addWidget(self._make_input_panel())

    def _make_header(self) -> QWidget:
        self._header_frame = header = QFrame()
        header.setFixedHeight(64)
        header.setObjectName("chatHeader")
        header.setStyleSheet(self._header_css())
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 0, 16, 0)
        lay.setSpacing(12)

        # AI avatar badge (circular, icon-based)
        self._avatar_badge = QLabel()
        self._avatar_badge.setFixedSize(40, 40)
        self._avatar_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_badge.setStyleSheet(
            "background: rgba(255,255,255,0.20); border-radius: 20px;"
        )
        if icons_available():
            self._avatar_badge.setPixmap(app_icon("bot", color="#FFFFFF", size=20).pixmap(20, 20))
        else:
            self._avatar_badge.setText("AI")
            self._avatar_badge.setStyleSheet(
                self._avatar_badge.styleSheet() + " color: white; font-weight: 900; font-size: 12px;")
        lay.addWidget(self._avatar_badge)

        # Title block
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._title_lbl = title_lbl = QLabel("AI Financial Assistant")
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: white; background: transparent;")
        self._sub_lbl = sub_lbl = QLabel(f"Local · {self.model}")
        sub_lbl.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent; font-size: 10px;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        lay.addLayout(title_col)
        lay.addStretch()

        # Status badge
        self.status_lbl = QLabel("●  Checking…")
        self.status_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.12);"
            " border-radius: 10px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )
        lay.addWidget(self.status_lbl)

        # Buttons
        self.run_model_btn = self._header_btn("  Run Model")
        set_btn_icon(self.run_model_btn, "calculate")
        self.run_model_btn.clicked.connect(self._run_model)
        lay.addWidget(self.run_model_btn)

        self.stop_model_btn = self._header_btn("  Stop Model", ghost=True)
        set_btn_icon(self.stop_model_btn, "close")
        self.stop_model_btn.clicked.connect(self._stop_model)
        self.stop_model_btn.hide()
        lay.addWidget(self.stop_model_btn)

        clear_btn = self._header_icon_btn("delete", "Clear chat")
        clear_btn.clicked.connect(self._clear_chat)
        lay.addWidget(clear_btn)

        close_btn = self._header_icon_btn("close", "Close")
        close_btn.clicked.connect(self.close)
        lay.addWidget(close_btn)

        return header

    @staticmethod
    def _header_css() -> str:
        return (
            f"QFrame#chatHeader {{"
            f"  background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.HERO_GRADIENT_END, diagonal=True)};"
            f"  border: none;"
            f"}}"
        )

    def _run_model_btn_css(self) -> str:
        return (
            f"QPushButton {{ background: #FFFFFF; color: {Theme.PRIMARY_DARK};"
            " border: none; border-radius: 8px; padding: 4px 14px; font-weight: 700; }"
            f"QPushButton:hover {{ background: {Theme.PRIMARY_LIGHT}; }}"
            "QPushButton:disabled { background: rgba(255,255,255,0.4); color: rgba(0,0,0,0.4); }"
        )

    def _header_btn(self, text: str, ghost: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        btn.setMinimumWidth(96)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        if ghost:
            btn.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.12); color: white;"
                " border: 1px solid rgba(255,255,255,0.25); border-radius: 8px; padding: 4px 14px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.22); }"
            )
        else:
            btn.setStyleSheet(self._run_model_btn_css())
        return btn

    @staticmethod
    def _header_icon_btn_css() -> str:
        return (
            "QPushButton { background: rgba(255,255,255,0.12); border: none; border-radius: 16px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.22); }"
        )

    def _header_icon_btn(self, icon_name: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(32, 32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setAccessibleName(tooltip)
        btn.setStyleSheet(self._header_icon_btn_css())
        if icons_available():
            btn.setIcon(app_icon(icon_name, color="#FFFFFF", size=16))
        return btn

    def _make_chat_area(self) -> QWidget:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(self._chat_area_css())
        self.chat_host = QWidget()
        self.chat_host.setStyleSheet(f"background: {Theme.BG};")
        self.chat_layout = QVBoxLayout(self.chat_host)
        self.chat_layout.setContentsMargins(24, 20, 24, 20)
        self.chat_layout.setSpacing(16)
        self.chat_layout.addStretch()
        self.scroll.setWidget(self.chat_host)
        return self.scroll

    @staticmethod
    def _input_panel_css() -> str:
        return (
            f"QFrame#inputPanel {{"
            f"  background: {Theme.SURFACE};"
            f"  border-top: 1px solid {Theme.BORDER};"
            f"}}"
        )

    def _input_bar_css(self, focused: bool = False) -> str:
        border = Theme.PRIMARY if focused else Theme.BORDER
        width = "2px" if focused else "1.5px"
        return (
            f"QFrame#inputBar {{ background: {Theme.BG}; border: {width} solid {border};"
            f" border-radius: 22px; }}"
        )

    @staticmethod
    def _icon_btn_css() -> str:
        return (
            "QPushButton { background: transparent; border: none; border-radius: 16px; }"
            f"QPushButton:hover {{ background: {Theme.SURFACE_ALT}; }}"
            "QPushButton:disabled { opacity: 0.4; }"
        )

    @staticmethod
    def _input_box_css() -> str:
        return (
            f"QPlainTextEdit {{"
            f"  background: transparent; color: {Theme.TEXT_PRIMARY};"
            f"  border: none; padding: 6px 2px; font-size: 13px;"
            f"}}"
        )

    def _send_btn_css(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.PRIMARY_GRADIENT_END)};"
                " border: none; border-radius: 18px; }"
                f"QPushButton:hover {{ background: {Theme.PRIMARY_DARK}; }}"
            )
        return (
            f"QPushButton {{ background: {Theme.SURFACE_ALT}; border: none; border-radius: 18px; }}"
        )

    @staticmethod
    def _hint_css() -> str:
        return f"color: {Theme.TEXT_MUTED}; font-size: 10px; background: transparent;"

    @staticmethod
    def _chat_area_css() -> str:
        return f"QScrollArea {{ border: none; background: {Theme.BG}; }}"

    def _make_input_panel(self) -> QWidget:
        self._input_panel = container = QFrame()
        container.setObjectName("inputPanel")
        container.setStyleSheet(self._input_panel_css())
        outer = QVBoxLayout(container)
        outer.setContentsMargins(20, 12, 20, 12)
        outer.setSpacing(8)

        # Attached files row (hidden until a file is added)
        self._files_row_widget = QWidget()
        self._files_row_widget.setStyleSheet("background: transparent;")
        self._files_row = QHBoxLayout(self._files_row_widget)
        self._files_row.setContentsMargins(2, 0, 0, 0)
        self._files_row.setSpacing(6)
        self._files_row.addStretch()
        self._files_row_widget.hide()
        outer.addWidget(self._files_row_widget)

        # One unified pill-shaped bar: attach | input | send — modern chat-app style
        self._input_bar = bar = QFrame()
        bar.setObjectName("inputBar")
        bar.setStyleSheet(self._input_bar_css())
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(6, 6, 6, 6)
        bar_layout.setSpacing(6)

        # Attach button
        self.attach_btn = QPushButton()
        self.attach_btn.setFixedSize(36, 36)
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setToolTip("Attach file")
        self.attach_btn.setAccessibleName("Attach file")
        self.attach_btn.setStyleSheet(self._icon_btn_css())
        if icons_available():
            self.attach_btn.setIcon(app_icon("attach", color=Theme.TEXT_SECONDARY, size=18))
        self.attach_btn.clicked.connect(self._pick_file)
        bar_layout.addWidget(self.attach_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Text input
        self.input_box = ChatInput()
        self.input_box.setPlaceholderText("Message AI assistant…  (Enter to send, Shift+Enter for new line)")
        self.input_box.setMinimumHeight(36)
        self.input_box.setMaximumHeight(120)
        self.input_box.setFrameShape(QFrame.Shape.NoFrame)
        self.input_box.setStyleSheet(self._input_box_css())
        self.input_box.send_requested.connect(self._send_message)
        self.input_box.textChanged.connect(self._on_input_changed)
        bar_layout.addWidget(self.input_box, 1)

        # Send button (circular, lights up once there's something to send)
        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.setAccessibleName("Send message")
        self.send_btn.clicked.connect(self._send_message)
        bar_layout.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        outer.addWidget(bar)
        self._update_send_btn_state()

        # Bottom hint
        self._hint_lbl = hint = QLabel("Local & private · Powered by Ollama")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(self._hint_css())
        outer.addWidget(hint)

        return container

    def _on_input_changed(self):
        self._auto_resize_input()
        self._update_send_btn_state()

    def _update_send_btn_state(self):
        has_content = bool(self.input_box.toPlainText().strip()) or bool(self._pending_files)
        self.send_btn.setStyleSheet(self._send_btn_css(has_content))
        icon_color = "#FFFFFF" if has_content else Theme.TEXT_MUTED
        if icons_available():
            self.send_btn.setIcon(app_icon("send", color=icon_color, size=16))

    def _auto_resize_input(self):
        doc_h = int(self.input_box.document().size().height())
        new_h = max(36, min(doc_h + 14, 120))
        self.input_box.setFixedHeight(new_h)

    # ── File attachment ───────────────────────────────────────────────────────

    def _pick_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", "",
            "All Files (*);;PDF (*.pdf);;CSV (*.csv);;Excel (*.xlsx *.xls);;"
            "Images (*.png *.jpg *.jpeg);;Text (*.txt);;JSON (*.json)"
        )
        for path in paths:
            if path and path not in self._pending_files:
                self._pending_files.append(path)
                pill = _FilePill(path)
                pill.removed.connect(self._remove_file)
                # Insert before the stretch
                self._files_row.insertWidget(self._files_row.count() - 1, pill)
        if self._pending_files:
            self._files_row_widget.show()
        self._update_send_btn_state()

    def _remove_file(self, path: str):
        if path in self._pending_files:
            self._pending_files.remove(path)
        # Remove pill widget
        for i in range(self._files_row.count()):
            item = self._files_row.itemAt(i)
            if item and isinstance(item.widget(), _FilePill):
                if item.widget().path == path:
                    w = self._files_row.takeAt(i).widget()
                    w.deleteLater()
                    break
        if not self._pending_files:
            self._files_row_widget.hide()
        self._update_send_btn_state()

    def _clear_pending_files(self):
        self._pending_files.clear()
        while self._files_row.count() > 1:
            item = self._files_row.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._files_row_widget.hide()
        self._update_send_btn_state()

    # ── Status ────────────────────────────────────────────────────────────────

    def _refresh_status(self):
        if is_ollama_available(model=self.model, timeout=1.5):
            self.status_lbl.setText("●  Online")
            self.status_lbl.setStyleSheet(
                Theme.badge_style(bg=f"{Theme.SUCCESS}26", fg=Theme.SUCCESS, radius=10,
                                   padding="4px 12px", size=11, weight=700)
            )
        else:
            self.status_lbl.setText("●  Offline")
            self.status_lbl.setStyleSheet(
                Theme.badge_style(bg=f"{Theme.DANGER}26", fg=Theme.DANGER, radius=10,
                                   padding="4px 12px", size=11, weight=700)
            )

    # ── Send / receive ────────────────────────────────────────────────────────

    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if (not text and not self._pending_files) or self._thread or self._start_thread:
            return
        if not is_ollama_available(model=self.model, timeout=1.5):
            QMessageBox.warning(self, "AI Unavailable",
                                f"Ollama is not reachable or {self.model} is not installed.")
            self._refresh_status()
            return

        attachments = list(self._pending_files)
        display_text = text or f"[{len(attachments)} file(s) attached]"

        self.input_box.clear()
        self._clear_pending_files()
        self._add_message("user", display_text, attachments=attachments)
        self._set_busy(True)
        self._thinking_row = self._add_thinking()

        # Build content for model (append file names)
        model_text = text
        if attachments:
            file_list = "\n".join(f"- {Path(p).name}" for p in attachments)
            model_text = (model_text + "\n\nAttached files:\n" + file_list).strip()

        self.messages.append({"role": "user", "content": model_text})
        self._thread = QThread(self)
        self._worker = OllamaChatWorker(list(self.messages))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_reply)
        self._worker.failed.connect(self._on_failure)
        self._worker.finished.connect(self._finish_worker)
        self._worker.failed.connect(self._finish_worker)
        self._thread.start()

    def _run_model(self):
        if self._start_thread or self._thread:
            return
        self._set_busy(True)
        self.run_model_btn.setText("Starting…")
        self._start_thread = QThread(self)
        self._start_worker = OllamaModelStartWorker()
        self._start_worker.moveToThread(self._start_thread)
        self._start_thread.started.connect(self._start_worker.run)
        self._start_worker.finished.connect(self._on_model_started)
        self._start_worker.failed.connect(self._on_model_start_failed)
        self._start_worker.finished.connect(self._finish_start_worker)
        self._start_worker.failed.connect(self._finish_start_worker)
        self._start_thread.start()

    def _on_model_started(self, message: str):
        self._add_message("assistant", message, remember=False, muted=True)
        self.stop_model_btn.show()
        self._refresh_status()

    def _on_model_start_failed(self, message: str):
        self._add_message("assistant", f"Could not start the model. {message}", remember=False, muted=True)
        self._refresh_status()

    def _finish_start_worker(self):
        if self._start_thread:
            self._start_thread.quit(); self._start_thread.wait()
        if self._start_worker:
            self._start_worker.deleteLater()
        if self._start_thread:
            self._start_thread.deleteLater()
        self._start_worker = self._start_thread = None
        self.run_model_btn.setText("  Run Model")
        set_btn_icon(self.run_model_btn, "calculate")
        self._set_busy(False)

    def _stop_model(self):
        if self._stop_thread or self._thread or self._start_thread:
            return
        self._set_busy(True)
        self.stop_model_btn.setText("Stopping…")
        self._stop_thread = QThread(self)
        self._stop_worker = OllamaModelStopWorker()
        self._stop_worker.moveToThread(self._stop_thread)
        self._stop_thread.started.connect(self._stop_worker.run)
        self._stop_worker.finished.connect(self._on_model_stopped)
        self._stop_worker.failed.connect(self._on_model_stop_failed)
        self._stop_worker.finished.connect(self._finish_stop_worker)
        self._stop_worker.failed.connect(self._finish_stop_worker)
        self._stop_thread.start()

    def _on_model_stopped(self):
        self._add_message("assistant", "Model unloaded from memory.", remember=False, muted=True)
        self.stop_model_btn.hide()
        self._refresh_status()

    def _on_model_stop_failed(self, message: str):
        self._add_message("assistant", message, remember=False, muted=True)
        self.stop_model_btn.hide()
        self._refresh_status()

    def _finish_stop_worker(self):
        if self._stop_thread:
            self._stop_thread.quit(); self._stop_thread.wait()
        if self._stop_worker:
            self._stop_worker.deleteLater()
        if self._stop_thread:
            self._stop_thread.deleteLater()
        self._stop_worker = self._stop_thread = None
        self.stop_model_btn.setText("  Stop Model")
        set_btn_icon(self.stop_model_btn, "close")
        self._set_busy(False)

    def _on_reply(self, content: str):
        self._remove_thinking()
        self._add_message("assistant", content)
        self._refresh_status()

    def _on_failure(self, message: str):
        self._remove_thinking()
        self._add_message("assistant", f"I couldn't get a response. {message}", remember=False, muted=True)
        self._refresh_status()

    def _finish_worker(self):
        self._set_busy(False)
        if self._thread:
            self._thread.quit(); self._thread.wait()
        if self._worker:
            self._worker.deleteLater()
        if self._thread:
            self._thread.deleteLater()
        self._worker = self._thread = None

    def _set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.run_model_btn.setEnabled(not busy)
        self.stop_model_btn.setEnabled(not busy)
        self.attach_btn.setEnabled(not busy)
        self.input_box.setEnabled(not busy)

    # ── Chat layout helpers ───────────────────────────────────────────────────

    def _add_message(self, role: str, text: str, remember: bool = True,
                     muted: bool = False, attachments: list[str] | None = None) -> QWidget:
        if remember:
            self.messages.append({"role": role, "content": text})

        is_user = role == "user"
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(10)

        avatar = _Avatar(role)
        bubble = _Bubble(role, text, muted=muted, attachments=attachments)
        bubble.setMaximumWidth(640)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        if is_user:
            row_lay.addStretch()
            row_lay.addWidget(bubble)
            row_lay.addWidget(avatar, 0, Qt.AlignmentFlag.AlignBottom)
        else:
            row_lay.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            row_lay.addWidget(bubble)
            row_lay.addStretch()

        self.chat_layout.insertWidget(max(0, self.chat_layout.count() - 1), row)
        QTimer.singleShot(30, self._scroll_to_bottom)
        return row

    def _add_thinking(self) -> QWidget:
        """Add animated typing indicator row."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(10)

        avatar = _Avatar("assistant")

        bubble = QFrame()
        bubble.setFixedSize(68, 40)
        bubble.setStyleSheet(
            f"QFrame {{ background: {Theme.SURFACE}; border: 1px solid {Theme.BORDER};"
            f" border-radius: 18px 18px 18px 4px; }}"
        )
        b_lay = QHBoxLayout(bubble)
        b_lay.setContentsMargins(12, 0, 12, 0)
        self._typing = _TypingIndicator()
        b_lay.addWidget(self._typing)

        row_lay.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        row_lay.addWidget(bubble)
        row_lay.addStretch()

        self.chat_layout.insertWidget(max(0, self.chat_layout.count() - 1), row)
        QTimer.singleShot(30, self._scroll_to_bottom)
        return row

    def _remove_thinking(self):
        if not self._thinking_row:
            return
        if hasattr(self, "_typing"):
            self._typing.stop()
        self.chat_layout.removeWidget(self._thinking_row)
        self._thinking_row.deleteLater()
        self._thinking_row = None

    def _clear_chat(self):
        if self._thread:
            return
        self.messages.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._add_message(
            "assistant",
            "Fresh session. What would you like to explore?",
            remember=False,
        )

    def _scroll_to_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
