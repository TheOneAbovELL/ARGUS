"""Robust prefetch of the local ONNX embedding model (all-MiniLM-L6-v2).

Chroma downloads this ~80 MB archive lazily on first use with a short default
timeout and no resume, which fails on slow connections, so a document upload
would hang and then fail. ARGUS downloads it itself instead:

* resumable (HTTP Range) into a ``.part`` file, long read timeout, retries;
* SHA-256 verified against Chroma's published hash before use;
* extracted with ``tarfile``'s ``data`` filter (no path traversal) into the
  exact cache layout Chroma expects, so Chroma never downloads anything.

Run ahead of time with ``python -m app.knowledge.model_cache``; the API also
starts it in the background when the model is missing.
"""

import hashlib
import logging
import os
import ssl
import tarfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger("argus.embeddings")

MODEL_NAME = "all-MiniLM-L6-v2"
DOWNLOAD_PATH = Path.home() / ".cache" / "chroma" / "onnx_models" / MODEL_NAME
ARCHIVE = DOWNLOAD_PATH / "onnx.tar.gz"
URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
REQUIRED_FILES = (
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
)


def model_ready(root: Path = DOWNLOAD_PATH) -> bool:
    return all((root / "onnx" / name).is_file() for name in REQUIRED_FILES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class PrefetchState:
    status: str = "not_started"  # not_started | downloading | ready | failed
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    error: str | None = None


class ModelPrefetcher:
    """Downloads once; safe to call from several threads."""

    def __init__(
        self,
        root: Path = DOWNLOAD_PATH,
        url: str = URL,
        sha256: str = SHA256,
        attempts: int = 20,
        read_timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.root = root
        self.url = url
        self.sha256 = sha256
        self.attempts = attempts
        self.read_timeout = read_timeout
        self.transport = transport
        self.state = PrefetchState(status="ready" if model_ready(root) else "not_started")
        self._lock = threading.Lock()

    def start_background(self) -> None:
        if self.state.status in ("ready", "downloading"):
            return
        threading.Thread(target=self.ensure, name="argus-embedding-prefetch", daemon=True).start()

    def ensure(self) -> bool:
        with self._lock:
            if model_ready(self.root):
                self.state.status = "ready"
                return True
            self.state = PrefetchState(status="downloading")
            try:
                archive = self.root / "onnx.tar.gz"
                if not (archive.is_file() and _sha256(archive) == self.sha256):
                    self._download(archive)
                self._extract(archive)
                if not model_ready(self.root):
                    raise RuntimeError("the archive did not contain the expected model files")
                self.state.status = "ready"
                logger.info("embedding model ready", extra={"path": str(self.root)})
                return True
            except Exception as exc:  # reported via status; the app keeps running
                self.state.status = "failed"
                self.state.error = f"{type(exc).__name__}: {exc}"[:300]
                logger.warning("embedding model download failed", extra={"error": self.state.error})
                return False

    def _download(self, archive: Path) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        part = archive.with_suffix(".gz.part")
        timeout = httpx.Timeout(connect=20.0, read=self.read_timeout, write=20.0, pool=20.0)
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            offset = part.stat().st_size if part.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            try:
                # Certificates are always verified, against the operating system's
                # trust store (which includes roots installed by corporate proxies
                # or antivirus HTTPS scanning) rather than only certifi's bundle.
                with httpx.Client(
                    timeout=timeout,
                    transport=self.transport,
                    follow_redirects=True,
                    verify=ssl.create_default_context(),
                ) as client:
                    with client.stream("GET", self.url, headers=headers) as response:
                        if response.status_code == 416:  # already complete
                            break
                        if response.status_code not in (200, 206):
                            raise RuntimeError(f"HTTP {response.status_code}")
                        if response.status_code == 200 and offset:
                            offset = 0  # server ignored Range: restart
                        length = response.headers.get("content-length")
                        self.state.total_bytes = offset + int(length) if length else None
                        with part.open("ab" if offset else "wb") as handle:
                            for chunk in response.iter_bytes():  # write as received, so a stall loses nothing
                                handle.write(chunk)
                                self.state.downloaded_bytes = handle.tell()
                break
            except Exception as exc:
                last_error = exc
                logger.info("embedding download interrupted; resuming", extra={"attempt": attempt, "error": repr(exc)})
                time.sleep(min(2 ** attempt, 60))
        else:
            raise RuntimeError(f"download failed after {self.attempts} attempts: {last_error!r}")
        if _sha256(part) != self.sha256:
            part.unlink(missing_ok=True)
            raise RuntimeError("downloaded archive failed SHA-256 verification")
        os.replace(part, archive)

    def _extract(self, archive: Path) -> None:
        with tarfile.open(archive, mode="r:gz") as tar:
            # The "data" filter rejects absolute paths, traversal, and links (Python 3.12+).
            tar.extractall(path=self.root, filter="data")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    prefetcher = ModelPrefetcher()
    if prefetcher.state.status == "ready":
        print(f"Embedding model already present at {DOWNLOAD_PATH}")
        return 0
    print(f"Downloading {MODEL_NAME} (~80 MB) to {DOWNLOAD_PATH} ...")
    done = threading.Event()

    def report() -> None:
        while not done.wait(5):
            s = prefetcher.state
            total = f"/{s.total_bytes / 1e6:.1f}" if s.total_bytes else ""
            print(f"  {s.downloaded_bytes / 1e6:.1f}{total} MB")

    threading.Thread(target=report, daemon=True).start()
    ok = prefetcher.ensure()
    done.set()
    print("Ready." if ok else f"Failed: {prefetcher.state.error}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
