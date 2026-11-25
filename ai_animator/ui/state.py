"""Shared application state that pages and panels talk through."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from ai_animator.ai.claude_service import ClaudeService
from ai_animator.config.settings import SecretStore, Settings
from ai_animator.projects.manager import Project, ProjectManager
from ai_animator.safety.approval import ActionRequest, ApprovalQueue, EmergencyStop

log = logging.getLogger(__name__)


class AppState(QObject):
    project_changed = Signal(object)          # Project | None
    task_changed = Signal(str, int)           # description, progress (-1 = busy, 0..100)
    action_updated = Signal(object)           # ActionRequest
    stop_triggered = Signal()
    log_message = Signal(str, str)            # level, text
    navigate = Signal(str)                    # page id
    settings_changed = Signal()

    def __init__(self, settings: Settings | None = None, secrets: SecretStore | None = None):
        super().__init__()
        self.settings = settings or Settings.load()
        self.secrets = secrets or SecretStore()
        self.claude = ClaudeService(self.settings, self.secrets)
        self.projects = ProjectManager(self.settings.projects_dir)
        self.stop = EmergencyStop()
        self.approvals = ApprovalQueue(self.stop)
        # the queue may notify from worker threads; Qt signals hop to the UI thread
        self.approvals.subscribe(self.action_updated.emit)
        self.project: Project | None = None

    def set_project(self, project: Project | None) -> None:
        self.project = project
        self.settings.last_project = str(project.root) if project else ""
        self.settings.save()
        self.project_changed.emit(project)
        if project:
            log.info("Opened project: %s", project.name)

    def restore_last_project(self) -> None:
        path = self.settings.last_project
        if path:
            try:
                self.set_project(self.projects.open_project(path))
            except Exception:
                log.warning("Last project could not be opened: %s", path)

    def request_action(self, req: ActionRequest) -> ActionRequest:
        return self.approvals.submit(req)

    def emergency_stop(self) -> None:
        self.stop.trigger()
        n = self.approvals.cancel_all("Emergency stop")
        log.warning("EMERGENCY STOP - automation halted, %d pending action(s) cancelled", n)
        self.stop_triggered.emit()
        self.task_changed.emit("Stopped", 0)

    def resume_after_stop(self) -> None:
        self.stop.reset()
        log.info("Emergency stop cleared - actions can be approved again")
