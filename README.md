# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

## Status

Stage 1 — scaffold. Server boots, `health_check` tool registered. Valuation tooling lands in
later stages.

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
