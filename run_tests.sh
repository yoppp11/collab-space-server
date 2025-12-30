#!/bin/bash
# Unix/Linux shell script to run tests

echo "================================"
echo "Running Tests"
echo "================================"

case "$1" in
    unit)
        echo "Running unit tests only..."
        pytest -m unit
        ;;
    integration)
        echo "Running integration tests only..."
        pytest -m integration
        ;;
    coverage)
        echo "Running tests with coverage..."
        pytest --cov=apps --cov-report=html --cov-report=term-missing
        ;;
    fast)
        echo "Running fast tests only..."
        pytest -m "not slow"
        ;;
    parallel)
        echo "Running tests in parallel..."
        pytest -n auto
        ;;
    *)
        echo "Running all tests..."
        pytest
        ;;
esac

echo ""
echo "================================"
echo "Test run complete"
echo "================================"
