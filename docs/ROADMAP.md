# Architecture, Dependencies, Costs and Roadmap

## Architecture in one picture

```
            ┌──────────────── Desktop UI (PySide6) ────────────────┐
            │ Chat │ Drawing │ Animation │ FNF │ Projects │ Assets │ Settings
            │ Right panel: screen + approvals │ Bottom: task, log, STOP
            └──────────────────────────┬────────────────────────────┘
                                       │
   ┌───────────────┬──────────────┬────┴─────────┬────────────────┬────────────────┐
   │ Claude service│ Workflows    │ Project store│ Safety layer    │ Integrations   │
   │ (reasoning,   │ (illustration│ (memory,     │ (approval queue,│ (Animate, PS,  │
   │  vision,      │  logo, anim, │  characters, │  emergency stop,│  Illustrator,  │
   │  planning)    │  FNF, 3D...) │  references, │  verification)  │  Blender,Krita,│
   └──────┬────────┴──────────────┤  backups)    └───────┬────────┤  Aseprite)     │
          │                       └──────────────┘       │        └────────────────┘
   ┌──────┴─────────────┐  ┌──────────────────────┐  ┌───┴──────────────────┐
   │ Image providers    │  │ Drawing / animation  │  │ Desktop control       │
   │ (pluggable: local  │  │ engines (layers,     │  │ (screenshots, vision, │
   │  ComfyUI, cloud)   │  │  timeline, export)   │  │  mouse/keyboard)      │
   └────────────────────┘  └──────────────────────┘  └───────────────────────┘
```

Key decisions:

* **Claude = brain, not paintbrush.** Claude plans, analyzes references, critiques and
  drives tools. Pixels come from image providers and our own engines. The provider
  interface (`ai/providers/base.py`) lets us swap models without touching anything else.
* **Scripting before clicking.** For each app we prefer official scripting (JSFL for
  Animate, ExtendScript/UXP for Photoshop/Illustrator, Python for Blender/Krita, Lua/CLI
  for Aseprite), then file exchange, and mouse/keyboard automation only as a last resort.
  Scripting is far more reliable than clicking on pixels.
* **Editable over flat.** Layers, separate body parts, vector where it fits, and
  editable project files (FLA via JSFL, PSD, .kra, .blend, .aseprite).
* **Safety is in the core.** Every changing action is an `ActionRequest` that needs
  APPROVE; destructive ones need a typed confirmation; STOP cancels everything; an action
  only counts as "succeeded" after verification.

## Dependencies

| Package | Why | Phase |
|---|---|---|
| PySide6 | desktop UI | 1 ✔ |
| anthropic | Claude API | 1 ✔ |
| Pillow | image loading/processing | 1 ✔ |
| mss | screenshots | 1 ✔ |
| keyring | API keys in Windows Credential Manager | 1 ✔ |
| PyInstaller + Inno Setup | `.exe` + installer | 1 ✔ |
| opencv-python | screen element detection, image ops | 2 |
| pywinauto (+ pyautogui fallback) | window/UI automation on Windows | 2 |
| numpy | image math, in-betweening | 3–4 |
| requests/websocket client | ComfyUI / cloud image APIs | 3 |
| svgwrite / skia-python (TBD) | vector & layered drawing engine | 3 |
| imageio / ffmpeg | GIF/MP4 export | 4 |

## Paid services and costs (be aware)

| Service | Needed? | Cost |
|---|---|---|
| **Anthropic API** (Claude) | Yes | Pay per use. Opus 5.5 ≈ $4 per million input tokens, $20 per million output. A normal chat turn costs about a cent or a few cents; turns with several large images cost more. Sonnet/Haiku are cheaper (switch in Settings). |
| **Image generation** | Yes, from Phase 3 | **Free option:** local ComfyUI + Stable Diffusion models (needs an NVIDIA GPU, ~8–12 GB VRAM or more). **Paid option:** a cloud image API (pay per image). We'll pick together in Phase 3 based on your hardware. |
| **LoRA style training** | Optional | Free locally with a strong GPU, or a few dollars per training run on cloud GPUs. |
| **Adobe Animate / Photoshop / Illustrator** | Optional | Creative Cloud subscription. Free alternatives supported: Krita, Blender. Aseprite is a one-time purchase. |
| **Code-signing certificate** | Optional | ~$100–400/yr. Without it Windows SmartScreen shows "Unknown publisher" on first run (click *More info → Run anyway*). |

## Roadmap

**Phase 1 — Foundation (done, this build)**
Desktop UI, Claude chat with streaming + image attachments, secure key setup, project
system with memory (characters, locked design notes, role-tagged references, notes,
chat history), backups, approval queue + STOP, manual screenshot, workflow and
integration registries, .exe/installer build pipeline, tests.

**Phase 2 — Desktop agent (the "Clicky, but more capable" core)**
* Agent loop on Claude's **computer-use tool**: screenshot → Claude decides → action → screenshot to verify → repeat, for long multi-step tasks.
* **Its own visible AI cursor**: an always-on-top, click-through overlay that animates to each target before acting, so you can watch.
* **Control-active indicator** (red screen border + tray badge) whenever it has control. It never acts silently.
* **Supervised mode**: each step (or each important step) waits for APPROVE.
  **Autonomous mode**: runs within a permission profile you set (allowed apps and folders, max steps, max time).
* Always-confirm list, even in autonomous mode: deleting or overwriting files, installs, purchases or payments, logins/passwords, sending messages.
* **Start / Pause / Resume / STOP** (STOP = button, Shift+Esc, or slamming the mouse into a screen corner).
* Recovery: if the screen doesn't match what was expected, re-look, retry another way, or stop and ask.
* Mouse/keyboard: click, double/right-click, drag, scroll, type, hotkeys, window switch/resize (pywinauto + SendInput).

**Phase 3 — Art engine**
Image provider(s), **reference library + style profiles** (Claude vision analysis of
line, shading, palette, proportions, eyes, texture → stored profile; retrieval of the right
references per task; image conditioning), optional clearly-labelled LoRA training only on
data you have rights to, layered drawing workspace (sketch →
lineart → flats → shading → FX), masked "redraw only this", transparent output,
character sheets/turnarounds, version compare, post-processing passes (grain, glitch,
palette limit).

**Phase 4 — Animation engine**
Timeline with onion skin, key poses → breakdowns → in-betweens, timing charts,
cutout/rig mode, loops, preview, PNG sequence / GIF / MP4 / sprite sheet export.

**Phase 5 — FNF Studio**
Presets (idle, sing directions, misses, custom), configurable frame counts, Sparrow
atlas + XML, offsets, Psych Engine character JSON, mod-ready folder.

**Phase 6 — App integrations (drawing *inside* real apps)**
Adobe Animate (JSFL: documents, layers, symbols, keyframes, bones, export), Photoshop and
Illustrator (scripts), Krita (Python), Aseprite (CLI/Lua). Desktop control for anything
the scripting can't reach.

**Phase 6b — 3D via Blender**
Blender's Python API: modeling, materials, textures, lights, cameras, armatures and rigging,
keyframes, physics, rendering, FBX/GLB export, plus desktop control so you can watch.

**Phase 6c — Coding agent**
Read/write project code, run commands in a sandboxed terminal, install approved
dependencies, run tests, debug and verify. Covers games, sites, tools and scripts
(Python, JS/TS, C#, C++, Lua, HTML/CSS). Folder-scoped permissions.

**Phase 7 — Polish**
Gallery of finished artwork and animations, project history browser,
End-to-end tests, performance, crash recovery/autosave, quality passes on art and
animation consistency, auto-update, code signing.
