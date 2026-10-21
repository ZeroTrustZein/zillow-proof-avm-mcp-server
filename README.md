# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

## Status

Stage 7 — refactor. Selection defaults live in one place (`valuation.DEFAULT_*`, imported by the
CLI so flags cannot drift from the engine); beds/baths share one adjustment formula; timestamps are
UTC-aware. 60 tests across models, geo, sources, engine, CLI, config, and server; coverage 99% of
`src/`. CI runs `ruff check .` plus `pytest --cov`.

## Install

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

## Run

```bash
zillow-proof-avm tools     # list registered tools
zillow-proof-avm serve     # stdio MCP server
zillow-proof-avm valuate --street "1 Main St" --city Austin --state TX --zip 78704 \
  --beds 3 --baths 2 --sqft 2000 --comps comps.json        # add --json for raw output
```

## Configure

Copy `.env.example` to `.env`. Transport defaults to stdio; set `ZPAVM_TRANSPORT=sse` for HTTP.

## Test

```bash
pytest -q --cov=zillow_proof_avm_mcp --cov-report=term-missing && ruff check .
```
