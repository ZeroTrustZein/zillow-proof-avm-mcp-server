"""MCP server definition. Tools land here as stages land."""

from mcp.server.mcpserver import MCPServer

from . import __version__

mcp = MCPServer("zillow-proof-avm", version=__version__)


@mcp.tool()
def health_check() -> dict:
    """Report server name, version, and readiness."""
    return {"server": "zillow-proof-avm", "version": __version__, "status": "ok"}
