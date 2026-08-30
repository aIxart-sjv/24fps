# 24FPS Backend — Windows Packaging & Deployment (Phase 20)

> **Honesty notice, read first.** This document was written from a Linux
> development machine (Arch Linux). **No Windows machine or Windows VM
> was available in this session.** Every claim below about *behavior on
> Windows specifically* is a documented, reasoned expectation based on
> (a) this codebase's existing Windows-portability design (`pathlib`
> throughout, `shell=False` subprocess execution, configurable roots),
> (b) a Linux PyInstaller build of the exact spec below, used only to
> validate the *packaging logic* (data-file bundling, entry-point
> resolution, `sys._MEIPASS` handling), and (c) published facts about
> third-party packages (e.g. `libewf-python` publishing Windows wheels).
> It is **not** a report of an actual Windows run. See the Phase 20 final
> report for the exact, itemized scope of what was and was not verified.

## 1. Packaging strategy

**PyInstaller**, one-directory build (`packaging/24fps.spec`). See that
file's own docstring for the full reasoning (why PyInstaller over Nuitka
or a native `pip install` deployment, and why one-directory over
one-file). Summary: the dependency tree (`torch`, `ultralytics`,
`opencv-python`) is large and has mature, maintained PyInstaller hooks
via `pyinstaller-hooks-contrib`; one-file mode would re-extract several
gigabytes on every launch, which is fragile for this payload size.

## 2. Distribution layout

```
24fps/
  24fps.exe                  <- entry point (built from backend/run.py)
  run_24fps.bat               <- recommended launcher (sets CWD, first-run .env)
  .env.example                 <- safe template; never a real .env
  _internal/                   <- PyInstaller onedir payload (Python runtime,
                                   torch/opencv/ultralytics, migrations/,
                                   alembic.ini, .env.example)
  ffmpeg/                       <- NOT bundled by this repo; operator-provided
                                   (see Section 5)
  data/                         <- created on first run (evidence/artifacts/
                                   reports/logs/models/case_metadata.db),
                                   sibling to the .exe once .env is copied
                                   next to it and points here
```

`_internal/` is PyInstaller 6.x's own onedir convention (not something
this project chose) -- confirmed by the Linux smoke build that
`app.bootstrap.resolve_application_root()` correctly resolves it via
`sys._MEIPASS`, which points at `_internal/` in onedir mode.

## 3. Prerequisites (target Windows machine)

- No Python installation required for an *end user* running the packaged
  `.exe` -- PyInstaller bundles the interpreter and every dependency.
- A Python installation **is** required only for *building* the package:
  **Python 3.12.x** (the only version this codebase has actually been
  run against in this session; `pyproject.toml` declares `>=3.11` as its
  floor, but numpy's PEP 695 stub syntax already forces `mypy` to target
  3.12, and 3.12 is what every dependency version below was resolved
  against — pinning the *build* machine to 3.12.x is the safest choice
  to maximize the chance every dependency, including `libewf-python`,
  resolves to a pre-built wheel rather than falling back to a source
  build that would need a C toolchain).
- FFmpeg (see Section 5) -- not bundled by this repository.
- A CUDA-capable GPU is optional (see Section 8); CPU-only operation is
  the documented, supported baseline.

## 4. Building the package (on Windows)

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller packaging\24fps.spec --distpath dist --workpath build
```

Output: `dist\24fps\` (the directory layout in Section 2). Copy
`packaging\run_24fps.bat` into `dist\24fps\` alongside `24fps.exe`.

This exact sequence has **not** been run on Windows in this session. It
was derived from the spec file, which **was** successfully smoke-built
on Linux (`pyinstaller packaging/24fps.spec`, producing a working Linux
ELF binary that started, ran migrations, and served real HTTP requests —
see the Phase 20 final report). The Windows-specific steps above (the
`.venv\Scripts\activate` path, the `.exe` extension) follow standard,
well-documented PyInstaller/Windows conventions but were not exercised.

## 5. FFmpeg on Windows

Not bundled in this repository (no Windows FFmpeg binary was available
to vendor correctly/legally in this environment). `app.media.ffmpeg` and
`app.utils.subprocess` already treat FFmpeg as a fully optional, fully
configurable external dependency — `settings.ffmpeg_path`/
`settings.ffprobe_path` (`FFMPEG_PATH`/`FFPROBE_PATH` in `.env`) accept
any absolute path, and every call site handles `FileNotFoundError`
cleanly (a controlled "unavailable" result, never a crash — see the
Phase 20 final report for the exact call sites verified).

Recommended packaging step (not automated by this repo): download the
official FFmpeg Windows build (`ffmpeg.exe`/`ffprobe.exe`), place them at
`dist\24fps\ffmpeg\`, and set in the shipped `.env`:

```
FFMPEG_PATH=./ffmpeg/ffmpeg.exe
FFPROBE_PATH=./ffmpeg/ffprobe.exe
```

If FFmpeg is left unconfigured (`FFMPEG_PATH=ffmpeg`, the default,
meaning "look on PATH"), and no FFmpeg is on PATH, `app.media.ffmpeg`'s
own availability check reports it as unavailable rather than crashing —
verify this by calling `GET /api/v1/system/health` and (once
implemented in a future phase) an FFmpeg-specific status field; today,
recording extraction itself will fail with a clear, controlled error the
first time it actually needs FFmpeg.

## 6. pyewf / E01 support on Windows

`libewf-python` (the `pyewf` bindings) publishes pre-built wheels for
`cp310`/`cp311`/`cp312`, both `win32` and `win_amd64`, per PyPI's own
file listing (verified via a package-index lookup during this phase,
not by installing on Windows). This means `pip install libewf-python`
on a Python-3.12 Windows build machine should install a working
pre-built binary without requiring a C compiler.

**Do not assume this guarantees full E01 write support.** On this
project's own Linux development machine, `pyewf` imports successfully
(`is_e01_support_available() == True`) but the installed build was
compiled **without zlib**, so EWF *write* operations
(`libewf_handle_open: write access currently not supported - compiled
without zlib`) are unavailable — 5 existing tests are still skipped for
exactly this reason (verified in this session; see the Phase 20 final
report). This is a property of the specific installed build, not of the
E01 format or this codebase's own code — it may or may not also be true
of the Windows wheel; **this has not been verified on Windows.** Report
`is_e01_support_available()` and the write-capability probe honestly
rather than assuming Windows fixes this.

## 7. YOLO / YuNet model weights on Windows

Neither is bundled into this repository or the packaged distribution
(task Phase 20 scope section 12). Both download into the configured
`AI_MODEL_ROOT` (`.env`: `AI_MODEL_ROOT=./data/models` by default) on
first use:

- `yolov8n.pt` (~6.2 MB): resolved and downloaded by `ultralytics`
  itself from its own official GitHub release the first time
  `app.ai.model_registry.load_object_detection_model` runs.
- `face_detection_yunet_2023mar.onnx` (232 KB): downloaded by
  `app.ai.model_registry._ensure_face_model_weights` from the OpenCV Zoo
  GitHub repository, **SHA-256-verified against a pinned hash on every
  download** before being written to disk or used.

Both paths already handle "no network" / "download failed" / "hash
mismatch" as a clean `ModelLoadResult(available=False, error=...)`
rather than crashing (verified by reading the code in this session; the
actual download was exercised and succeeded on this Linux machine — see
the Phase 20 final report). Offline operation without pre-downloading
these files is therefore *not* supported for a brand-new `AI_MODEL_ROOT`
— this is an existing, pre-Phase-20 characteristic, not something this
phase changed. An operator who needs fully offline first-run AI can
pre-populate `AI_MODEL_ROOT` with these two files before disconnecting
network access.

## 8. GPU (CUDA) on Windows

`app.ai.device.select_device`/`is_cuda_available` use
`torch.cuda.is_available()` — the same cross-platform PyTorch API on
every OS. **On this Linux development machine, a real CUDA GPU is
present, and this session actually exercised it**: `select_device
(prefer_gpu=True)` returned `"cuda:0"`, and the YOLO model was
confirmed loaded onto `cuda:0` (verified via
`next(model.model.parameters()).device`). **This has not been repeated
on Windows** — no GPU-equipped Windows machine was available. CPU
fallback (`select_device(prefer_gpu=False)` → `"cpu"`, or automatically
when no CUDA device is detected) is the documented, safe baseline on any
machine, Windows included, and is what the existing (Linux) CI-style
test suite runs under by default.

## 9. Database / migrations

`app.bootstrap.run_database_migrations` runs `alembic upgrade head`
**programmatically** (via `alembic.command.upgrade`, not the `alembic`
CLI) on every application startup, before the health-check DB
connectivity check, resolving the bundled `migrations/` directory
relative to the running process itself (`sys._MEIPASS` when frozen) —
never relative to the current working directory, and never via
`Base.metadata.create_all()`. This was added in Phase 20 specifically
so a packaged `.exe` never requires an investigator to run an `alembic`
command by hand (Master Specification Section 65).

Verified in this session (Linux, both as a plain `python run.py`
process launched from a directory other than the repo root, and as the
actual PyInstaller-built binary): a brand-new, empty SQLite database is
correctly migrated to the current head (20 tables) on first startup, and
an already-current database is a safe no-op on subsequent restarts.

## 10. Configuration (`.env`)

Never package a real `.env` (task Phase 20 scope section 6). Ship only
`.env.example` (bundled by the spec at `_internal/.env.example`, and
copied to the distribution root); `run_24fps.bat` copies it to `.env` on
first run only if `.env` does not already exist, so it never overwrites
an operator's configuration.

| Variable | Default | Required? | Notes |
|---|---|---|---|
| `APP_ENV` | `development` | optional | `development`/`testing`/`staging`/`production` |
| `APP_VERSION` | `0.1.0` | optional | reported by `GET /system/info` |
| `DATABASE_URL` | `sqlite:///./data/case_metadata.db` | optional | relative paths resolve from CWD — see `run_24fps.bat`'s `cd /d %~dp0` |
| `EVIDENCE_ROOT` | `./data/evidence` | optional | preserved source evidence |
| `ARTIFACT_ROOT` | `./data/artifacts` | optional | derived media/AI output |
| `REPORT_ROOT` | `./data/reports` | optional | generated JSON/PDF |
| `TEMP_ROOT` | `./data/temp` | optional | |
| `LOG_ROOT` | `./data/logs` | optional | |
| `FFMPEG_PATH` | `ffmpeg` | optional | set to a bundled path if not on PATH — see Section 5 |
| `FFPROBE_PATH` | `ffprobe` | optional | |
| `LIBEWF_PATH` | *(empty)* | optional | only relevant if a non-default libewf tool location is needed |
| `AI_MODEL_ROOT` | `./data/models` | optional | see Section 7 |
| `BLOCKCHAIN_PROVIDER` | `none` | optional | `none` or `local_testnet` — **never** a real network in this build (Phase 17 scope) |
| `BLOCKCHAIN_NETWORK` | `none` | optional | |
| `MAX_WORKERS` | `4` | optional | |
| `LOG_LEVEL` | `INFO` | optional | |
| `HOST` | `127.0.0.1` | optional | added in Phase 20 for the packaged entry point |
| `PORT` | `8000` | optional | |

No variable is required to have a non-default value for a first run —
every default is a relative path safely resolved from the launcher's
`cd /d %~dp0` working directory. **No variable in this table is a
secret**; nothing in this project's configuration surface requires
credentials, API keys, or private keys today (Phase 17's blockchain
layer has no real-network mode implemented — see Section 12).

## 11. First-run procedure

1. Extract/copy the `24fps/` distribution directory anywhere writable
   (e.g. `C:\Program Files\24FPS\` or `C:\Users\<name>\24FPS\` — both
   contain spaces and/or non-ASCII-adjacent characters in the general
   case, which `pathlib`-based path handling throughout this codebase
   supports; this was not re-verified with a literal space-containing
   path on Windows in this session).
2. (Optional) Place `ffmpeg.exe`/`ffprobe.exe` under `24fps\ffmpeg\` and
   set `FFMPEG_PATH`/`FFPROBE_PATH` in `.env` accordingly (Section 5).
3. Double-click `run_24fps.bat` (not `24fps.exe` directly — the batch
   script guarantees the correct working directory and creates `.env`
   on first run).
4. On first run: `.env` is created from `.env.example`; `data\` is
   created (evidence/artifacts/reports/logs/models roots); the database
   is migrated to head; the API starts listening on `http://127.0.0.1:
   8000` (or the configured `HOST`/`PORT`).
5. Verify with a browser or `curl`: `http://127.0.0.1:8000/api/v1/health`
   should return `{"status": "ok", "database_connected": true, ...}`.
6. AI model weights download automatically the first time an AI job
   actually runs (Section 7) — this requires network access unless
   pre-provisioned.
7. Starting the frontend: this repository's frontend (`frontend/`) is a
   separate Vite/React project, currently built against **mock data**
   only (see the Phase 20 final report — no real backend integration
   layer exists in the frontend yet, a pre-existing gap this phase does
   not close). `npm run build` produces a static `dist/` that CORS-
   permits `http://localhost:5173`/`tauri://localhost` origins against
   this backend (already configured in `app.main`'s CORS middleware,
   unchanged by Phase 20) once real API wiring exists in a future phase.

## 12. Blockchain provider on Windows

Identical behavior to every other platform — `app.blockchain.provider`
reads `BLOCKCHAIN_PROVIDER`/`BLOCKCHAIN_NETWORK` from `.env`. Default
(`none`) means blockchain anchoring is unavailable by design (Phase 16
audit-chain integrity is unaffected). Setting `BLOCKCHAIN_PROVIDER=
local_testnet` enables `LocalTestBlockchainProvider` — an in-memory,
deterministic, explicitly non-real ledger (transaction references are
prefixed `LOCAL-TEST-ANCHOR-`, status is always `LOCAL_TEST`, never
`CONFIRMED`). **No real blockchain network integration exists anywhere
in this codebase** (Phase 17's own scope boundary) — this remains true
identically on Windows; there is no Windows-specific blockchain
behavior to validate.

## 13. Known limitations (Windows-specific)

- **`WindowsStorageAccess` (`app/acquisition/windows_storage.py`)
  remains an interface stub.** Every method raises `NotImplementedError`
  with a message naming this exact situation. Raw physical-drive
  acquisition (`\\.\PhysicalDriveN`) is **not implemented** — this phase
  deliberately did not implement it blind, with no Windows machine to
  test against, for a forensic tool where incorrect low-level disk I/O
  is a safety-critical risk, not merely a bug. **Native export /
  file-backed evidence acquisition (the path this project's real CP
  Plus evidence uses) is unaffected** — `FileBackedReader`/
  `EvidenceStorageReader` are built entirely on `pathlib`, which is
  fully cross-platform, and this is the acquisition path exercised by
  every existing test and by the live validation in the Phase 20 final
  report.
- No genuine clean-Windows-machine or Windows-VM testing occurred in
  this session (see Section 1's honesty notice and the Phase 20 final
  report's "Clean-machine validation status").
- GPU support on Windows is unverified (Section 8).
- `libewf-python`'s zlib/write-support limitation on Windows is
  unverified (Section 6).
