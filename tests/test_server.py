import asyncio

from zillow_proof_avm_mcp import __version__
from zillow_proof_avm_mcp.server import health_check, mcp


def test_server_name():
    assert mcp.name == "zillow-proof-avm"


def test_health_check():
    out = health_check()
    assert out["version"] == __version__
    assert out["status"] == "ok"


def test_health_check_registered():
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    assert "health_check" in names
