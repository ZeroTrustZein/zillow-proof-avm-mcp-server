import pytest

from zillow_proof_avm_mcp.config import Config

VARS = ("ZPAVM_TRANSPORT", "ZPAVM_HOST", "ZPAVM_PORT", "ZPAVM_COMPS_FILE")


def test_defaults_when_unset(monkeypatch):
    for var in VARS:
        monkeypatch.delenv(var, raising=False)
    cfg = Config.from_env()
    assert cfg.transport == "stdio"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8010
    assert cfg.comps_file is None


def test_reads_env(monkeypatch):
    monkeypatch.setenv("ZPAVM_TRANSPORT", "sse")
    monkeypatch.setenv("ZPAVM_HOST", "0.0.0.0")
    monkeypatch.setenv("ZPAVM_PORT", "9000")
    monkeypatch.setenv("ZPAVM_COMPS_FILE", "comps.json")
    cfg = Config.from_env()
    assert cfg.transport == "sse"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9000
    assert cfg.comps_file == "comps.json"


def test_empty_comps_file_is_none(monkeypatch):
    monkeypatch.setenv("ZPAVM_COMPS_FILE", "")
    assert Config.from_env().comps_file is None


def test_bad_port_raises(monkeypatch):
    monkeypatch.setenv("ZPAVM_PORT", "not-a-port")
    with pytest.raises(ValueError):
        Config.from_env()
