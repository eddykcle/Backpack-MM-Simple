# Backpack-MM-Simple

## Project Overview

**Backpack-MM-Simple** is a comprehensive cryptocurrency trading framework designed for market making and hedging strategies. It supports multiple exchanges (Backpack, Aster, Paradex, Lighter) and offers a modular architecture for custom strategy extension.

**Key Features:**
*   **Multi-Exchange Support:** Backpack, Aster, Paradex, Lighter.
*   **Strategy Modes:**
    *   Spot Market Making (Spread + Rebalancing)
    *   Perpetual Market Making (Position Management + Risk Neutral)
    *   Maker-Taker Hedging
    *   Grid Trading (Spot & Perpetual)
*   **Interfaces:** Web Dashboard (Flask) and Interactive CLI.
*   **Data Handling:** WebSocket for real-time data, optional SQLite logging.

## Architecture

*   **`run.py`**: Main entry point. Handles argument parsing, environment setup, and strategy execution.
*   **`api/`**: Exchange clients inheriting from `base_client.py` for standardized API interaction.
*   **`strategies/`**: Core logic for different trading strategies (`market_maker.py`, `perp_market_maker.py`, `grid_strategy.py`, etc.).
*   **`web/`**: Flask application for the web dashboard.
*   **`cli/`**: Interactive command-line interface logic.
*   **`config.py` & `.env`**: Configuration management.

## Building and Running

**Prerequisites:**
*   Python 3.8+ (Note: Python 3.13+ is currently not supported)

**Installation:**
```bash
pip install -r requirements.txt
```

**Configuration:**
Copy `.env.example` to `.env` and populate it with your API keys and proxy settings.

**Running the Application:**

The application supports three main modes:

1.  **Web Dashboard (Recommended for visual monitoring):**
    ```bash
    python run.py --web
    ```
    Access at `http://localhost:5000`.

2.  **Interactive CLI:**
    ```bash
    python run.py --cli
    ```

3.  **Quick Start / Headless Mode:**
    Run specific strategies directly via command line arguments.

    *   *Spot Market Making (Backpack):*
        ```bash
        python run.py --exchange backpack --symbol SOL_USDC --spread 0.01 --max-orders 3
        ```
    *   *Perpetual Grid (Aster):*
        ```bash
        python run.py --exchange aster --market-type perp --symbol SOLUSDT --strategy perp_grid --auto-price --grid-num 10
        ```

## Development Conventions

*   **Code Style:** Follows standard Python PEP 8 guidelines.
*   **Logging:** Uses a centralized logger (`core.logger`). Logs are stored in `logs/` and can be optionally written to SQLite.
*   **Safety:** API keys are strictly managed via environment variables.
*   **Extension:** New exchanges should inherit from `api.base_client.BaseClient`. New strategies should follow the pattern in `strategies/`.
