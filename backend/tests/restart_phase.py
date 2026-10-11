"""One phase of the restart-persistence test, run in its own Python process.

    python -m tests.restart_phase write <data_dir>   # create state, print it as JSON
    python -m tests.restart_phase read  <data_dir>   # read state back in a new process

Uses fixture market data, hash embeddings, and a persistent on-disk SQLite +
Chroma store in ``data_dir`` — the same storage paths a real server uses.
"""

import json
import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import Container
from app.main import create_app
from app.providers.cache import CachingMarketDataProvider
from app.providers.fixture import FixtureMarketDataProvider

TODAY = date(2026, 6, 30)
EMAIL, PASSWORD = "restart@example.test", "restart-password-1"


def app_for(data_dir: Path):
    settings = Settings(
        environment="test", market_data_provider="fixture", data_dir=data_dir, embedding_provider="hash",
        llm_provider="none", _env_file=None,
    )
    provider = CachingMarketDataProvider(FixtureMarketDataProvider(today=TODAY), today=lambda: TODAY)
    container = Container(settings, provider=provider, use_configured_llm=False)
    container.market._today = lambda: TODAY
    return create_app(settings, container)


def write(data_dir: Path) -> dict:
    with TestClient(app_for(data_dir)) as client:
        signup = client.post("/api/auth/signup", json={"email": EMAIL, "password": PASSWORD}, params={"return_token": "true"})
        token = signup.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/api/watchlist", json={"symbol": "NVDA"}, headers=headers)
        portfolio = client.post("/api/portfolios", headers=headers, json={
            "name": "Restart test", "benchmark": "SPY", "rebalancing": "buy_and_hold",
            "holdings": [{"symbol": "SPY", "weight": 60}, {"symbol": "TLT", "weight": 40}],
        }).json()
        document = client.post("/api/documents", headers=headers, data={"symbol": "NVDA", "title": "Restart doc"},
                               files={"file": ("doc.txt", b"Export controls on advanced chips affect data center revenue.", "text/plain")}).json()
        report = client.post("/api/research", headers=headers, json={"symbol": "NVDA", "question": "export controls?"}).json()
        return {"token": token, "portfolio_id": portfolio["id"], "portfolio_version": portfolio["version"],
                "document_id": document["id"], "document_status": document["status"], "report_id": report["id"]}


def read(data_dir: Path, token: str) -> dict:
    with TestClient(app_for(data_dir)) as client:
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/auth/me", headers=headers)
        login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        watchlist = client.get("/api/watchlist", headers=headers).json()
        portfolios = client.get("/api/portfolios", headers=headers).json()["items"]
        documents = client.get("/api/documents", headers=headers).json()["items"]
        search = client.post("/api/documents/search", headers=headers, json={"query": "export controls chips"}).json()
        reports = client.get("/api/research", headers=headers).json()["items"]
        return {
            "session_valid": me.status_code == 200,
            "login_status": login.status_code,
            "watchlist": [w["symbol"] for w in watchlist],
            "portfolios": [(p["id"], p["name"], p["version"]) for p in portfolios],
            "documents": [(d["id"], d["status"]) for d in documents],
            "search_hits": len(search["passages"]),
            "reports": [r["id"] for r in reports],
        }


if __name__ == "__main__":
    phase, directory = sys.argv[1], Path(sys.argv[2])
    if phase == "write":
        print(json.dumps(write(directory)))
    else:
        print(json.dumps(read(directory, sys.argv[3])))
