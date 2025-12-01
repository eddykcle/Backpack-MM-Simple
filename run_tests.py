#!/usr/bin/env python3
"""
Comprehensive Test Runner
Runs all unit tests with reporting and coverage information
"""
import unittest
import sys
import os
from pathlib import Path
from io import StringIO
import time

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class ColoredTextTestResult(unittest.TextTestResult):
    """Test result class with colored output"""
    
    # ANSI color codes
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_times = {}
    
    def startTest(self, test):
        super().startTest(test)
        self.test_times[test] = time.time()
    
    def addSuccess(self, test):
        super().addSuccess(test)
        elapsed = time.time() - self.test_times.get(test, 0)
        if self.showAll:
            self.stream.write(f"{self.GREEN}✓ PASS{self.RESET} ({elapsed:.3f}s)\n")
    
    def addError(self, test, err):
        super().addError(test, err)
        if self.showAll:
            self.stream.write(f"{self.RED}✗ ERROR{self.RESET}\n")
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.showAll:
            self.stream.write(f"{self.RED}✗ FAIL{self.RESET}\n")
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.showAll:
            self.stream.write(f"{self.YELLOW}⊘ SKIP{self.RESET} ({reason})\n")


class ColoredTextTestRunner(unittest.TextTestRunner):
    """Test runner with colored output"""
    resultclass = ColoredTextTestResult


def print_header():
    """Print test suite header"""
    print("=" * 70)
    print("  COMPREHENSIVE TEST SUITE")
    print("  Python Trading Bot - Unit Tests")
    print("=" * 70)
    print()


def print_summary(result, elapsed_time):
    """Print test summary"""
    print()
    print("=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    print(f"  Tests Run: {result.testsRun}")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures:  {len(result.failures)}")
    print(f"  Errors:    {len(result.errors)}")
    print(f"  Skipped:   {len(result.skipped)}")
    print(f"  Time:      {elapsed_time:.2f}s")
    print("=" * 70)
    
    if result.wasSuccessful():
        print(f"{ColoredTextTestResult.GREEN}✓ ALL TESTS PASSED{ColoredTextTestResult.RESET}")
    else:
        print(f"{ColoredTextTestResult.RED}✗ SOME TESTS FAILED{ColoredTextTestResult.RESET}")
    
    print()


def print_failures(result):
    """Print detailed failure information"""
    if result.failures:
        print()
        print("=" * 70)
        print("  FAILURES")
        print("=" * 70)
        for test, traceback in result.failures:
            print(f"\n{ColoredTextTestResult.RED}✗ {test}{ColoredTextTestResult.RESET}")
            print(traceback)
    
    if result.errors:
        print()
        print("=" * 70)
        print("  ERRORS")
        print("=" * 70)
        for test, traceback in result.errors:
            print(f"\n{ColoredTextTestResult.RED}✗ {test}{ColoredTextTestResult.RESET}")
            print(traceback)


def discover_tests(test_dir='tests', pattern='test_*.py'):
    """Discover and load tests"""
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern=pattern)
    return suite


def run_tests(verbosity=2, failfast=False):
    """Run all tests with specified verbosity"""
    print_header()
    
    # Discover tests
    print("Discovering tests...")
    suite = discover_tests()
    
    test_count = suite.countTestCases()
    print(f"Found {test_count} tests\n")
    
    # Run tests
    runner = ColoredTextTestRunner(verbosity=verbosity, failfast=failfast)
    
    start_time = time.time()
    result = runner.run(suite)
    elapsed_time = time.time() - start_time
    
    # Print summary
    print_summary(result, elapsed_time)
    
    # Print failures if any
    if not result.wasSuccessful():
        print_failures(result)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


def run_specific_test(test_name):
    """Run a specific test by name"""
    print_header()
    print(f"Running specific test: {test_name}\n")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_name)
    
    runner = ColoredTextTestRunner(verbosity=2)
    
    start_time = time.time()
    result = runner.run(suite)
    elapsed_time = time.time() - start_time
    
    print_summary(result, elapsed_time)
    
    if not result.wasSuccessful():
        print_failures(result)
    
    return 0 if result.wasSuccessful() else 1


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run unit tests for the trading bot')
    parser.add_argument('test', nargs='?', help='Specific test to run (e.g., tests.test_daemon_manager.TestTradingBotDaemon.test_init)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Minimal output')
    parser.add_argument('-f', '--failfast', action='store_true', help='Stop on first failure')
    parser.add_argument('--list', action='store_true', help='List all available tests')
    
    args = parser.parse_args()
    
    # Determine verbosity
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 2
    
    # List tests if requested
    if args.list:
        suite = discover_tests()
        print("Available tests:")
        for test_group in suite:
            for test_case in test_group:
                for test in test_case:
                    print(f"  {test.id()}")
        return 0
    
    # Run specific test or all tests
    if args.test:
        exit_code = run_specific_test(args.test)
    else:
        exit_code = run_tests(verbosity=verbosity, failfast=args.failfast)
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())