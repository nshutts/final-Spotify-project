"""Minimal Jev (TypeSafe) client for the Choice primitive.

Endpoint: POST https://api.typesafe.ai/v1/systemone
Auth:     Authorization: Bearer <TYPESAFE_API_KEY>

Standard library only. Retries rate limits and server errors with exponential
backoff plus jitter, and reports every attempt so the caller can log it.
"""

import json
import random
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
RETRYABLE = {429, 500, 502, 503, 504}


class JevError(Exception):
    def __init__(self, message, status=None, retryable=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class JevClient:
    def __init__(self, api_key, timeout=60, max_retries=3, sleep=time.sleep):
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY is empty")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep

    def choose(self, state, questions):
        """Send one review text and the Choice questions. Returns (parsed_json, attempts).

        `attempts` is a list of dicts, one per HTTP attempt, for the call log.
        """
        body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode("utf-8")
        attempts = []
        for attempt in range(1, self.max_retries + 2):
            started = time.time()
            try:
                req = urllib.request.Request(
                    ENDPOINT, data=body, method="POST",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                attempts.append({"attempt": attempt, "outcome": "succeeded", "status": 200,
                                 "seconds": round(time.time() - started, 3)})
                return payload, attempts
            except urllib.error.HTTPError as e:
                status = e.code
                attempts.append({"attempt": attempt, "outcome": "failed", "status": status,
                                 "seconds": round(time.time() - started, 3)})
                if status in RETRYABLE and attempt <= self.max_retries:
                    self.sleep(min(30, 2 ** attempt) + random.uniform(0, 1))
                    continue
                err = JevError(f"Jev HTTP {status}", status=status, retryable=status in RETRYABLE)
                err.attempts = attempts
                raise err
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                attempts.append({"attempt": attempt, "outcome": "failed", "status": None,
                                 "seconds": round(time.time() - started, 3), "error": type(e).__name__})
                if attempt <= self.max_retries:
                    self.sleep(min(30, 2 ** attempt) + random.uniform(0, 1))
                    continue
                err = JevError(f"Jev network error: {type(e).__name__}", retryable=True)
                err.attempts = attempts
                raise err
        err = JevError("Jev retries exhausted", retryable=True)
        err.attempts = attempts
        raise err
