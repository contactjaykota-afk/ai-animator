"""Application entry point.

    AI Animator.exe               start the app
    AI Animator.exe --self-test   check the install (no window), write a report, exit 0/1
"""
from __future__ import annotations

import json
import logging
import sys
import traceback

from ai_animator import APP_NAME, __version__

log = logging.getLogger("ai_animator")


def self_test(check_api: bool = False) -> int:
    """Verifies a packaged build: imports, resources, UI construction, screenshot."""
    import os
    import tempfile
    os.environ.setdefault("AI_ANIMATOR_HOME", tempfile.mkdtemp(prefix="aia_selftest_"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    report: dict[str, str] = {}

    def check(name, fn):
        try:
            report[name] = "ok: " + str(fn() or "")
        except Exception as exc:
            report[name] = f"FAIL: {type(exc).__name__}: {exc}"

    check("imports", lambda: __import__("anthropic").__version__)
    check("pillow", lambda: __import__("PIL").__version__)
    check("mss", lambda: __import__("mss").__version__)
    check("keyring_backend", lambda: type(__import__("keyring").get_keyring()).__name__)

    from ai_animator.core.resources import resource_path
    check("icon_resource", lambda: (resource_path("icon.png").exists() or (_ for _ in ()).throw(
        FileNotFoundError(resource_path("icon.png")))) and "found")

    def ui():
        from PySide6.QtWidgets import QApplication
        from ai_animator.ui.main_window import MainWindow
        from ai_animator.ui.state import AppState
        from ai_animator.ui.theme import STYLESHEET
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(STYLESHEET)
        state = AppState()
        p = state.projects.create_project("Self Test")
        state.set_project(p)
        win = MainWindow(state)
        win.show()
        app.processEvents()
        for key in win.pages:
            win.show_page(key)
            app.processEvents()
        win.close()
        return f"{len(win.pages)} pages"
    check("ui", ui)

    def screenshot():
        from ai_animator.core.screen import capture_screen
        img = capture_screen()
        return f"{img.width}x{img.height}"
    check("screenshot", screenshot)

    if check_api:
        def api():
            from ai_animator.ai.claude_service import ClaudeService
            from ai_animator.config.settings import SecretStore, Settings
            return ClaudeService(Settings.load(), SecretStore()).test_connection()
        check("claude_api", api)

    out = json.dumps({"app": APP_NAME, "version": __version__, "results": report}, indent=2)
    print(out)
    try:
        from ai_animator.config.settings import app_data_dir
        (app_data_dir() / "self_test_report.json").write_text(out, encoding="utf-8")
    except Exception:
        pass
    # screenshot can legitimately fail on headless CI machines; everything else must pass
    hard = [k for k, v in report.items() if v.startswith("FAIL") and k != "screenshot"]
    return 1 if hard else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test(check_api="--check-api" in argv)

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ai_animator.core.logging_setup import setup_logging
    from ai_animator.core.resources import resource_path
    from ai_animator.ui.main_window import MainWindow
    from ai_animator.ui.state import AppState
    from ai_animator.ui.theme import STYLESHEET

    setup_logging()
    if sys.platform == "win32":
        try:  # own taskbar icon instead of python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIAnimator.Studio")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    icon = resource_path("icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    def excepthook(etype, value, tb):
        log.critical("Unhandled error:\n%s", "".join(traceback.format_exception(etype, value, tb)))
        QMessageBox.critical(None, APP_NAME, f"Unexpected error:\n{value}\n\nDetails are in the log file.")
    sys.excepthook = excepthook

    state = AppState()
    state.restore_last_project()
    win = MainWindow(state)
    win.show()
    log.info("%s %s started", APP_NAME, __version__)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
