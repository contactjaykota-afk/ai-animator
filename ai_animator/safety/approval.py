"""Approval queue + emergency stop.

Every action that changes something on the computer becomes an
ActionRequest. It sits in the queue as PENDING until the user approves or
rejects it. Destructive actions need a second, explicit confirmation.
The emergency stop cancels everything pending and blocks new execution
until the user resets it.

Pure Python (no Qt) so it can be tested and reused by any integration.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger(__name__)


class Risk(str, Enum):
    READ_ONLY = "read-only"
    CHANGE = "change"
    DESTRUCTIVE = "destructive"   # delete, overwrite, install, ...


class Status(str, Enum):
    PENDING = "pending"
    REJECTED = "rejected"
    RUNNING = "running"
    SUCCEEDED = "succeeded"       # executed AND verified
    UNVERIFIED = "unverified"     # executed but verification failed / unavailable
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationHalted(RuntimeError):
    pass


class ConfirmationRequired(RuntimeError):
    pass


@dataclass
class ActionRequest:
    title: str                    # what the AI wants to do
    application: str              # which app it will touch
    reason: str                   # why
    expected_result: str          # what should happen
    execute: Callable[[], Any]
    risk: Risk = Risk.CHANGE
    verify: Callable[[Any], bool] | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: Status = Status.PENDING
    result: Any = None
    error: str = ""


class EmergencyStop:
    def __init__(self):
        self._event = threading.Event()

    def trigger(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    @property
    def triggered(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise AutomationHalted("Emergency stop is active")


class ApprovalQueue:
    def __init__(self, stop: EmergencyStop):
        self.stop = stop
        self._items: dict[str, ActionRequest] = {}
        self._listeners: list[Callable[[ActionRequest], None]] = []
        self._lock = threading.RLock()

    def subscribe(self, fn: Callable[[ActionRequest], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, req: ActionRequest) -> None:
        for fn in list(self._listeners):
            try:
                fn(req)
            except Exception:
                log.exception("approval listener failed")

    def pending(self) -> list[ActionRequest]:
        with self._lock:
            return [r for r in self._items.values() if r.status == Status.PENDING]

    def get(self, req_id: str) -> ActionRequest:
        return self._items[req_id]

    def submit(self, req: ActionRequest) -> ActionRequest:
        with self._lock:
            if self.stop.triggered:
                req.status = Status.CANCELLED
                req.error = "Emergency stop is active"
            self._items[req.id] = req
        log.info("Action requested [%s]: %s (%s)", req.risk.value, req.title, req.application)
        self._notify(req)
        return req

    def reject(self, req_id: str) -> ActionRequest:
        with self._lock:
            req = self._items[req_id]
            if req.status == Status.PENDING:
                req.status = Status.REJECTED
        log.info("Rejected: %s", req.title)
        self._notify(req)
        return req

    def approve(self, req_id: str, confirmed_destructive: bool = False) -> ActionRequest:
        with self._lock:
            req = self._items[req_id]
            if req.status != Status.PENDING:
                raise RuntimeError(f"Action is {req.status.value}, not pending")
            if req.risk == Risk.DESTRUCTIVE and not confirmed_destructive:
                raise ConfirmationRequired(req.title)
            try:
                self.stop.check()
            except AutomationHalted as exc:
                req.status, req.error = Status.CANCELLED, str(exc)
                self._notify(req)
                return req
            req.status = Status.RUNNING
        self._notify(req)
        log.info("Approved, running: %s", req.title)
        try:
            req.result = req.execute()
        except Exception as exc:
            req.status, req.error = Status.FAILED, f"{type(exc).__name__}: {exc}"
            log.error("Action failed: %s - %s", req.title, req.error)
            self._notify(req)
            return req
        # Never claim success without checking the result.
        if req.verify is None:
            req.status = Status.UNVERIFIED
            req.error = "No verification available for this action"
        else:
            try:
                ok = bool(req.verify(req.result))
            except Exception as exc:
                ok, req.error = False, f"verification error: {exc}"
            req.status = Status.SUCCEEDED if ok else Status.UNVERIFIED
        log.info("Action %s: %s", req.status.value, req.title)
        self._notify(req)
        return req

    def cancel_all(self, reason: str = "Emergency stop") -> int:
        n = 0
        with self._lock:
            for req in self._items.values():
                if req.status == Status.PENDING:
                    req.status, req.error = Status.CANCELLED, reason
                    n += 1
                    self._notify(req)
        return n
