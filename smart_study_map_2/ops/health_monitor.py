from __future__ import annotations
import csv
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA_DIR / "backend_health.csv"

@dataclass
class ProbeResult:
    timestamp: datetime
    status: str            # "up" or "down"
    latency_ms: Optional[float]
    http_status: Optional[int]
    error: Optional[str]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def probe_health(api_base: str, timeout: float = 3.0) -> ProbeResult:
    url = f"{api_base.rstrip('/')}/health"
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        status = "up" if r.ok else "down"
        return ProbeResult(
            timestamp=_now_utc(),
            status=status,
            latency_ms=round(latency_ms, 2),
            http_status=r.status_code,
            error=None if r.ok else f"HTTP {r.status_code}"
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return ProbeResult(
            timestamp=_now_utc(),
            status="down",
            latency_ms=round(latency_ms, 2),
            http_status=None,
            error=str(e)
        )


def append_probe(result: ProbeResult) -> None:
    is_new = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp_iso", "status", "latency_ms", "http_status", "error"])
        w.writerow([
            result.timestamp.isoformat(),
            result.status,
            f"{result.latency_ms if result.latency_ms is not None else ''}",
            f"{result.http_status if result.http_status is not None else ''}",
            result.error or "",
        ])


def read_window(minutes: int = 60):
    """Return rows within the last N minutes as a list of dicts."""
    if not CSV_PATH.exists():
        return []
    cutoff = _now_utc() - timedelta(minutes=minutes)
    rows = []
    with CSV_PATH.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                ts = datetime.fromisoformat(row["timestamp_iso"])
            except Exception:
                continue
            if ts >= cutoff:
                rows.append({
                    "timestamp": ts,
                    "status": row.get("status", "down"),
                    "latency_ms": float(row["latency_ms"]) if row.get("latency_ms") else None,
                    "http_status": int(row["http_status"]) if row.get("http_status") else None,
                    "error": row.get("error") or None
                })
    return rows


def compute_metrics(rows) -> Tuple[float, Optional[float], int, Optional[datetime]]:
    """
    Returns tuple:
      (uptime_pct, avg_latency_ms_on_success, errors_count, last_down_at)
    For uptime, considers rows with status == 'up' as up.
    """
    if not rows:
        return 0.0, None, 0, None
    ups = sum(1 for r in rows if r["status"] == "up")
    total = len(rows)
    uptime_pct = round((ups / total) * 100.0, 2)
    latencies = [r["latency_ms"] for r in rows if r["status"] == "up" and r["latency_ms"] is not None]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
    errors_count = sum(1 for r in rows if r["status"] == "down")
    # Find last down timestamp (most recent where status == down)
    last_down_at = None
    for r in reversed(rows):
        if r["status"] == "down":
            last_down_at = r["timestamp"]
            break
    return uptime_pct, avg_latency, errors_count, last_down_at
