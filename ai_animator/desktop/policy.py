"""Permission profiles and the decision "may this action run without asking?".

Modes
  supervised  - every action that changes something waits for APPROVE
                (screenshots, zoom, cursor_position and wait are read-only and run freely)
  autonomous  - actions run on their own, within the profile's limits, EXCEPT anything
                on the always-confirm list, which still needs the user.

Always-confirm (both modes): deleting, overwriting, installing/uninstalling, purchases
and payments, logins/passwords/credentials, sending messages, system settings, and any
app outside the allowed list. Detection uses the foreground window title, the keys and
text involved, and Claude's own declaration via the `request_user_confirmation` tool.
These heuristics are a safety net, not a guarantee - the STOP controls stay the primary
protection.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

READ_ONLY = {"screenshot", "zoom", "cursor_position", "wait", "mouse_move"}

SENSITIVE_TITLES = {
    "delete": r"\bdelet(e|ing)\b|\bremove\b|recycle bin|\bpermanently\b",
    "overwrite": r"\breplace\b.*\bfile|\boverwrite\b|confirm save as|already exists",
    "install": r"\binstall(er|ing)?\b|\bsetup\b|\buninstall\b|user account control|\bwizard\b",
    "purchase": r"\bcheckout\b|\bpayment\b|\bpurchase\b|\bbuy\b|\bcart\b|\bbilling\b|\bpaypal\b",
    "credentials": r"\bsign[ -]?in\b|\blog[ -]?in\b|\bpassword\b|\bcredential|\b2fa\b|\bauthenticat",
    "system": r"\bregistry editor\b|\bcontrol panel\b|\bsettings\b|\btask manager\b|\bcommand prompt\b"
              r"|\bpowershell\b|\bterminal\b",
    "messaging": r"\bgmail\b|\boutlook\b|\bdiscord\b|\bslack\b|\bwhatsapp\b|\bmessenger\b",
}
DANGEROUS_KEYS = {"shift+delete": "delete", "shift+del": "delete", "delete": "delete", "del": "delete",
                  "ctrl+shift+esc": "system", "alt+f4": "close"}
DANGEROUS_TEXT = re.compile(
    r"rm\s+-rf|\bdel\s+/|\brmdir\b|remove-item|format\s+[a-z]:|\bshutdown\b|reg\s+delete|"
    r"diskpart|\bpip\s+install\b|\bnpm\s+install\b|winget\s+install|choco\s+install|curl\s+.*\|\s*(sh|bash)",
    re.I)
CATEGORY_LABELS = {
    "delete": "deleting something", "overwrite": "overwriting a file", "install": "installing or uninstalling software",
    "purchase": "a purchase or payment", "credentials": "a login, password or credential",
    "system": "system settings / terminal", "messaging": "sending a message", "close": "closing a window",
    "outside_allowed_apps": "an app outside your allowed list", "declared": "the AI flagged this as important",
}


@dataclass
class PermissionProfile:
    mode: str = "supervised"                 # "supervised" | "autonomous"
    allowed_apps: list[str] = field(default_factory=list)  # window-title keywords; empty = any app
    max_steps: int = 80                      # actions per task
    max_minutes: int = 30
    confirm_categories: list[str] = field(default_factory=lambda: list(SENSITIVE_TITLES) + ["close"])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "PermissionProfile":
        d = d or {}
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if p.mode not in ("supervised", "autonomous"):
            p.mode = "supervised"
        # these can never be switched off
        for must in ("delete", "overwrite", "install", "purchase", "credentials"):
            if must not in p.confirm_categories:
                p.confirm_categories.append(must)
        p.max_steps = max(1, min(int(p.max_steps), 1000))
        p.max_minutes = max(1, min(int(p.max_minutes), 240))
        return p


@dataclass
class Decision:
    needs_approval: bool
    reasons: list[str]
    destructive: bool = False


def classify(name: str, inp: dict, window_title: str, profile: PermissionProfile) -> Decision:
    if name in READ_ONLY:
        return Decision(False, [])
    reasons: list[str] = []
    cats: set[str] = set()
    title = (window_title or "").lower()
    for cat, pattern in SENSITIVE_TITLES.items():
        if cat in profile.confirm_categories and re.search(pattern, title):
            cats.add(cat)
    if name == "key":
        combo = str(inp.get("text", "")).lower().replace(" ", "")
        cat = DANGEROUS_KEYS.get(combo)
        if cat and cat in profile.confirm_categories:
            cats.add(cat)
    if name == "type" and DANGEROUS_TEXT.search(str(inp.get("text", ""))):
        cats.add("system")
    if profile.allowed_apps and title and not any(a.lower() in title for a in profile.allowed_apps):
        cats.add("outside_allowed_apps")
    for c in sorted(cats):
        reasons.append(CATEGORY_LABELS.get(c, c))
    destructive = bool(cats & {"delete", "overwrite", "install", "purchase", "credentials"})
    if profile.mode == "supervised":
        return Decision(True, reasons or ["supervised mode: every change is approved"], destructive)
    return Decision(bool(cats), reasons, destructive)


def describe_action(name: str, inp: dict) -> str:
    """Human-readable one-liner for the approval card and the log."""
    c = inp.get("coordinate")
    at = f" at ({c[0]}, {c[1]})" if c else ""
    mods = f" holding {inp['text']}" if inp.get("text") and name.endswith(("click", "scroll", "drag")) else ""
    if name == "type":
        t = str(inp.get("text", ""))
        return f'Type "{t[:120]}{"…" if len(t) > 120 else ""}"'
    if name == "key":
        rep = f" ×{inp['repeat']}" if inp.get("repeat", 1) != 1 else ""
        return f"Press {inp.get('text')}{rep}"
    if name == "hold_key":
        return f"Hold {inp.get('text')} for {inp.get('duration')}s"
    if name == "scroll":
        return f"Scroll {inp.get('scroll_direction')} {inp.get('scroll_amount')}{at}{mods}"
    if name == "left_click_drag":
        s = inp.get("start_coordinate")
        return f"Drag from ({s[0]}, {s[1]}) to ({c[0]}, {c[1]}){mods}" if s and c else "Drag"
    return f"{name.replace('_', ' ').capitalize()}{at}{mods}"
