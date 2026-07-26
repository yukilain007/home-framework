# Contributing

Contributions must preserve the project's local-first, human-reviewed, fail-closed boundaries.

## Development setup

HOME requires Python 3.11 or newer.

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

## Pull request flow

1. Create a focused branch for one documented change.
2. Keep the change scoped, with tests or documentation that explain its purpose.
3. Run the relevant tests and the complete quality gate:

   ```bash
   python -m pytest
   python scripts/check.py
   ```

4. Open a pull request that describes the change, its motivation, and the validation performed.

## License and provenance

Do not remove or alter `LICENSE`, `NOTICE`, copyright notices, or SPDX identifiers from tracked
source files. This is a contribution and maintenance rule, not an additional license beyond
Apache-2.0. Any future relicensing requires explicit maintainer approval. Do not rewrite
historical tags, GitHub Releases, or published package artifacts.
