@echo off
REM This batch file activates the local venv and runs the CLI. Double-click to execute.
SET VENV_DIR=%~dp0.venv\Scripts
IF EXIST "%VENV_DIR%\Activate.ps1" (
    REM Use PowerShell activation for proper environment; run python directly to avoid shell issues
    "%VENV_DIR%\python.exe" -m jira_worklog.cli
) ELSE (
    REM fallback: call system python
    python -m jira_worklog.cli
)
pause
