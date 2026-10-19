"""Offline stand-in for the Jev client, for tests and free dry runs. NEVER a source of results.

Answers are derived from simple keywords so the whole pipeline can be exercised without an API key.
Every reply reports model "SIMULATED-no-api-call"; export refuses simulated records unless explicitly
allowed for testing. It can also inject failures (HTTP errors, malformed output) to test recovery.
"""

import random
import uuid

from pipeline.jev_client import JevError

SIM_MODEL = "SIMULATED-no-api-call"
KEYWORDS = [("login", "access"), ("password", "access"), ("account", "access"), ("ad", "usability"),
            ("shuffle", "usability"), ("crash", "playback"), ("stop", "playback"), ("offline", "downloads"),
            ("download", "downloads"), ("lyrics", "catalog"), ("song", "catalog"), ("premium", "billing"),
            ("price", "billing"), ("support", "support")]


class FakeJevClient:
    def __init__(self, fail_every=0, malformed_every=0, seed=7):
        self.model = SIM_MODEL
        self.calls = 0
        self.fail_every = fail_every
        self.malformed_every = malformed_every
        self.rng = random.Random(seed)

    def ask(self, state, questions):
        self.calls += 1
        rid = "sim-" + uuid.uuid4().hex
        if self.fail_every and self.calls % self.fail_every == 0:
            raise JevError("simulated HTTP 503", status=503, retryable=True,
                           attempts=[{"request_id": rid, "attempt": 1, "outcome": "failed", "status": 503,
                                      "seconds": 0.0}])
        text = state if isinstance(state, str) else str(state)
        low = text.lower()
        answers = {}
        for name, q in questions.items():
            if q["type"] == "choice":
                opts = list(q["criteria"])
                pick = opts[0]
                if "playback" in opts:
                    pick = next((t for k, t in KEYWORDS if k in low), "other")
                elif "complaint" in opts:
                    neg = any(w in low for w in ("bad", "hate", "worst", "crash", "not", "can't", "stop", "ads"))
                    pick = "cancellation" if "uninstall" in low else ("complaint" if neg else "praise")
                elif "1" in opts:
                    pick = "3" if any(w in low for w in ("crash", "can't", "not")) else (
                        "2" if any(w in low for w in ("bad", "hate", "worst")) else "1")
                else:
                    pick = opts[self.rng.randrange(len(opts))]
                probs = {o: (0.7 if o == pick else 0.3 / max(len(opts) - 1, 1)) for o in opts}
                answers[name] = {"type": "choice", "choice": pick, "probabilities": probs, "confidence": 0.7}
            elif q["type"] == "score":
                s = 0.5 if any(w in low for w in ("bad", "hate", "worst")) else 3.2
                answers[name] = {"type": "score", "score": s}
            else:
                answers[name] = {"type": "noul", "noul": 0.1}
        if self.malformed_every and self.calls % self.malformed_every == 0:
            answers.pop(next(iter(answers)))
        payload = {"model": SIM_MODEL, "answers": answers,
                   "usage": {"input_tokens": len(str(questions)) // 4 + len(text) // 4, "output_tokens": 0}}
        return payload, [{"request_id": rid, "attempt": 1, "outcome": "succeeded", "status": 200, "seconds": 0.0}]

    choose = ask
