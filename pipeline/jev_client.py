"""Minimal Jev (TypeSafe) client.

Endpoint: POST https://api.typesafe.ai/v1/systemone  (docs: https://docs.typesafe.ai/api)
Auth:     Authorization: Bearer <TYPESAFE_API_KEY>
Body:     {"model": ..., "state": ..., "questions": {...}}
Reply:    {"model": ..., "answers": {...}, "usage": {"input_tokens": n, "output_tokens": n}}

Standard library only and thread-safe (no shared mutable state). Retries rate limits (429),
overload (529) and server errors with exponential backoff plus jitter, honouring Retry-After.
Every HTTP attempt is reported back to the caller so it can be written to the call log.
"""

import json
import random
import time
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"          # pinned version; the alias jev-latest pointed here on 2026-10-19
RETRYABLE = {429, 500, 502, 503, 504, 529}


class JevError(Exception):
    def __init__(self, message, status=None, retryable=False, attempts=None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.attempts = attempts or []


class JevClient:
    def __init__(self, api_key, model=MODEL, timeout=60, max_retries=4, sleep=time.sleep):
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY is empty")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep

    def ask(self, state, questions):
        """Send one state and its questions. Returns (payload, attempts).

        attempts: one dict per HTTP attempt with request_id, outcome, status, seconds.
        Raises JevError (with .attempts) when every attempt fails.
        """
        body = json.dumps({"model": self.model, "state": state, "questions": questions},
                          ensure_ascii=False).encode("utf-8")
        attempts = []
        for attempt in range(1, self.max_retries + 2):
            local_id = "local-" + uuid.uuid4().hex
            started = time.time()
            wait = None
            try:
                req = urllib.request.Request(
                    ENDPOINT, data=body, method="POST",
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    rid = resp.headers.get("x-request-id") or resp.headers.get("request-id") or local_id
                    payload = json.loads(resp.read().decode("utf-8"))
                attempts.append({"request_id": rid, "attempt": attempt, "outcome": "succeeded",
                                 "status": 200, "seconds": round(time.time() - started, 3)})
                return payload, attempts
            except urllib.error.HTTPError as e:
                status = e.code
                rid = (e.headers.get("x-request-id") if e.headers else None) or local_id
                attempts.append({"request_id": rid, "attempt": attempt, "outcome": "failed",
                                 "status": status, "seconds": round(time.time() - started, 3)})
                if status in RETRYABLE and attempt <= self.max_retries:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    try:
                        wait = float(retry_after) if retry_after else None
                    except ValueError:
                        wait = None
                else:
                    raise JevError(f"Jev HTTP {status}", status=status,
                                   retryable=status in RETRYABLE, attempts=attempts)
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
                attempts.append({"request_id": local_id, "attempt": attempt, "outcome": "failed",
                                 "status": None, "seconds": round(time.time() - started, 3),
                                 "error": type(e).__name__})
                if attempt > self.max_retries:
                    raise JevError(f"Jev network error: {type(e).__name__}", retryable=True,
                                   attempts=attempts)
            self.sleep(wait if wait is not None else min(30, 2 ** attempt) + random.uniform(0, 1))
        raise JevError("Jev retries exhausted", retryable=True, attempts=attempts)

    # Backwards-compatible name used by older code and tests.
    choose = ask
