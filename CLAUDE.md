# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-exchange cryptocurrency trading bot framework supporting market making, hedging, and grid trading strategies on Backpack, Aster, Paradex, and Lighter exchanges. The system is designed with extensibility in mind to support additional exchanges and strategies.

## Common Commands

### Running the Trading Bot

The project supports multiple execution modes:

```bash
# Daemon mode (recommended for production)
.venv/bin/python3 core/daemon_manager.py start --daemon

# Check daemon status
.venv/bin/python3 core/daemon_manager.py status

# Stop daemon
.venv/bin/python3 core/daemon_manager.py stop

# Web UI mode (for development/monitoring)
python run.py --web

# CLI interactive mode
python run.py --cli

# Direct execution mode (with parameters)
python run.py --exchange backpack --symbol SOL_USDC --spread 0.01 --max-orders 3 --duration 3600 --interval 60
```

### Testing

```bash
# Run all tests
python tests/run_tests.py all

# Run specific test suite
python tests/run_tests.py config

# Generate test report
python tests/run_tests.py report

# Using pytest (if available)
pytest tests/

# Using unittest directly
python -m unittest discover tests
```

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Architecture Overview

### Multi-Layer Configuration System

The project uses a sophisticated configuration management system with two formats:

1. **Legacy Format**: Single `config/daemon_config.json` file with all settings
2. **Multi-Config Format**: Structured configuration split into four sections:
   - `metadata`: Configuration metadata (name, description, exchange, strategy)
   - `daemon_config`: Process management settings
   - `exchange_config`: Exchange-specific settings
   - `strategy_config`: Strategy parameters

Configuration files support environment variable interpolation using `${VARIABLE_NAME}` syntax. Sensitive values (API keys) **must** use environment variables via the `.env` file.

Configuration directory structure:
- `config/templates/`: Template configurations for quick setup
- `config/active/`: Active configuration files
- `config/archived/`: Archived configurations
- `config/daemon_config.json`: Main daemon configuration

### Exchange Client Architecture

All exchange clients inherit from `BaseClient` (api/base_client.py) which defines a standardized interface. This abstraction enables:

- Consistent API across different exchanges
- Easy addition of new exchanges by implementing the base interface
- Standardized data structures (OrderResult, PositionInfo, BalanceInfo, etc.)

Each exchange client handles:
- Authentication (varies by exchange: API key/secret for Backpack/Aster, StarkNet signatures for Paradex, wallet signatures for Lighter)
- REST API interactions
- WebSocket connections for real-time data
- Order management and position tracking
- Exchange-specific quirks and error handling

### Strategy Architecture

Strategies are independent modules in `strategies/` directory:

- `market_maker.py`: Spot market making with multi-layer orders and rebalancing
- `perp_market_maker.py`: Perpetual futures market making with position management
- `maker_taker_hedge.py`: Maker order placement with immediate taker hedge on fill
- `grid_strategy.py`: Spot grid trading for range-bound markets
- `perp_grid_strategy.py`: Perpetual futures grid trading (neutral/long/short modes)

Each strategy implements:
- Order placement logic based on market conditions
- Position/inventory management
- Risk controls (stop-loss, take-profit, position limits)
- Statistics tracking and reporting

### Daemon Management System

The daemon manager (`core/daemon_manager.py`) provides production-grade process management:

- Background process execution (replaces nohup)
- Automatic restart on crash
- Health monitoring (CPU, memory usage)
- Graceful shutdown on SIGTERM/SIGINT
- Log rotation and cleanup
- PID file management

Key features:
- Reads configuration from `config/daemon_config.json` or multi-config format
- Supports both legacy and new configuration formats
- Periodic health checks and automatic recovery
- Structured logging via `core/log_manager.py`

### Logging System

Advanced logging system (`core/log_manager.py` and `core/logger.py`) with:

- Structured JSON logging for machine parsing
- Console output with color coding
- File rotation and compression
- Process-specific log files
- Automatic cleanup of old logs based on retention policy
- Multi-level logging (strategy decisions, market state, execution results)

## Key Implementation Details

### Configuration Parameter Reading

When developing new features or strategies, **always** read parameters from configuration files, not hardcoded values. The system uses:

1. Environment variables (`.env` file) for sensitive data
2. JSON configuration files for strategy parameters
3. Command-line arguments for quick testing/overrides

Priority order: CLI args > config file > environment variables > defaults

### Signal Handling

The `StrategySignalHandler` in `run.py` ensures graceful shutdown:
- Captures SIGTERM/SIGINT during strategy execution
- Calls strategy's `stop()` method for cleanup
- Prevents data loss and ensures proper position closing

### WebSocket Integration

Real-time market data is handled via `ws_client/client.py`:
- Maintains persistent connections to exchange WebSocket endpoints
- Automatic reconnection on disconnection
- Proxy support via HTTP_PROXY/HTTPS_PROXY environment variables

### Database Management

Optional SQLite database (`database/db.py`) for trade history:
- Controlled by `ENABLE_DATABASE` environment variable (default: disabled)
- Records order executions, fills, and P&L
- Can be disabled for performance in high-frequency scenarios

### Proxy Configuration

Global proxy support for all exchanges (both REST and WebSocket):
```bash
# In .env file
HTTP_PROXY=http://user:pass@host:port
HTTPS_PROXY=https://user:pass@host:port
```

Handled by `api/proxy_utils.py` for consistent proxy application.

## Strategy Development Guidelines

When implementing new strategies:

1. **Inherit from appropriate base class**: Use existing strategies as templates
2. **Implement required methods**:
   - `run(duration_seconds, interval_seconds)`: Main execution loop
   - `stop()`: Graceful shutdown and cleanup
   - `get_stats()`: Return current statistics for monitoring
3. **Use standardized data structures**: Leverage OrderResult, PositionInfo, etc. from base_client.py
4. **Handle errors gracefully**: Log errors but don't crash on single failures
5. **Respect position limits**: Always check max_position and position_threshold
6. **Track statistics**: Update buy/sell counts, fees, P&L for web dashboard
7. **Support stop signals**: Check `self.running` flag in loops

## Exchange Integration Guidelines

When adding a new exchange:

1. Create new client in `api/` directory (e.g., `new_exchange_client.py`)
2. Inherit from `BaseClient` and implement all abstract methods:
   - `get_balance()`, `get_open_orders()`, `place_order()`, `cancel_order()`
   - `get_ticker()`, `get_market_info()`, `get_orderbook()`
   - For perpetuals: `get_position()`, `close_position()`
3. Handle authentication in client's `__init__` or dedicated auth method
4. Add exchange configuration to `config.py`
5. Update `run.py` to support new exchange in argument parsing
6. Create configuration template in `config/templates/`
7. Test with CLI mode before enabling in Web UI

## File Organization Principles

- `api/`: Exchange API clients (one file per exchange)
- `strategies/`: Trading strategy implementations
- `core/`: System-level services (logging, daemon, config management)
- `web/`: Flask web dashboard (server, templates, static assets)
- `cli/`: Interactive command-line interface
- `config/`: Configuration files and templates
- `utils/`: Shared utilities and helpers
- `tests/`: Unit tests and integration tests
- `docs/`: Documentation (strategy guides, system docs)

## Important Notes

### Primary Execution Mode

The daemon manager is the preferred production execution mode:
```bash
.venv/bin/python3 core/daemon_manager.py start --daemon
```

This ensures:
- Background execution
- Automatic restart on failure
- Proper log management
- Health monitoring

### Configuration Management

Core configuration is in `config/daemon_config.json`. When adding parameters:
- Update config schema in `core/config_manager.py`
- Add validation in `validate_config()` method
- Support environment variable interpolation where appropriate
- Never hardcode sensitive values (API keys, secrets)

### Testing Requirements

When modifying core functionality:
- Add unit tests in `tests/` directory
- Follow naming convention: `test_*.py` for files, `test_*` for methods
- Run tests before committing: `python tests/run_tests.py all`
- Ensure tests pass in clean environment

### Input Validation

Security-critical: Use `utils/input_validation.py` framework for all user inputs:
- Validate exchange names, symbols, numeric parameters
- Prevent command injection in shell execution
- Sanitize file paths and configuration values

### Multi-Instance Support

The system supports running multiple bots simultaneously:
- Each instance should use a separate configuration file
- Use distinct log files (configured in daemon_config)
- Ensure no port conflicts for web dashboard
- Monitor resource usage (CPU/memory limits in config)

## Reference Documentation

- Backpack API: `Reference/Backpack_Exchange_API.json`
- Code structure: `Reference/codemap.md`
- Strategy guides: `docs/strategies/` directory
- System architecture: `docs/system/` directory
- Cursor AI rules: `.kilocode/rules/Backpack_coding.md`

## Python Version

- **Supported**: Python 3.8 - 3.12
- **Not supported**: Python 3.13+ (dependency compatibility issues)
- **Recommended**: Python 3.11 (best compatibility)
