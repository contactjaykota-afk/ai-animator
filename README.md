# AI Animator

An AI-assisted digital art and animation studio for Windows. Claude is the creative
director: it plans artwork and animation, analyzes your references, remembers your
projects, and drives drawing/animation tools, always with your approval before it changes
anything on your computer.

**Current build: Phase 1 (foundation).** See [docs/ROADMAP.md](docs/ROADMAP.md) for what's
done and what's next, and [docs/ART_DIRECTION.md](docs/ART_DIRECTION.md) for the
reference analysis.

## What works now
- Dark studio interface: Chat, Drawing/Animation/FNF studios (planned-feature screens),
  Projects, Asset Library, Settings; screen + approvals panel; task/log panel with **STOP**.
- Claude chat with live streaming, image attachments, and project memory.
- Secure API-key setup (stored in Windows Credential Manager, never in files).
- Projects with characters, **locked design details**, reference images tagged by
  **role** (style / character / anatomy / animation / composition / environment / palette),
  remembered decisions, chat history and zip backups. Originals are never overwritten.
- Approval queue: APPROVE / REJECT, typed confirmation for destructive actions,
  emergency stop (button or Shift+Esc), results verified before being called a success.
- Manual screenshot (read-only).

## Not built yet (honestly)
Image generation, drawing workspace, animation timeline, FNF export, Adobe Animate and
other app control, screen understanding and mouse/keyboard automation. These are
Phases 2-6.

## For users
Run **AI Animator Setup.exe**, keep "Create a desktop shortcut" ticked, then open
AI Animator, go to **Settings** and paste your Anthropic API key
(from console.anthropic.com). No Python needed.

- Projects: `Documents\AI Animator Projects`
- Settings and logs: `%APPDATA%\AI Animator`
- Uninstall: Windows Settings → Apps → AI Animator (your projects are kept).

## For developers
```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py                 # start the app
python -m pytest -q           # tests
python run.py --self-test     # install check (add --check-api to test the key)
build.bat                     # tests -> AI Animator.exe -> self-test -> Setup.exe
set AIA_ONEFILE=1 && pyinstaller packaging\ai_animator.spec --distpath dist\portable   # portable single file
```
`build.bat` needs Inno Setup 6 for the installer step. The GitHub Actions workflow in
`.github/workflows/windows-build.yml` builds both on a clean Windows machine, then tests:
no-Python launch, Credential Manager key storage, invalid-key handling, project saving,
real window launch, install (shortcuts), installed self-test, and uninstall (projects kept).
Passing builds on `main` are published as a GitHub Release.
