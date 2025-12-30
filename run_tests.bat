@echo off
REM Windows batch script to run tests

echo ================================
echo Running Tests
echo ================================

if "%1"=="unit" (
    echo Running unit tests only...
    pytest -m unit
) else if "%1"=="integration" (
    echo Running integration tests only...
    pytest -m integration
) else if "%1"=="coverage" (
    echo Running tests with coverage...
    pytest --cov=apps --cov-report=html --cov-report=term-missing
) else if "%1"=="fast" (
    echo Running fast tests only...
    pytest -m "not slow"
) else if "%1"=="parallel" (
    echo Running tests in parallel...
    pytest -n auto
) else (
    echo Running all tests...
    pytest
)

echo.
echo ================================
echo Test run complete
echo ================================
