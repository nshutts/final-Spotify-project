"""Shared helpers: JSON lines I/O, the spend ledger, run logging and rates."""

import json
import os
import threading
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATES_PATH = ROOT / "cost" / "rates.csv"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def read_jsonl(path):
    """Yield objects from a JSON-lines file, skipping a torn last line left by a hard stop."""
    p = Path(path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


class JsonlWriter:
    """Append-only writer. Each line is flushed; the file is fsynced every `sync_every` lines
    and on close, so a completed batch survives a crash."""

    def __init__(self, path, sync_every=50):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("a", encoding="utf-8")
        self.sync_every = sync_every
        self.pending = 0
        self.lock = threading.Lock()

    def write(self, obj):
        with self.lock:
            self.f.write(canonical(obj) + "\n")
            self.f.flush()
            self.pending += 1
            if self.pending >= self.sync_every:
                os.fsync(self.f.fileno())
                self.pending = 0

    def sync(self):
        with self.lock:
            self.f.flush()
            os.fsync(self.f.fileno())
            self.pending = 0

    def close(self):
        self.sync()
        self.f.close()


def write_json(path, value):
    """Atomic JSON write (temp file, then rename)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def load_input_rate(model, path=RATES_PATH):
    """USD per input token for `model` from cost/rates.csv (price per million / 1,000,000)."""
    import csv
    with Path(path).open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["model"] == model and row["item"] == "uncached_input":
                return float(Decimal(row["price_per_million_tokens"]) / Decimal(1_000_000))
    raise KeyError(f"no uncached_input rate for {model} in {path}")


class SpendLedger:
    """One ledger shared by every worker and stage in a run.

    Before a call is dispatched its worst-case cost is reserved. Work is admitted only while
    spent + reserved + next reservation <= cap. After the call, the reservation is replaced by the
    actual cost from reported usage. Spend is persisted in the run folder so a resumed run keeps
    counting from where it stopped.
    """

    def __init__(self, cap_usd, ledger_path=None):
        self.cap = float(cap_usd)
        self.spent = 0.0
        self.reserved = 0.0
        self.lock = threading.Lock()
        self.path = Path(ledger_path) if ledger_path else None
        if self.path and self.path.exists():
            self.spent = float(json.loads(self.path.read_text(encoding="utf-8")).get("spent_usd", 0.0))

    def try_reserve(self, amount):
        with self.lock:
            if self.spent + self.reserved + amount > self.cap:
                return False
            self.reserved += amount
            return True

    def settle(self, reserved_amount, actual):
        with self.lock:
            self.reserved -= reserved_amount
            self.spent += actual

    def save(self):
        if self.path:
            with self.lock:
                write_json(self.path, {"spent_usd": round(self.spent, 8), "cap_usd": self.cap,
                                       "updated": time.strftime("%Y-%m-%dT%H:%M:%S")})


def log_event(path, **fields):
    fields.setdefault("time", time.strftime("%Y-%m-%dT%H:%M:%S"))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(canonical(fields) + "\n")
