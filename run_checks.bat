@echo off
echo Running project checks...

:: Run auto-formatter (linting)
uv run black .

:: Run Python unit tests using the existing wrapper
uv run python scripts/run_tests.py
if errorlevel 1 (
    echo [ERROR] Tests failed!
    exit /b 1
)

echo [SUCCESS] all checks passed.
echo [INFO] Coverage report generated at: htmlcov/index.html
