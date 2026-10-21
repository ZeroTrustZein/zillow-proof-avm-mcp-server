import json
from datetime import date, timedelta

from click.testing import CliRunner

from zillow_proof_avm_mcp.cli import cli


def _comps_file(tmp_path, count=3, encoding="utf-8"):
    today = date.today()
    records = [
        {
            "address": {"street": f"{i + 2} Oak Ave", "city": "Austin", "state": "TX", "zip": "78704"},
            "facts": {"beds": 3, "baths": 2, "sqft": 1950 + i * 50},
            "sale_price": 400_000.0 + i * 10_000,
            "sale_date": (today - timedelta(days=20 + i * 5)).isoformat(),
            "distance_miles": 0.3 + i * 0.1,
            "source": "fixture",
        }
        for i in range(count)
    ]
    path = tmp_path / "comps.json"
    path.write_text(json.dumps(records), encoding=encoding)
    return path


SUBJECT_ARGS = [
    "--street", "1 Main St", "--city", "Austin", "--state", "TX", "--zip", "78704",
    "--beds", "3", "--baths", "2", "--sqft", "2000",
]


def _run(*args):
    return CliRunner().invoke(cli, ["valuate", *SUBJECT_ARGS, *args])


def test_valuate_json(tmp_path):
    result = _run("--comps", str(_comps_file(tmp_path)), "--json")
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["band"]["point"] > 0
    assert len(out["comps"]) == 3
    assert out["methodology"]


def test_valuate_summary(tmp_path):
    result = _run("--comps", str(_comps_file(tmp_path)))
    assert result.exit_code == 0, result.output
    assert "point" in result.output
    assert "comps" in result.output


def test_valuate_comps_file_with_bom(tmp_path):
    result = _run("--comps", str(_comps_file(tmp_path, encoding="utf-8-sig")), "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["band"]["point"] > 0


def test_valuate_too_few_comps(tmp_path):
    result = _run("--comps", str(_comps_file(tmp_path, count=2)))
    assert result.exit_code == 1
    assert "at least 3" in result.output


def test_valuate_without_comp_source():
    result = CliRunner().invoke(
        cli, ["valuate", *SUBJECT_ARGS], env={"ZPAVM_COMPS_FILE": ""}
    )
    assert result.exit_code == 1
    assert "no comp source" in result.output
