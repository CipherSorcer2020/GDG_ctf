@echo off
REM ---------------------------------------------------------------------------
REM  One-click launcher (Windows): starts the CTF server in its own window and
REM  exposes it with a free Cloudflare Tunnel (HTTPS, no router setup).
REM
REM  The ADMIN TOKEN is printed in the "ctf-server" window - only there.
REM  Every launch WIPES scores + lobby (the old scores are saved as a backup).
REM
REM  Options (set before running):
REM    set PORT=8001          use another port
REM    set EVENT=my-event     event folder (default: this folder if it has an
REM                           event.json, otherwise "demo")
REM    set KEEP_STATE=1       do NOT wipe (resume after a crash mid-event)
REM    set HOST=0.0.0.0       same-wifi play without the tunnel (default 127.0.0.1)
REM
REM  Needs once:  setup.bat    and for the tunnel:  winget install cloudflare.cloudflared
REM ---------------------------------------------------------------------------
setlocal
set "ROOT=%~dp0"
if "%PORT%"=="" set PORT=8000
if "%HOST%"=="" set HOST=127.0.0.1
set KEEP=
if defined KEEP_STATE set KEEP=--keep

if not defined EVENT (
    if exist "%ROOT%event.json" (set "EVENT=%ROOT%") else (set "EVENT=%ROOT%demo")
)
if not exist "%EVENT%\event.json" (
    echo [!] No event.json found in "%EVENT%". Create one with:  ctf init my-event
    exit /b 1
)

if exist "%ROOT%.venv\Scripts\python.exe" (set "PY=%ROOT%.venv\Scripts\python.exe") else (set PY=python)
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
    echo [!] Port %PORT% is already in use - an old server is probably still running.
    echo     Close its window, or run with another port:  set PORT=8001 ^& run.bat
    exit /b 1
)

echo Starting CTF server on port %PORT%  (event: %EVENT%)
pushd "%EVENT%"
start "ctf-server" cmd /k call "%PY%" -m ctf_runner serve --host %HOST% --port %PORT% %KEEP%
popd
timeout /t 3 /nobreak >nul

echo.
echo  1) Look in the "ctf-server" window for the ADMIN TOKEN.
echo  2) Organizer panel:  http://localhost:%PORT%/admin
echo  3) Send players the https://....trycloudflare.com link printed below.
echo.

where cloudflared >nul 2>&1
if %errorlevel%==0 (
    cloudflared tunnel --url http://localhost:%PORT%
) else (
    echo NOTE: cloudflared is not installed - the server is local only: http://localhost:%PORT%
    echo       Install it with:  winget install cloudflare.cloudflared
    echo       (players on the same wifi can also join with HOST=0.0.0.0)
    pause
)
