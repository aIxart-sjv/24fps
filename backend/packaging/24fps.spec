# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the 24FPS backend (Phase 20, "Windows Packaging +
End-to-End Validation").

============================================================================
WHY PYINSTALLER (and not Nuitka or a native-Python zip deployment)
============================================================================
- The dependency tree (`torch`, `ultralytics`, `opencv-python`, `reportlab`,
  `pypdf`, `libewf-python`) is large, includes compiled C-extension/CUDA
  binaries, and is exactly the kind of stack `pyinstaller-hooks-contrib`
  ships pre-built, maintained hooks for (`cv2`, `torch`, `ultralytics` are
  all covered) -- Nuitka's C-compilation model has to work through the
  same dynamic-import/binary-dependency surface with much less
  off-the-shelf coverage for this specific stack, and would need to be
  independently verified against every one of these libraries.
- "The investigator does not manually run Python/npm commands" (Master
  Specification Section 65) rules out a native/"just ship requirements.txt
  and a venv" deployment -- that still requires a working Python
  installation and a `pip install` step on the target machine.
- PyInstaller directly supports the one-dir vs one-file choice this
  project needs (see DIRECTORY VS ONE-FILE below) without a different
  tool for each.

============================================================================
DIRECTORY VS ONE-FILE PACKAGING
============================================================================
This spec builds a **one-directory** distribution (`COLLECT`, not a
single-file `EXE` with `onefile=True`). Reasons (task Phase 20 scope
section 4: "Do not force one-file packaging if it creates unnecessary
fragility"):
- `torch`/`ultralytics`/`opencv-python` bundle large binary payloads
  (CUDA runtime pieces, OpenCV shared libraries). One-file mode
  re-extracts the entire bundle into a temp directory on *every* launch,
  which is slow and fragile for a payload this large, and leaves a stale
  temp-extraction risk if the process is killed mid-extraction.
  Directory mode extracts once, at build time.
- `migrations/`, model weights (downloaded into a *separate*, user-
  configurable `AI_MODEL_ROOT`, never bundled -- see AI_MODEL_ROOT below),
  and a bundled `ffmpeg`/`ffprobe` binary are all naturally files sitting
  next to the executable in a directory build, which is exactly how
  `app.bootstrap.resolve_application_root()` (onedir: `sys.executable`'s
  own directory) expects to find them.
- A directory distribution is trivially inspectable (task Phase 20 scope
  section 33, "Check packaged output for hardcoded secrets... unsafe
  subprocess calls") -- every bundled file is a plain file on disk, not
  hidden inside a compressed single-file archive.

============================================================================
WHAT THIS SPEC BUNDLES
============================================================================
- `run.py` as the entry point (see that file's own docstring for why a
  plain `app.main:app` ASGI object cannot be the entry point).
- `migrations/` (Alembic scripts) and `alembic.ini`, so
  `app.bootstrap.run_database_migrations` can find them at
  `resolve_application_root() / "migrations"` regardless of install
  location.
- `.env.example` (never a real `.env` -- task Phase 20 scope section 6:
  "DO NOT package the developer's real .env"). The Windows launcher
  script copies this to `.env` on first run if one does not already
  exist (see `packaging/run_24fps.bat`).
- Hidden imports for `uvicorn`'s dynamically-loaded event-loop/protocol
  implementations and Alembic's own runtime modules, which PyInstaller's
  static import analysis cannot always discover on its own.
- `collect_all(...)` for `ultralytics`, `cv2`, and `torch`: these
  packages load significant portions of themselves dynamically (plugin-
  style submodule discovery for `ultralytics`, native extension loading
  for `cv2`/`torch`) that plain import-graph analysis misses.

============================================================================
WHAT THIS SPEC DELIBERATELY DOES NOT BUNDLE
============================================================================
- `ffmpeg.exe`/`ffprobe.exe`: not vendored into this repository (no
  Windows FFmpeg binary is available in this development environment to
  bundle correctly/legally-cleanly here). The build/install procedure
  (`packaging/WINDOWS_DEPLOYMENT.md`) documents downloading the official
  FFmpeg Windows build and placing it at `<dist>/ffmpeg/` at packaging
  time, with `FFMPEG_PATH`/`FFPROBE_PATH` in the shipped `.env` pointing
  there -- `app.media.ffmpeg`/`app.utils.subprocess` already treat FFmpeg
  as a fully configurable, optional external dependency (see the Phase 20
  final report), so this spec does not need to hardcode its location.
- AI model weights (`yolov8n.pt`, the YuNet ONNX file): never bundled
  into the source tree or this distribution (task Phase 20 scope section
  12: "Do not bundle huge weights unnecessarily... Do not download models
  into the source tree"). They download into the configured
  `AI_MODEL_ROOT` on first use, exactly as `app.ai.model_registry`
  already implements, integrity-checked by SHA-256 for the YuNet model.
- Real secrets/credentials/private keys: none exist in this repository to
  bundle in the first place (task Phase 20 scope section 6).

============================================================================
HOW TO BUILD (on a Windows machine, with this repo checked out)
============================================================================
    cd backend
    .venv\\Scripts\\python -m pip install -r requirements.txt
    .venv\\Scripts\\python -m pip install pyinstaller
    .venv\\Scripts\\python -m PyInstaller packaging\\24fps.spec --distpath dist --workpath build

Output: `dist/24fps/` containing `24fps.exe` and every bundled
dependency/data file. See `packaging/WINDOWS_DEPLOYMENT.md` for the full
first-run procedure.

This spec was smoke-tested on this project's own Linux development
machine (producing a Linux ELF executable, never a Windows `.exe`) purely
to validate the *packaging logic itself* -- data-file collection, entry-
point resolution, hidden-import completeness for the pure-Python/most
C-extension parts of the dependency graph. It has not been run on Windows
in this session (no Windows environment was available) -- see the Phase
20 final report for the exact, honest scope of what was and was not
validated.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# `packaging/24fps.spec` -> backend project root is one level up.
PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - PyInstaller injects SPECPATH

datas = [
    (str(PROJECT_ROOT / "migrations"), "migrations"),
    (str(PROJECT_ROOT / "alembic.ini"), "."),
    (str(PROJECT_ROOT / ".env.example"), "."),
]
binaries = []
hiddenimports = [
    # uvicorn selects its event loop and HTTP/WS protocol implementations
    # dynamically at runtime based on what is importable -- PyInstaller's
    # static analysis does not see these import paths.
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Alembic's `command.upgrade` reaches into these at runtime.
    "alembic.runtime.migration",
    "alembic.script",
    "alembic.ddl.sqlite",
]

# These three libraries load significant portions of themselves
# dynamically; `collect_all` pulls in their submodules, data files (e.g.
# ultralytics' bundled default config YAML), and any native binaries
# `pyinstaller-hooks-contrib`'s bundled hooks for them know about.
for _pkg in ("ultralytics", "cv2", "torch"):
    _pkg_datas, _pkg_binaries, _pkg_hiddenimports = collect_all(_pkg)
    datas += _pkg_datas
    binaries += _pkg_binaries
    hiddenimports += _pkg_hiddenimports

a = Analysis(  # noqa: F821 - PyInstaller injects Analysis/PYZ/EXE/COLLECT
    [str(PROJECT_ROOT / "run.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="24fps",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-compressed forensic-tool binaries are harder to
    # audit/verify (task Phase 20 scope section 33's security-review
    # spirit) and can trigger antivirus false positives on Windows.
    console=True,  # a forensic tool's own startup/migration/error output
    # must be visible, never silently hidden behind a windowed subsystem.
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="24fps",
)

if sys.platform != "win32":
    print(  # noqa: T201 - build-time diagnostic, not application logging
        "NOTE: building on a non-Windows platform. This produces a "
        f"{sys.platform} executable for packaging-logic smoke-testing "
        "only -- it is not a Windows .exe. See packaging/24fps.spec's "
        "own docstring and the Phase 20 final report.",
        file=sys.stderr,
    )
