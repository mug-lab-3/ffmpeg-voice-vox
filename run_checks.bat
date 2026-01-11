@echo off
echo Running project checks...

:: Run auto-formatter (linting)
python -m black .

:: Run Python unit tests using the existing wrapper
python scripts/run_tests.py
if errorlevel 1 (
    echo [ERROR] Tests failed!
    exit /b 1
)

echo [SUCCESS] all checks passed.
