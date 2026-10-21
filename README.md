# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

## Status

Stage 3 — core logic. `models.py` holds the domain types; `valuation.py` is the sales-comparison
engine: comp filtering, line-item adjustment grid, proximity/recency weighting, and a
dispersion-driven confidence band. MCP tools land in later stages.

## Install

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

## Run

```bash
zillow-proof-avm tools     # list registered tools
zillow-proof-avm serve     # stdio MCP server
```

## Configure

Copy `.env.example` to `.env`. Transport defaults to stdio; set `ZPAVM_TRANSPORT=sse` for HTTP.

## Test

```bash
pytest -q && ruff check .
```
