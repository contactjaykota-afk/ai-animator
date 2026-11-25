@echo off
REM One-click Windows build: tests -> AI Animator.exe -> self-test -> AI Animator Setup.exe
REM Needs (developer machine only): Python 3.11+ and Inno Setup 6. End users need neither.
setlocal
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv || goto :fail )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :fail
pip install -r requirements.txt || goto :fail
python -m pytest -q || goto :fail
pyinstaller --noconfirm --clean packaging\ai_animator.spec || goto :fail
"dist\AI Animator\AI Animator.exe" --self-test || goto :fail
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 not found - skipping installer. Get it from https://jrsoftware.org/isdl.php
  goto :done
)
%ISCC% packaging\installer.iss || goto :fail
:done
echo.
echo BUILD OK:
echo   dist\AI Animator\AI Animator.exe
echo   dist\AI Animator Setup.exe
exit /b 0
:fail
echo BUILD FAILED
exit /b 1
