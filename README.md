<h1 align="center">Market Making Simulator 📈</h1>

<p align="center">
  <strong>A professional-grade quoting simulator using the Avellaneda-Stoikov model on live Binance data and historical backtesting.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-blue.svg" />
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-Live%20Dashboard-FF4B4B.svg" />
  <img alt="Binance" src="https://img.shields.io/badge/Binance-WebSocket-F3BA2F.svg" />
  <img alt="Status" src="https://img.shields.io/badge/Status-Active-brightgreen.svg" />
</p>

---

## ⚡ Overview

This repository features a comprehensive market making simulation suite that illustrates the intersection of deterministic infrastructure and stochastic control theory. The simulator includes both live trading demonstrations and historical backtesting capabilities.

The live simulator connects to real-time crypto markets (via free Binance WebSockets), computes high-frequency bid/ask quotes dynamically based on inventory exposure, and visualizes live P&L data using a sleek Streamlit dashboard.

The backtesting module allows for offline analysis using synthetic or historical data, enabling strategy optimization and performance evaluation across different market conditions.

It replicates the fundamental architecture of what quantitative developers handle at firms like Jane Street—from maintaining low-latency data feeds to implementing risk limits and automated kill switches against drawdowns.

---

## 🚀 Features

- **Live Order Book Sync:** Streams real `BTCUSDT` and `ETHUSDT` tick data over WebSockets (latency-optimized background threading).
- **Dynamic Quoting (Avellaneda-Stoikov):** Calculates optimal bid and ask spreads using stochastic control parameters.
  - Generates a tailored **Reservation Price** factoring in your current inventory skew.
  - Dynamically widens or narrows **Optimal Spread** based on market volatility and set liquidity density.
- **Advanced Market Regime Detection:** Real-time classification into CALM, TRENDING, and VOLATILE states with confidence scoring.
- **Volatility Estimation:** Rolling window standard deviation with 100-tick history for adaptive risk management.
- **Microprice Calculator:** Order book weighting for divergence signals and reservation price adjustments.
- **Dynamic Position Sizing:** Kelly-inspired sizing with multi-factor adjustment (confidence, volatility, inventory utilization).
- **Adverse Selection Analysis:** Toxicity detection measuring quote fill quality and execution costs.
- **Simulated Real-time Fills:** Top-of-book crossover deterministic matching system. Watch your inventory spike as market swings trigger fill conditions against your quotes!
- **Strict Risk Management Layer:** Built-in "Kill Switch" circuitry that bounds maximum inventory ($BTC/$ETH) and caps unrealized drawdowns.
- **Live Analytical Dashboard:** Instant visualization of realized/unrealized P&L, quote distribution relative to mid-price, and inventory positioning using responsive Plotly charts.
- **Historical Backtesting:** Run the strategy on synthetic or historical data to evaluate performance, optimize parameters, and analyze different market regimes.
- **Synthetic Data Generation:** Generate realistic market data with configurable volatility regimes, order flow imbalance, and microprice dynamics.
- **Backtest Reporting:** Automated HTML reports with detailed P&L analysis, trade logs, and performance metrics.
- **Parameter Sensitivity Analysis:** Grid search optimization across gamma and liquidity parameters.
- **Performance Analytics:** Sharpe/Sortino ratios, max drawdown, win rate, and rolling statistics.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    %% Styling
    classDef external fill:#f3ba2f,stroke:#333,stroke-width:2px,color:#000
    classDef layer fill:#2b2b2b,stroke:#00a8ff,stroke-width:2px,color:#fff
    classDef presentation fill:#ff4b4b,stroke:#333,stroke-width:2px,color:#fff

    %% External Data Source
    Binance{{"Binance WebSocket<br/>(Live Order Book)"}}:::external

    %% Simulator Components
    subgraph Simulator Data Flow
        Streamer["Data Layer<br/>(stream.py)"]:::layer
        Model["Strategy Layer<br/>(model.py)"]:::layer
        Engine["Execution Engine<br/>(engine.py)"]:::layer
        Risk["Risk Manager<br/>(risk.py)"]:::layer
    end

    %% Presentation
    Dashboard["Streamlit Dashboard<br/>(dashboard.py)"]:::presentation
    Charts[("Plotly Real-time Charts")]:::layer

    %% Edges
    Binance -- "Tick Data (bestBid/Ask)" --> Streamer
    Streamer -- "Live Top-of-Book" --> Dashboard
    
    Dashboard -- "Mid Price" --> Model
    Engine -. "Current Position" .-> Model
    Model -- "Optimal Quotes & Spread" --> Dashboard

    Dashboard -- "Evaluate Quotes vs Market" --> Engine
    Engine -- "Simulated Fills (Inventory + P&L)" --> Dashboard
    
    Engine -- "Risk Metrics" --> Risk
    Risk -- "Kill Switch / Halts" --> Dashboard
    
    Dashboard -- "Metrics Render" --> Charts
```

The simulator is built entirely in Python, reflecting a modular, micro-service-like component design:

```text
📁 mm-simulator/
├── stream.py          # WebSocket Manager feeding order-book top states to shared memory
├── model.py           # Core Math (Avellaneda-Stoikov parameterizations + AI prediction)
├── engine.py          # Virtual matching engine assessing real-market hits against our quotes
├── risk.py            # Independent observer enforcing threshold logic to halt trading
├── dashboard.py       # Streamlit GUI coordinating threads, state loops, and Plotly UI
├── backtest.py        # Historical backtesting engine for strategy evaluation
├── generate_history.py # Synthetic market data generator with regime shifts
├── volatility.py      # Real-time volatility estimation and regime detection
├── sizing.py          # Dynamic position sizing with Kelly-inspired logic
├── analytics.py       # Adverse selection analysis and performance metrics
├── dashboard_utils.py # Professional visualization components for Streamlit
├── history.csv        # Generated historical/synthetic market data
├── backtest_report.html # Automated backtest performance report
├── COMPLETION_REPORT.md # Detailed implementation checklist and status
├── ENHANCEMENTS.md   # Comprehensive enhancement documentation
├── requirements.txt   # Python dependencies
└── README.md
```

### Enhanced Modules Overview

The simulator has been significantly enhanced with four new specialized modules:

- **`volatility.py`**: Implements `VolatilityEstimator`, `RegimeDetector`, and `MicropriceCalculator` classes for real-time market analysis.
- **`sizing.py`**: Contains `DynamicSizer` for Kelly-inspired position sizing with multi-factor risk adjustment.
- **`analytics.py`**: Provides `AdverseSelectionAnalyzer`, `ParameterSensitivityAnalyzer`, and `PerformanceAnalytics` for comprehensive strategy evaluation.
- **`dashboard_utils.py`**: Professional visualization utilities including `SessionAnalytics` and multiple chart creation functions.

### Documentation

- **`COMPLETION_REPORT.md`**: Detailed checklist of all implemented features and validation results.
- **`ENHANCEMENTS.md`**: Comprehensive documentation of all enhancements, code changes, and testing outcomes.

---

## 📊 System Diagrams

### Use Case Diagram (Requirements)
```mermaid
flowchart LR
    %% Styling
    classDef actor fill:#8e44ad,stroke:#fff,stroke-width:2px,color:#fff
    classDef usecase fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    
    User([Trader / Quant]):::actor
    API([Binance WebSocket]):::actor
    Data([Historical Data]):::actor

    subgraph MM Simulator
        UC1([Start / Stop Live Engine]):::usecase
        UC2([Adjust Risk & Volatility Params]):::usecase
        UC3([Monitor Live P&L & Inventory]):::usecase
        UC4([Receive Live Order Book Ticks]):::usecase
        UC5([Execute Simulated Fills]):::usecase
        UC6([Halt on Risk Limit Exceeded]):::usecase
        UC7([Generate Synthetic Data]):::usecase
        UC8([Run Historical Backtest]):::usecase
        UC9([Analyze Backtest Results]):::usecase
    end

    User --> UC1
    User --> UC2
    User --> UC3
    User --> UC7
    User --> UC8
    User --> UC9
    
    API --> UC4
    UC4 -.-> UC5
    UC5 -.-> UC3
    UC6 -.-> UC1
    
    Data --> UC8
    UC8 -.-> UC9
```

### Activity Diagram (Workflow)
```mermaid
stateDiagram-v2
    %% Styling
    classDef idleState fill:#27ae60,color:#fff,stroke:#fff,stroke-width:2px
    classDef actionState fill:#2980b9,color:#fff,stroke:#fff,stroke-width:2px
    classDef dangerState fill:#c0392b,color:#fff,stroke:#fff,stroke-width:2px
    classDef streamState fill:#2c3e50,color:#fff,stroke:#3498db,stroke-width:2px
    classDef backtestState fill:#9b59b6,color:#fff,stroke:#fff,stroke-width:2px
    
    [*] --> Idle
    Idle --> DataStream : User clicks 'Start MM'
    Idle --> GenerateData : User runs backtest
    
    state DataStream {
        [*] --> AwaitTick
        AwaitTick --> CheckRisk : Tick Received
        
        CheckRisk --> Halt : Limits Breached
        CheckRisk --> CalcQuotes : Safe
        
        CalcQuotes --> CheckFills : Bid & Ask Calculated
        CheckFills --> UpdateEngine : Market crosses Quotes
        CheckFills --> AwaitTick : No Fill
        UpdateEngine --> AwaitTick
    }
    
    state Backtest {
        [*] --> LoadData
        LoadData --> ProcessTick : Data Loaded
        
        ProcessTick --> CheckRiskBT : Tick Processed
        CheckRiskBT --> HaltBT : Limits Breached
        CheckRiskBT --> CalcQuotesBT : Safe
        
        CalcQuotesBT --> CheckFillsBT : Quotes Calculated
        CheckFillsBT --> UpdateEngineBT : Fill Occurred
        CheckFillsBT --> ProcessTick : No Fill
        UpdateEngineBT --> ProcessTick
        
        HaltBT --> GenerateReport
        ProcessTick --> GenerateReport : End of Data
        GenerateReport --> [*]
    }
    
    GenerateData --> Backtest
    Halt --> Idle : Auto-Stopped / User Resets

    class Idle idleState
    class AwaitTick actionState
    class CheckRisk actionState
    class CalcQuotes actionState
    class CheckFills actionState
    class UpdateEngine actionState
    class Halt dangerState
    class DataStream streamState
    class GenerateData backtestState
    class LoadData backtestState
    class ProcessTick backtestState
    class CheckRiskBT backtestState
    class CalcQuotesBT backtestState
    class CheckFillsBT backtestState
    class UpdateEngineBT backtestState
    class HaltBT backtestState
    class GenerateReport backtestState
```

---

## 🧮 The Math (Avellaneda-Stoikov 2008)

The core algorithm dynamically alters the mid-price to a "Reservation Price" $r(s, t)$ mapping to your inventory position $q$:

$$ r(s, t) = s - q \cdot \gamma \cdot \sigma^2 \cdot (T - t) $$

And it defines the "Optimal Spread" $\delta$:

$$ \delta = \gamma \cdot \sigma^2 \cdot (T - t) + \frac{2}{\gamma} \ln \left( 1 + \frac{\gamma}{k} \right) $$

**Where:**
- $s$: Current Mid Price
- $q$: Inventory position
- $\gamma$: Risk Aversion factor
- $\sigma$: Volatility factor
- $k$: Market liquidity density

*(We treat $(T-t)$ as $1.0$ for a continuous approximation).*

---

## 💻 Tech Stack

- **Python** (Core engine)
- **`websocket-client`** (Real-time Binance connections)
- **Streamlit** (State-managed frontend and user interaction loop)
- **Pandas & NumPy** (Fast numeric arrays and rolling dataframes)
- **Plotly** (High-performance charting)

---

## ⚙️ How to Run Locally

### 1. Prerequisites
Ensure you have Python **3.11** or higher installed. (Note: Some pre-releases like 3.14 may not support pre-compiled pandas/streamlit binaries).

### 2. Installation
Clone the repo and navigate to the project directory. Install the necessary dependencies:

```bash
cd mm-simulator
python -m pip install -r requirements.txt
```

### 3. Launching the Simulator
Start the Streamlit dashboard loop:

```bash
python -m streamlit run dashboard.py
```

### 4. Running the Demo
Once the browser window opens:
1. Hit **Start MM** in the left sidebar to connect to the Binance feed.
2. The UI will establish a connection, and high-frequency quote generation will begin!
3. Play with **Risk Aversion ($\gamma$)**, **Volatility**, and **Liquidity Density** on the fly to see how the engine instantly transforms your quoting behavior!

---

## 🔄 Backtesting

### Generating Synthetic Data
Create realistic historical data for backtesting:

```bash
python generate_history.py
```

This generates `history.csv` with configurable market conditions including volatility regimes and order flow imbalance.

### Running a Backtest
Execute the backtesting engine on the generated data:

```bash
python backtest.py
```

The script will:
- Load historical data from `history.csv`
- Run the Avellaneda-Stoikov strategy with dynamic parameters
- Generate an HTML report (`backtest_report.html`) with detailed analysis
- Display key performance metrics including Sharpe ratio, max drawdown, and trade statistics
- Perform adverse selection analysis and parameter sensitivity sweeps

### Customizing Backtest Parameters
Modify parameters in `backtest.py`:
- `gamma`: Risk aversion factor
- `k`: Liquidity density
- `ofi_weight`: Order flow imbalance sensitivity
- Adjust risk limits in the `RiskManager` initialization

---

## 🛠️ Recent Final Patch Notes (2026-04-01)
This section documents the latest code stabilizations and bug fixes applied in this session:

- UI emoji cleanup: removed decorative section icons, retained status indicators (`🟢`, `🟡`, `🔴`).
- `dashboard_utils.create_statistics_panel()` variable fix: corrected `total_pnl` usage.
- Risk logic event thresholds tightened for safe comparison (inventory `> max_inventory`, drawdown `total_pnl < max_drawdown`).
- AI confidence model enhanced in `model.py` for warm-up and model-quality scoring.
- AI return display scale adjusted in dashboard to avoid `0.000bps` for small epsilon signals.
- README.md updated with all enhanced features, new modules, and complete file structure.

---

## ⚠️ Disclaimer

This is a **simulated** trading environment designed for robust quantitative testing, portfolio planning, and demonstrating low-latency Python system design. It is completely sandbox-based and does **not** actually place orders or risk real capital on Binance. Use responsibly.
