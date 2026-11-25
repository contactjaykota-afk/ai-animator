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


def self_test(argv: list[str]) -> int:
    """Verifies an installed/packaged build without touching the user's data.

    Writes a JSON report (path from --report <file>, default: temp folder) because a
    windowed .exe has no console. Exit code 0 = all hard checks passed.
    Each result is "ok: ...", "warn: ..." (non-fatal) or "FAIL: ...".
    """
    import os
    import tempfile
    from pathlib import Path

    check_api = "--check-api" in argv
    report_path = None
    if "--report" in argv and argv.index("--report") + 1 < len(argv):
        report_path = Path(argv[argv.index("--report") + 1])
    # isolate everything the test creates (settings, projects) in a temp folder
    os.environ["AI_ANIMATOR_HOME"] = tempfile.mkdtemp(prefix="aia_selftest_")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    report: dict[str, str] = {}

    def check(name, fn):
        try:
            value = fn()
            report[name] = value if isinstance(value, str) and value.startswith("warn:") \
                else "ok: " + str(value if value is not None else "")
        except Exception as exc:
            report[name] = f"FAIL: {type(exc).__name__}: {exc}"

    check("python_bundled", lambda: f"{sys.version.split()[0]} frozen={getattr(sys, 'frozen', False)}")
    check("anthropic", lambda: __import__("anthropic").__version__)
    check("pillow", lambda: __import__("PIL").__version__)
    check("mss", lambda: __import__("mss").__version__)

    from ai_animator.core.resources import resource_path

    def icon():
        for name in ("icon.png", "icon.ico"):
            if not resource_path(name).exists():
                raise FileNotFoundError(resource_path(name))
        return "found"
    check("resources", icon)

    def vault():
        import keyring
        backend = type(keyring.get_keyring()).__name__
        if sys.platform == "win32" and "Win" not in backend:
            raise RuntimeError(f"expected Windows Credential Manager, got {backend}")
        from ai_animator.config.settings import SecretStore, Settings
        # separate service name: never touches the user's real saved key
        store = SecretStore(service="AI Animator SelfTest", use_env=False)
        dummy = "sk-ant-selftest-0000000000000000"
        store.set_api_key(dummy)
        try:
            if store.get_api_key() != dummy:
                raise RuntimeError("key read back does not match")
            Settings.load().save()
            home = Path(os.environ["AI_ANIMATOR_HOME"])
            for f in home.rglob("*"):
                if f.is_file() and dummy.encode() in f.read_bytes():
                    raise RuntimeError(f"API key leaked into {f}")
        finally:
            store.clear_api_key()
        if store.get_api_key() is not None:
            raise RuntimeError("key was not removed")
        return f"{backend}: save/read/remove ok, not written to disk"
    check("api_key_vault", vault)

    def invalid_key():
        import anthropic
        from ai_animator.ai.claude_service import ClaudeService, friendly_error
        from ai_animator.config.settings import SecretStore, Settings

        class FixedKey(SecretStore):
            def get_api_key(self):
                return "sk-ant-invalid-selftest-key"
        try:
            ClaudeService(Settings.load(), FixedKey(backend=None)).test_connection()
        except anthropic.AuthenticationError as exc:
            msg = friendly_error(exc)
            if "invalid" not in msg:
                raise RuntimeError(f"unfriendly message: {msg}")
            return "invalid key rejected with a friendly message"
        except anthropic.APIConnectionError:
            return "warn: no internet - invalid-key check skipped"
        raise RuntimeError("an invalid key was accepted")
    check("api_key_invalid_handling", invalid_key)

    def projects():
        from ai_animator.config.settings import Settings
        from ai_animator.projects.manager import ProjectManager
        from PIL import Image
        pm = ProjectManager(Settings.load().projects_dir)
        p = pm.create_project("Self Test Project", "check", "character")
        ch = p.add_character("Test Hero", "round head", "always wears a red scarf")
        img = Path(os.environ["AI_ANIMATOR_HOME"]) / "ref.png"
        Image.new("RGB", (32, 32), (200, 40, 50)).save(img)
        ref = p.import_reference(img, ["style"], character_id=ch.id)
        p.add_memory_note("eyes glow yellow")
        p.append_chat({"role": "user", "content": [{"type": "text", "text": "hi"}], "display": "hi"})
        backup = p.backup("self test")
        again = ProjectManager(pm.projects_dir).open_project(p.root)
        ok = (again.characters()[0].design_notes == "always wears a red scarf"
              and again.references()[0].roles == ["style"]
              and again.reference_path(ref).exists() and len(again.load_chat()) == 1
              and "eyes glow yellow" in again.memory_summary() and backup.exists())
        if not ok:
            raise RuntimeError("project data did not survive save/reopen")
        return "create/save/reopen/backup ok"
    check("project_saving", projects)

    def ui():
        from PySide6.QtWidgets import QApplication
        from ai_animator.ui.main_window import MainWindow
        from ai_animator.ui.state import AppState
        from ai_animator.ui.theme import STYLESHEET
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(STYLESHEET)
        state = AppState()
        state.restore_last_project()
        win = MainWindow(state)
        win.show()
        app.processEvents()
        for key in win.pages:
            win.show_page(key)
            app.processEvents()
        win.close()
        return f"{len(win.pages)} pages built"
    check("ui", ui)

    def screenshot():
        from ai_animator.core.screen import capture_screen
        img = capture_screen()
        return f"{img.width}x{img.height}"
    check("screenshot", screenshot)

    def desktop_control():
        if sys.platform != "win32":
            return "warn: desktop control is Windows-only"
        from ai_animator.desktop.input_backend import WindowsInput
        pos = WindowsInput().cursor_position()   # read-only: never moves the mouse here
        return f"input ready, cursor at {pos}"
    check("desktop_control", desktop_control)

    if check_api:
        def api():
            from ai_animator.ai.claude_service import ClaudeService
            from ai_animator.config.settings import SecretStore, Settings
            return "served by " + ClaudeService(Settings.load(), SecretStore()).test_connection()
        check("claude_api_live", api)

    # Screenshots need a real desktop; on headless build machines that is a warning.
    if report.get("screenshot", "").startswith("FAIL") and os.environ.get("AI_ANIMATOR_HEADLESS"):
        report["screenshot"] = "warn: " + report["screenshot"][6:]
    out = json.dumps({"app": APP_NAME, "version": __version__, "results": report}, indent=2)
    try:
        print(out)
    except Exception:
        pass  # windowed exe: no console
    target = report_path or Path(tempfile.gettempdir()) / "ai_animator_self_test.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
    except Exception:
        pass
    return 1 if any(v.startswith("FAIL") for v in report.values()) else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test(argv)

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
