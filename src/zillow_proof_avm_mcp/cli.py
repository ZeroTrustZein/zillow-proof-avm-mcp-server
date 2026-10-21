"""CLI entrypoint."""

import asyncio
from dataclasses import replace

import click

from . import __version__
from .config import Config
from .models import Address, PropertyFacts, PropertyType, SubjectProperty, Valuation
from .server import mcp
from .sources import source_from_config
from .valuation import value_property


@click.group()
def cli() -> None:
    """Zillow-Proof AVM MCP server."""


@cli.command()
def version() -> None:
    """Print version."""
    click.echo(__version__)


@cli.command()
def tools() -> None:
    """List registered MCP tools."""
    for tool in asyncio.run(mcp.list_tools()):
        click.echo(tool.name)


@cli.command()
def serve() -> None:
    """Run the MCP server."""
    cfg = Config.from_env()
    if cfg.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=cfg.transport, host=cfg.host, port=cfg.port)


@cli.command()
@click.option("--street", required=True)
@click.option("--city", required=True)
@click.option("--state", required=True)
@click.option("--zip", "zip_code", required=True)
@click.option("--beds", type=float, required=True)
@click.option("--baths", type=float, required=True)
@click.option("--sqft", type=int, required=True)
@click.option("--lot-sqft", type=int, default=None)
@click.option("--year-built", type=int, default=None)
@click.option(
    "--property-type",
    type=click.Choice([t.value for t in PropertyType]),
    default=PropertyType.SINGLE_FAMILY.value,
    show_default=True,
)
@click.option("--latitude", type=float, default=None)
@click.option("--longitude", type=float, default=None)
@click.option(
    "--comps",
    "comps_file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Comps JSON file (defaults to ZPAVM_COMPS_FILE).",
)
@click.option("--max-distance", type=float, default=2.0, show_default=True)
@click.option("--max-age-days", type=int, default=180, show_default=True)
@click.option("--min-comps", type=int, default=3, show_default=True)
@click.option("--limit", type=int, default=8, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Emit the full valuation as JSON.")
def valuate(
    street: str,
    city: str,
    state: str,
    zip_code: str,
    beds: float,
    baths: float,
    sqft: int,
    lot_sqft: int | None,
    year_built: int | None,
    property_type: str,
    latitude: float | None,
    longitude: float | None,
    comps_file: str | None,
    max_distance: float,
    max_age_days: int,
    min_comps: int,
    limit: int,
    as_json: bool,
) -> None:
    """Value a property from nearby sales."""
    subject = SubjectProperty(
        address=Address(street=street, city=city, state=state, zip=zip_code),
        facts=PropertyFacts(
            beds=beds,
            baths=baths,
            sqft=sqft,
            lot_sqft=lot_sqft,
            year_built=year_built,
            property_type=PropertyType(property_type),
            latitude=latitude,
            longitude=longitude,
        ),
    )
    cfg = Config.from_env()
    if comps_file:
        cfg = replace(cfg, comps_file=comps_file)

    try:
        source = source_from_config(cfg)
        valuation = value_property(
            subject,
            source.comps_for(subject),
            max_distance_miles=max_distance,
            max_age_days=max_age_days,
            min_comps=min_comps,
            limit=limit,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(valuation.model_dump_json(indent=2) if as_json else _summary(valuation))


def _summary(v: Valuation) -> str:
    band = v.band
    lines = [
        (
            f"{v.subject.address.street}, {v.subject.address.city} "
            f"{v.subject.address.state} {v.subject.address.zip}"
        ),
        f"  point  ${band.point:,.0f}   (${v.price_per_sqft:,.0f}/sqft)",
        f"  range  ${band.low:,.0f} - ${band.high:,.0f}   (+/- {band.spread_pct / 2:.1%})",
        f"  conf   {band.confidence:.1%}   comps {len(v.comps)}",
        "",
        "  comps",
    ]
    for c in v.comps:
        lines.append(
            f"    {c.address.street}  ${c.sale_price:,.0f} -> ${c.adjusted_price:,.0f} "
            f"({c.net_adjustment:+,.0f})  {c.distance_miles:.2f} mi  {c.sale_date}  {c.source}"
        )
    lines.append("")
    lines.append(f"  methodology  {v.methodology}")
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
