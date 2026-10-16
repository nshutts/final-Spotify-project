# final-Spotify-project

## Setup

This project uses Claude (Anthropic) as the LLM provider and Jev (TypeSafe). You need two keys: `ANTHROPIC_API_KEY` and `TYPESAFE_API_KEY`. `OPENAI_API_KEY` is listed in `.env.example` but is not used.

1. Install dependencies (Python 3.10+):
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
