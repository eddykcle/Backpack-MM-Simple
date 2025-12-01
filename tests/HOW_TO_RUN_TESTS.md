# How to Run the Tests

## Quick Start

```bash
# From project root directory
cd /home/jailuser/git

# Run all tests
python -m unittest discover tests/

# Run with verbose output
python -m unittest discover tests/ -v
```

## Run Specific Test Files

```bash
# Test daemon manager
python -m unittest tests.test_daemon_manager

# Test CLI commands  
python -m unittest tests.test_cli_commands

# Test exceptions
python -m unittest tests.test_exceptions

# Test strategies
python -m unittest tests.test_strategies

# Test web server
python -m unittest tests.test_web_server
```

## Run Specific Test Classes

```bash
python -m unittest tests.test_daemon_manager.TestTradingBotDaemon
python -m unittest tests.test_cli_commands.TestResolveApiCredentials
```

## Run Individual Tests

```bash
python -m unittest tests.test_daemon_manager.TestTradingBotDaemon.test_init_multi_config_format
```

## What Was Tested

✓ **core/daemon_manager.py** - Process management, configuration, health checks
✓ **cli/commands.py** - CLI functions, credential resolution, client caching  
✓ **core/exceptions.py** - Custom exception classes
✓ **strategies/*.py** - Grid strategies, market making
✓ **web/server.py** - Flask endpoints, validation

## Test Statistics

- **5 test files created**
- **130+ test methods**
- **2,155+ lines of test code**
- **Coverage**: Happy paths, edge cases, error handling

## Requirements

- Python 3.11+
- unittest (standard library)
- Project dependencies (from requirements.txt)

No additional testing libraries needed!