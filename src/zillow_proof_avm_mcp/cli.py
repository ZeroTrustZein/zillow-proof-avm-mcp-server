"""CLI entrypoint."""

import asyncio

import click

from . import __version__
from .config import Config
from .server import mcp


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


if __name__ == "__main__":
    cli()
