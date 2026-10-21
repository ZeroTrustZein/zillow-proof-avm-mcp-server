# zillow-proof-avm-mcp-server

MCP server exposing an automated valuation model (AVM) for US residential property that stands up
to Zestimate scrutiny: transparent comps, adjustment grids, and a confidence band you can defend.

Every number is traceable. Each comp carries the line items that moved it (field, amount, reason),
and the final band is a weighted blend of dispersion, comp count, and proximity — no black boxes.

## Status

Stages 1–8 complete: domain types, sales-comparison engine, geo, comp sources, CLI, tests, CI.

- **60 tests, 99% coverage** of `src/`, enforced at a 95% floor in CI (Python 3.10/3.11/3.12).
- **MCP surface today is `health_check` only.** Valuation is reachable through the CLI; exposing the
  engine as MCP tools is the next stage.
- **No live data providers yet.** Comps come from a JSON file (county/MLS export shape). The
  `.env.example` keys for RentCast/Census are reserved, not read.

## Install

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                      # macOS/Linux
pip install -e ".[dev]"
```

Two entry points are installed, both pointing at the same CLI: `zillow-proof-avm` and
`zillow-proof-avm-mcp`.

## Quickstart

```bash
zillow-proof-avm tools     # health_check
zillow-proof-avm serve     # stdio MCP server

zillow-proof-avm valuate \
  --street "1510 Kenwood Ave" --city Austin --state TX --zip 78704 \
  --beds 3 --baths 2 --sqft 1950 --lot-sqft 7400 --year-built 1955 \
  --latitude 30.2504 --longitude -97.7601 \
  --comps examples/austin-78704-comps.json
```

Real output — note `4000 Balcones Dr` (~4 mi out) never makes the grid, see selection rules:

```
1510 Kenwood Ave, Austin TX 78704
  point  $713,271   ($366/sqft)
  range  $691,872 - $734,670   (+/- 3.0%)
  conf   81.2%   comps 4
  ...
```

`--json` emits the full valuation document (`subject`, adjusted `comps` with every adjustment line,
`band`, `methodology`, `created_at`) instead of the human summary.

The example comps file is pinned to 2026 sale dates. If your clock is later than
`sale_date + --max-age-days`, every comp ages out and the command fails with a "usable comps" error —
pass a larger `--max-age-days` or use fresher data.

## CLI

| Command | What it does |
| --- | --- |
| `zillow-proof-avm version` | Print the version. |
| `zillow-proof-avm tools` | List registered MCP tools. |
| `zillow-proof-avm serve` | Run the MCP server (transport from config). |
| `zillow-proof-avm valuate` | Value one property from a comps source; prints summary or `--json`. |

`valuate` options:

| Flag | Required | Default | Notes |
| --- | --- | --- | --- |
| `--street --city --state --zip` | yes | — | ZIP must be 5 digits; state is uppercased. |
| `--beds --baths` | yes | — | Floats, `>= 0`. |
| `--sqft` | yes | — | Integer, `> 0`. |
| `--lot-sqft` | no | none | Omit and no lot adjustment is applied. |
| `--year-built` | no | none | 1700–2100. |
| `--property-type` | no | `single_family` | `single_family`, `condo`, `townhouse`, `multi_family`, `manufactured`. Comps of another type are discarded. |
| `--latitude --longitude` | no | none | Needed to derive distance for comps that omit it. |
| `--comps` | no | `ZPAVM_COMPS_FILE` | Path to a comps JSON file. |
| `--max-distance` | no | `2.0` | Miles. |
| `--max-age-days` | no | `180` | Days since sale. |
| `--min-comps` | no | `3` | Below this, the command errors instead of guessing. |
| `--limit` | no | `8` | Max comps kept after sorting. |
| `--json` | no | off | Raw valuation JSON. |

Exit code is `1` with a one-line message when the comp source has too few usable comps, when a comp
has neither `distance_miles` nor coordinates, or when no comp source is configured.

## MCP client setup

stdio (default):

```json
{
  "mcpServers": {
    "zillow-proof-avm": {
      "command": "zillow-proof-avm",
      "args": ["serve"],
      "env": { "ZPAVM_COMPS_FILE": "C:/path/to/comps.json" }
    }
  }
}
```

HTTP instead of stdio: set `ZPAVM_TRANSPORT=sse` (or `streamable-http`) with `ZPAVM_HOST` /
`ZPAVM_PORT` (`127.0.0.1:8010` by default) and run `zillow-proof-avm serve`.

## Configure

Copy `.env.example` to `.env` (or export the vars; the CLI reads the process environment):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ZPAVM_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http`. |
| `ZPAVM_HOST` | `127.0.0.1` | Bind host for HTTP transports. |
| `ZPAVM_PORT` | `8010` | Bind port for HTTP transports. |
| `ZPAVM_COMPS_FILE` | none | Comps JSON path used when `--comps` is not passed. |
| `ZPAVM_USER_AGENT`, `ZPAVM_RENTCAST_API_KEY`, `ZPAVM_CENSUS_API_KEY` | none | Reserved for live sources; not read today. |

## Comps JSON

Either a bare list or `{"comps": [...]}`. Each record is a `Comp`:

```json
{
  "address": { "street": "1104 Almar St", "city": "Austin", "state": "TX", "zip": "78704" },
  "facts": { "beds": 3, "baths": 2, "sqft": 1980, "lot_sqft": 7200, "year_built": 1958,
             "property_type": "single_family", "latitude": 30.251, "longitude": -97.761 },
  "sale_price": 712000,
  "sale_date": "2026-08-14",
  "source": "travis-county"
}
```

- `distance_miles` is optional. Omit it and it is computed from the subject's and comp's
  coordinates (haversine, statute miles) — the usual shape of county exports. A comp with neither
  coordinates nor `distance_miles` is rejected with a named error.
- Unknown fields are forbidden at every level, so typos fail loudly instead of silently defaulting.
- A UTF-8 BOM is tolerated in the file (Excel/CSV exports).

## Methodology

Sales comparison approach. Comps are filtered to the subject's property type, within
`--max-distance` miles and `--max-age-days` days, sorted by age then distance, and capped at
`--limit`. Each kept comp is adjusted to the subject line by line:

| Field | Adjustment | Why |
| --- | --- | --- |
| GLA (sqft) | `sqft_diff × (comp_sale_price / comp_sqft) × 0.5` | GLA is worth roughly half the market $/sqft; full $/sqft double-counts land and improvements. |
| Beds | `diff × price × 1.5%` | Marginal value of a bedroom is well under a full room's cost. |
| Baths | `diff × price × 1.0%` | Same formula as beds, lower rate. |
| Year built | `diff × price × 0.3%/yr`, capped at ±30 yr | Age effect saturates; a 60-year gap is not twice a 30-year gap. |
| Lot | `lot_diff/1000 × price × 1.0%` | Applied only when both sides have `lot_sqft`. |

Rates are fractions of the comp's sale price, so adjustments stay proportional across price tiers.
Zero-amount lines are dropped from the grid.

Reconciliation weights each adjusted price by `0.5 ** (age_days / 90) × 1 / (1 + distance_miles)`:
recency halves every 90 days and never reaches zero; proximity decays hyperbolically.

The band spans one weighted standard deviation around the weighted mean, floored at 3% and capped at
50% of the point estimate (`low` floored, `high` ceiled to whole dollars). Confidence blends spread,
count, and proximity:

```
confidence = 0.45 × spread + 0.35 × min(comps/6, 1) + 0.20 × clamp(1 - mean_distance/2, 0, 1)
spread     = clamp(1 - (dispersion / point) × 5, 0, 1)
```

clamped to `[0.05, 0.95]` — a confident answer is never reported as certain, and a thin comp set is
never reported as worthless. The exact prose shipped with each valuation lives in
`valuation.METHODOLOGY`.

## Architecture

```
src/zillow_proof_avm_mcp/
  models.py      pydantic domain types (Address, PropertyFacts, Comp, AdjustedComp, ConfidenceBand, Valuation)
  geo.py         haversine distance; returns None when coordinates are missing
  sources.py     CompSource protocol, JsonCompSource, StaticCompSource, comp_from_record
  valuation.py   adjustment grid, comp selection, weighting, reconciliation, value_property
  config.py      env-driven frozen Config
  server.py      MCPServer instance and registered tools
  cli.py         click CLI (version, tools, serve, valuate)
```

Dependencies flow one way: `cli → sources → valuation → models`, with `geo` used by `sources`.
`valuation` imports nothing from `sources`, so a live provider only has to satisfy
`comps_for(subject) -> list[Comp]`.

The CLI imports `DEFAULT_MAX_DISTANCE_MILES`, `DEFAULT_MAX_AGE_DAYS`, `DEFAULT_MIN_COMPS`, and
`DEFAULT_LIMIT` from `valuation`, so flag defaults cannot drift from the engine.

## Development

```bash
pytest -q --cov=zillow_proof_avm_mcp --cov-report=term-missing && ruff check .
```

CI (`.github/workflows/ci.yml`) runs ruff, the test suite with a 95% coverage floor, and a smoke test
of the installed `zillow-proof-avm tools` entry point on 3.10/3.11/3.12; runs on the same branch
cancel in progress.

## Limitations

- Single-family-centric heuristics. Condo/townhouse comps work but the GLA and lot rates are
  calibrated on detached housing.
- No time trend: adjustments are recency-*weighted* but not market-*trend adjusted*, so a comp from
  170 days ago in a fast market is discounted, not re-projected.
- No condition, renovation, view, or school-district adjustment. Anything the grid cannot see lands
  in the dispersion term, which widens the band.
- Estimator, not an appraisal. Not USPAP-compliant output and not a substitute for a licensed
  appraiser.

## Roadmap

1. Expose valuation as MCP tools (`valuate_property`, comp lookup) with structured output.
2. Live comp providers behind the `CompSource` protocol (county open data, RentCast).
3. Market-trend adjustment from repeat-sales or ZIP-level price indices.
4. Condition/renovation inputs feeding the adjustment grid.
