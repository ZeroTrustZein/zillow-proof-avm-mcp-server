# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

## Status

Stage 4 — subsystems. `geo.py` derives great-circle comp distance from coordinates;
`sources.py` is the comp-access layer (`CompSource` protocol, in-memory and JSON-file
sources, distance back-filled from lat/lon when a record omits it). `valuation.py` is the
sales-comparison engine: comp filtering, line-item adjustment grid, proximity/recency
weighting, and a dispersion-driven confidence band. MCP tools land in later stages.

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
