"""Logging to a rotating file in the app data folder (+ the UI activity log)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ai_animator.config.settings import app_data_dir


def setup_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(app_data_dir() / "ai_animator.log", maxBytes=2_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)
    # keep HTTP client noise out of the user-facing log
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
