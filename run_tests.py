#!/usr/bin/env python
"""
Test runner script for running different test suites.

Usage:
    python run_tests.py                  # Run all tests
    python run_tests.py --unit           # Run only unit tests
    python run_tests.py --integration    # Run only integration tests
    python run_tests.py --coverage       # Run with coverage report
    python run_tests.py --fast           # Run fast tests only
    python run_tests.py --app users      # Run tests for specific app
"""
import sys
import subprocess
import argparse


def run_command(cmd):
    """Run a shell command and return the exit code."""
    print(f"\n{'='*80}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*80}\n")
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Run tests for the project')
    parser.add_argument('--unit', action='store_true', help='Run only unit tests')
    parser.add_argument('--integration', action='store_true', help='Run only integration tests')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage report')
    parser.add_argument('--fast', action='store_true', help='Run only fast tests (exclude slow)')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    parser.add_argument('--app', type=str, help='Run tests for specific app (e.g., users, workspaces)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--failfast', '-x', action='store_true', help='Stop on first failure')
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ['pytest']
    
    # Add markers
    if args.unit:
        cmd.extend(['-m', 'unit'])
    elif args.integration:
        cmd.extend(['-m', 'integration'])
    elif args.fast:
        cmd.extend(['-m', 'not slow'])
    
    # Add coverage
    if args.coverage:
        cmd.extend([
            '--cov=apps',
            '--cov-report=html',
            '--cov-report=term-missing',
        ])
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(['-n', 'auto'])
    
    # Add specific app
    if args.app:
        cmd.append(f'apps/{args.app}/tests/')
    
    # Add verbose
    if args.verbose:
        cmd.append('-v')
    
    # Add fail fast
    if args.failfast:
        cmd.append('-x')
    
    # Run tests
    exit_code = run_command(cmd)
    
    # Print summary
    print(f"\n{'='*80}")
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print(f"{'='*80}\n")
    
    if args.coverage and exit_code == 0:
        print("Coverage report generated at: htmlcov/index.html")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
