# final-Spotify-project

## Setup

Every model role in this project uses Jev (TypeSafe), model `jev-1.13.0`. You need one key: `TYPESAFE_API_KEY`. The other variables in `.env.example` are unused.

1. Install dependencies (Python 3.9+; tested on 3.9 and 3.13):
   ```
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create your keys in each provider's developer console (Anthropic Console; Jev/TypeSafe). Confirm API billing and credits are in place before running the 100-review pilot.
3. Copy the template and fill in your keys locally:
   ```
   cp .env.example .env
   ```
   Edit `.env` and set `ANTHROPIC_API_KEY` and `TYPESAFE_API_KEY`. Leave unused variables blank.
4. The program loads keys through `config.py` (python-dotenv). Do not hard-code keys or put them in notebooks, prompts, logs, screenshots, or browser code.

Offline calculator replay and saved-output checks run without any keys.

## Secret hygiene

`.env` and `.env.*` are git-ignored; only the blank `.env.example` is committed. Before every push:

```
git check-ignore .env                 # should print: .env
git ls-files -- .env '.env.*'         # should list only .env.example
git diff --cached                     # inspect staged changes for secrets
```

If `.env` was ever tracked, run `git rm --cached .env` (ignore rules do not untrack it). If a real key is committed or shared, revoke and rotate it immediately; deleting the file does not remove it from Git history.

## Running the pipeline

Put the course dataset files in `data/` (git-ignored): `spotify_reviews_18months.csv`, `cost_100.csv`, `checkpoint_500.csv`, `analysis_10000.csv`.

```
python3 -m pytest -q                                   # offline tests, no key, no cost
python3 -m cost.pilot report                           # offline cost report from saved pilot files
python3 -m cost.pilot run --csv data/cost_100.csv      # PAID: real 100-review cold + warm pilot
python3 run.py all --csv data/checkpoint_500.csv --work runs/r500 --sample 50        # PAID
python3 run.py all --csv data/spotify_reviews_18months.csv --work runs/full --workers 8   # PAID: full run
python3 run.py rank --work runs/full                    # offline: regenerate ranking from saved outputs
python3 run.py status --work runs/full                  # offline: progress and total spend
```

Add `--dry-run` to any paid command to exercise it with the offline simulator (no calls, results marked SIMULATED).
All paid commands share one spend ledger (`runs/spend_ledger.json`) and stop before passing `--cap` (default $10 in total).
