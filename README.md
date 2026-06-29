# GasTradingAgents: Multi-Agent LLM Framework for Natural-Gas Trading

> Based on [TradingAgents](https://github.com/TauricResearch/TradingAgents) by [Tauric Research](https://github.com/TauricResearch) — see [Acknowledgements](#acknowledgements).

---

<div align="center">

🚀 [GasTradingAgents](#gastradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 📦 [Package Usage](#gastradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Acknowledgements](#acknowledgements)

</div>

## GasTradingAgents Framework

GasTradingAgents is a multi-agent framework that mirrors the dynamics of a real-world gas trading desk. By deploying specialized LLM-powered agents — from fundamentals, sentiment, and technical analysts, to trader and risk management — the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

> **GasTradingAgents is a gas-trading-desk build.** It trades **both** Dutch **TTF** front-month (`TTF=F`, EUR/MWh) and US **Henry Hub** front-month (`NG=F`, USD/MMBtu) as first-class instruments; each is the other's alpha benchmark (the TTF–Henry Hub spread). Instrument identity, currency units, and agent framing resolve per-contract from an instrument-profile table. Henry Hub currently runs without a supply/demand fundamentals analyst (no US storage/flow/weather vendors yet). The equity and crypto code paths from upstream have been removed: the "fundamentals" analyst reads the gas supply/demand balance (storage, weather, pipeline flows, EUA carbon) instead of company financials, and sentiment is read from the energy news flow rather than StockTwits/Reddit.


<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> GasTradingAgents is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. It is not intended as financial, investment, or trading advice.

Our framework decomposes complex trading tasks into specialized roles.

### Analyst Team
- Fundamentals Analyst (gas supply/demand): Builds the European gas balance from AGSI+ storage fill, NW-Europe heating/cooling degree days, Norway pipeline + LNG sendout flows, and EUA carbon (coal-gas switching) to read whether the balance is tight or loose.
- Sentiment Analyst (energy positioning): Reads desk positioning from the energy news flow — supply outages, LNG cargoes, storage headlines, weather scares, Norway maintenance — since gas has no retail cashtag feed.
- News Analyst: Monitors global news, euro-area macro indicators (FRED), and prediction-market probabilities, interpreting the impact of events on the gas market.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) on the traded gas contract (TTF=F or NG=F) to detect trading patterns, accounting for front-month seasonality and roll.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions, determining the timing and magnitude of trades.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone GasTradingAgents:
```bash
git clone https://github.com/<you>/GasTradingAgents.git
cd GasTradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.12
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

GasTradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
```

Gas data sources: **FRED** (euro-area macro) and **GIE AGSI+** (gas storage) need free keys; ENTSOG pipeline flows, Open-Meteo weather, Polymarket, and EUA carbon (via yfinance) are keyless.

```bash
export FRED_API_KEY=...            # FRED macro data (https://fred.stlouisfed.org)
export GIE_API_KEY=...             # GIE AGSI+ gas storage (https://agsi.gie.eu)
```

For Azure OpenAI, copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For AWS Bedrock, install the extra with `pip install ".[bedrock]"`, set `llm_provider: "bedrock"`, configure AWS credentials (environment variables, `~/.aws/credentials`, or an IAM role) and `AWS_DEFAULT_REGION`, and use a Bedrock model ID, e.g. `us.anthropic.claude-opus-4-8-v1:0`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

For any other OpenAI-compatible server (vLLM, LM Studio, llama.cpp, or a custom relay), use `llm_provider: "openai_compatible"` and set the endpoint via `backend_url` (or `TRADINGAGENTS_LLM_BACKEND_URL`), e.g. `http://localhost:8000/v1` for vLLM or `http://localhost:1234/v1` for LM Studio. The model is whatever your server serves. No key is needed for local servers; set `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires one.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select the gas contract (TTF=F or NG=F), analysis date, LLM provider, research depth, and more.

### Instruments

This gas desk build trades two natural-gas futures via Yahoo Finance. Instrument identity and the alpha benchmark resolve per-contract from an instrument-profile table.

- **Dutch TTF** — `TTF=F` (front-month future, EUR/MWh). Full EU fundamentals stack (storage, weather, pipeline flows, EUA carbon).
- **Henry Hub** — `NG=F` (front-month future, USD/MMBtu). Price/technical/news/sentiment only — no US supply/demand fundamentals vendors yet.

Each contract is the other's alpha benchmark, so the reflection layer reads as the TTF–Henry Hub (global LNG arbitrage) spread in either direction. The CLI offers both contracts directly; you can also type `TTF` or `NATGAS`, which normalize to `TTF=F` / `NG=F`.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## GasTradingAgents Package

### Implementation Details

We built GasTradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use GasTradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("TTF=F", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-5.5"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("TTF=F", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

### News sources

News defaults to a curated set of gas/energy RSS feeds via the `rss_feeds` vendor, chained ahead of Yahoo Finance (`yfinance`). Energy newswires carry desk-relevant signal — LNG cargoes, Norway/supply outages, EU storage, Henry Hub, geopolitics — at higher density than a generic finance feed. The default chain is:

```python
config["data_vendors"]["news_data"] = "rss_feeds,yfinance"   # default: RSS first, Yahoo fallback
```

The shipped feed list (`rss_news_feeds`) covers Natural Gas Intelligence, Gas Outlook, Offshore Energy, Oilprice, and Rigzone. Curate it for your desk — add operator/TSO/terminal feeds or paid wires, or drop ones you don't want:

```python
config["rss_news_feeds"] = [
    {"name": "Gas Outlook",      "url": "https://gasoutlook.com/feed/",   "topics": ["europe", "lng"]},
    {"name": "My Operator Feed", "url": "https://example.com/news/rss",   "topics": ["outages"]},
]
```

To go back to Yahoo only, set `config["data_vendors"]["news_data"] = "yfinance"`. Notes:

- **Chain order is strict** — a vendor that returns anything ends the chain; there is no silent merge. RSS returns nothing only by *raising*, so `rss_feeds,yfinance` correctly falls through to Yahoo when no feed has an in-window article.
- **Live-oriented.** RSS exposes only the latest items with no point-in-time query, so for a pinned historical/backtest date the chain falls through to Yahoo (which can query a past window). Look-ahead filtering (future-dated / undated-in-backtest articles excluded) is shared with the Yahoo path.
- **Resilient.** A feed that errors is logged and skipped, never aborting the batch. Each news call fetches the feeds, so latency scales with the feed count.

## Persistence and Recovery

GasTradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, GasTradingAgents fetches the realised return (raw and alpha vs the contract's spread leg — Henry Hub `NG=F` when trading TTF, Dutch TTF `TTF=F` when trading Henry Hub), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("TTF=F", "2026-01-15")
```

## Reproducibility

GasTradingAgents is LLM-driven, so two runs of the same ticker and date can differ. This is expected for a research tool built on language models, not a defect. The variation comes from a few distinct sources, and it helps to separate them.

Language model sampling is non-deterministic. Even at a fixed temperature, providers do not guarantee byte-identical output across calls, and reasoning models (the default GPT-5.x family, and any thinking-mode model) vary the most because their internal reasoning is itself sampled.

Live data moves. Energy news returns different content as time passes, so a run today sees different inputs than a run last week even for the same historical trade date. Pin the analysis date to hold the price and indicator window fixed, but the news sources still reflect "now".

To reduce variation you can lower the sampling temperature. Set `temperature` in your config (or `TRADINGAGENTS_TEMPERATURE` in `.env`); lower values make models that honor it more repeatable. The current curated models are reasoning-first and largely ignore temperature, so for tighter reproducibility use a non-reasoning model, which you can set explicitly via the Custom model ID option.

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["temperature"] = 0.0
# Reasoning models ignore temperature. For tighter reproducibility, set a
# non-reasoning deep/quick model explicitly (e.g. via the Custom model ID option).
```

What does not vary anymore: the analyzed instrument identity is resolved deterministically from the ticker before any agent runs, and the market analyst grounds exact price and indicator claims in a verified data snapshot. Earlier reports of "different companies" or fabricated price levels across runs are addressed by these two mechanisms.

Backtest results are not guaranteed to match any published figure. Returns depend on the model, the temperature, the date range, data quality, and the sampling above. Treat the framework as a research scaffold for studying multi-agent analysis, not as a strategy with a fixed, replicable return.

## Contributing

Contributions are welcome: bug fixes, documentation, and feature ideas.

## Acknowledgements

GasTradingAgents is based on [TradingAgents](https://github.com/TauricResearch/TradingAgents) by [Tauric Research](https://github.com/TauricResearch). The multi-agent topology — analyst team, bullish/bearish researcher debates, trader, risk management, and portfolio manager — and the LangGraph orchestration are inherited from that work and adapted to a natural-gas trading desk (TTF / Henry Hub, gas supply/demand fundamentals, and energy-news positioning).

If GasTradingAgents is useful to you, please cite the original TradingAgents paper:

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
