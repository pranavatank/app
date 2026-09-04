"""ui/ollama_worker.py — Background worker that warms up the local Ollama model."""

import json
import os
from urllib import error as url_error
from urllib import request as url_request

from PyQt6.QtCore import QObject, pyqtSignal

from engines.statement_parser import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_KEEP_ALIVE,
    DEFAULT_OLLAMA_MODEL,
    mark_ollama_model_used,
    ollama_keep_alive_value,
)


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
