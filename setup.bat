@echo off
REM One-time setup (Windows): creates a virtual environment and installs everything.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
echo.
echo Done. Check the content with:   .venv\Scripts\ctf lint     (run it inside the demo folder)
echo Then start the game with:       run.bat
pause
