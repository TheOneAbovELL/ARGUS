"""State survives a real process restart (SQLite + on-disk Chroma + uploads)."""

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def run_phase(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "tests.restart_phase", *args],
        cwd=BACKEND, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_workspace_survives_a_process_restart(tmp_path: Path) -> None:
    written = run_phase("write", str(tmp_path))
    assert written["document_status"] == "ready"
    after = run_phase("read", str(tmp_path), written["token"])
    assert after["session_valid"] is True  # server-side session persisted
    assert after["login_status"] == 200
    assert after["watchlist"] == ["NVDA"]
    assert after["portfolios"] == [[written["portfolio_id"], "Restart test", written["portfolio_version"]]]
    assert after["documents"] == [[written["document_id"], "ready"]]
    assert after["search_hits"] >= 1  # the vector index was persisted, not just the metadata
    assert after["reports"] == [written["report_id"]]
