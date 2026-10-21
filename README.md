# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

## Status

Stage 5 — CLI/interface. `valuate` runs the whole pipeline from the shell: subject flags
plus a comps JSON file (or `ZPAVM_COMPS_FILE`), human summary by default, `--json` for the
full `Valuation`. `geo.py`, `sources.py`, and `valuation.py` are unchanged from stage 4.
MCP tools land in later stages.

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
pytest -q && ruff check .
```
