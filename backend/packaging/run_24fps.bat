@echo off
REM ============================================================================
REM 24FPS backend launcher (Phase 20, "Windows Packaging + End-to-End
REM Validation").
REM
REM Runs the packaged 24fps.exe with the correct working directory and a
REM first-run .env setup step. Never packaged with a real .env -- this
REM script copies .env.example to .env only if .env does not already
REM exist, so an operator's real configuration is never overwritten.
REM
REM WHY "cd /d %~dp0" FIRST:
REM Double-clicking an .exe from Windows Explorer usually sets the working
REM directory to the .exe's own folder, but a desktop shortcut ("Start in"
REM field), a scheduled task, or a different launch method can set it to
REM something else entirely (task Phase 20 scope section 8: "Do not
REM assume working directory is repository root"). `app.bootstrap`
REM resolves migrations/data-file locations independent of CWD (verified
REM via sys._MEIPASS / sys.executable), but pydantic-settings' `.env` file
REM loading in app.config.Settings uses a CWD-relative path -- this line
REM guarantees CWD is always this script's own directory (where .env is
REM expected to sit next to 24fps.exe), regardless of how this script was
REM launched.
REM ============================================================================

cd /d %~dp0

if not exist ".env" (
    echo No .env found -- copying .env.example to .env for first run.
    copy /Y ".env.example" ".env" >nul
    echo A default .env has been created at %~dp0.env
    echo Edit it now if you need non-default evidence/artifact/report paths,
    echo FFmpeg location, or blockchain provider configuration, then re-run
    echo this script.
)

echo Starting 24FPS backend...
echo Logs: %~dp0data\logs\application.log
echo API:  http://127.0.0.1:8000/api/v1/health  (or your configured HOST:PORT)
echo.

"%~dp024fps.exe"

set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
    echo.
    echo 24FPS backend exited with code %EXITCODE%.
    echo Check %~dp0data\logs\application.log for details.
    pause
)
