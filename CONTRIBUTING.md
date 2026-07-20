# Contributing

Contributions must preserve the project's local-first, human-reviewed, fail-closed boundaries.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Required checks

```bash
python scripts/check.py
pre-commit run --all-files
```

Do not submit real conversations, personal profiles, private paths, credentials, or examples
derived from a real person. New behaviors require tests that fail before the implementation is
changed. Generated example exports are disposable and must not be committed.

The full pytest suite runs in the default local pre-commit stage. The same commands run in the
read-only GitHub Actions quality job on Python 3.11. Secret-scan exceptions must identify one
specific path and one specific rule in `.home-secret-scan-allowlist`; broad directory exclusions
are not accepted.
