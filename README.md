# HOME Framework

**Your context belongs to you.**

## Switching AI shouldn't mean starting from zero.

### Before HOME

```text
ChatGPT  → new chat   → explain the context again
Claude   → new thread → repeat the context
Codex    → new task   → rebuild project state
```

### After HOME

```text
Your reviewed context
          ↓
       Compile
          ↓
   Context Handoff
          ↓
Compatible AI tools
```

Works with AI tools that can accept text or files.

HOME Framework is a local-first Python toolkit that validates reviewed authority files and
compiles deterministic, purpose-scoped context handoffs. It gives an AI the information needed for
one task, while keeping unreviewed, expired, or out-of-scope material out of that handoff.

### Clear boundaries

- HOME does not automatically read your chat history.
- Suggestions and candidates are not treated as approved facts.
- Context continuity does not imply continuous identity or consciousness.

> AI can suggest what matters. Only you decide what represents you.

English | [简体中文](README.zh-CN.md)

HOME Framework is **not an automatic memory system**. It does not infer consent or send workspace
content to third-party services.

> **Status — Pre-release / published to PyPI.** The current package version is `0.1.0a4`.
> File formats and command output may change before the first stable release.

[![PyPI](https://img.shields.io/pypi/v/home-framework)](https://pypi.org/project/home-framework/)
[![Python](https://img.shields.io/pypi/pyversions/home-framework)](https://pypi.org/project/home-framework/)
[![License](https://img.shields.io/github/license/yukilain007/home-framework)](LICENSE)
[![CI](https://github.com/yukilain007/home-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/yukilain007/home-framework/actions/workflows/ci.yml)

## Quickstart

HOME requires Python 3.11 or newer. Install the published alpha package, then create and run a
fully fictional example workspace:

```bash
python -m pip install home-framework==0.1.0a4

home init example-home --name example-home
home validate example-home
home build example-home \
  --handoff project.execution \
  --as-of 2026-07-20
home doctor example-home --as-of 2026-07-20
```

The generated handoff is written to `example-home/exports/project.execution.md`. Start with the
concepts below, or read the [Chinese zero-technical-background guide](docs/guides/zero-tech-user-guide.zh-CN.md)
for an AI-assisted local setup with explicit user approvals.

## What HOME produces

HOME compiles reviewed local authority files into a readable, purpose-scoped Context Handoff.

```text
Reviewed local context
        ↓
Deterministic compile
        ↓
Purpose-scoped Markdown
        ↓
User-approved handoff
```

The Markdown export is a derived artifact: it can be deleted and rebuilt from its authority files.
Its canonical metadata records the selected handoff, context date, and fingerprint.

## First-run details

`home init` creates two public fictional authority documents and one handoff, so the example can
validate and build immediately. Review and replace that example content before using the workspace
for real work. Re-running `home init` on a valid workspace is safe and does not overwrite files;
an unknown non-empty directory is refused.

For the same authority files, handoff, and context date, repeated builds produce the same
fingerprint. Without `--as-of`, `home build` and `home doctor` use the local date, so tests and
reproducible automation should always provide it.

`home doctor` exits with `1` when it finds an error. Warnings normally leave the exit status at
`0`; use `home doctor example-home --as-of 2026-07-20 --strict` when warnings should also return
`1`. Informational diagnostics never change the exit status.

## How approval works

HOME does not decide what becomes long-lived context. A human operator makes core and current
documents authoritative by placing them in their reviewed directories. Candidate documents remain
proposals—even when their review metadata records approval—and never become compiler inputs.
Promotion is an external human action, not an automated framework action.

Each handoff then explicitly selects document IDs, scopes, and permitted sensitivities for one
purpose. This makes the resulting Context Handoff inspectable and limits it to the context chosen
for that task.

## Core concepts

- **Authority files** are human-controlled YAML documents. They are the only inputs to builds.
- **Core documents** contain reviewed, stable guidance.
- **Current documents** contain reviewed context with an explicit validity window.
- **Candidates** are untrusted proposals. They are validated but never compiled.
- **Handoffs** explicitly select IDs, scopes, and allowed sensitivities for one purpose.
- **Exports** are disposable Markdown projections that can be rebuilt from authority files.
- **Workspace manifests** identify a compatible workspace and its default export directory.

The build pipeline is:

```text
workspace manifest and authority YAML files
→ Pydantic validation
→ repository loading and cross-file diagnostics
→ fail-closed handoff selection
→ deterministic compilation and SHA-256 fingerprint
→ machine-readable metadata and Markdown export
```

## Privacy boundary

- The CLI reads only the workspace path supplied by the operator.
- Missing selectors choose no context.
- Handoffs allow only `public` content unless `private` is explicitly listed.
- `secret` content cannot be exported, even if validation is bypassed.
- Candidates never enter a compiled context.
- The project contains only fictional example data.
- Generated exports are ignored by Git and should not be edited directly.
- Doctor and the secret scanner stay inside the supplied workspace and never print matched secret
  values.

See [the privacy model](docs/privacy-model.md) and [security policy](SECURITY.md).

## Workspace layout

```text
home.yaml           versioned workspace manifest
sources/core/       reviewed stable authority documents
sources/current/    reviewed time-bounded authority documents
candidates/         proposals that never compile
handoffs/           reviewed selection declarations
exports/            disposable generated Markdown
```

`home.yaml` is intentionally small:

```yaml
kind: workspace
schema_version: "1.0"
name: example-home
framework:
  minimum_version: 0.1.0a4
defaults:
  export_directory: exports
```

The export directory is a safe relative path. Absolute paths, `..`, symbolic-link escapes, and
custom `--output` paths outside the workspace are refused.

Documents use `schema_version: "1.0"` and a strict `kind` discriminator. Unknown fields are
errors. JSON Schema files under `schemas/` are generated from the Pydantic models. Pydantic runtime
validation is authoritative and also enforces cross-field invariants that standalone JSON Schema
cannot fully express:

```bash
python scripts/export_schemas.py
python scripts/check_schema_drift.py
```

## Export metadata and stale detection

Exports begin with a canonical machine-readable metadata comment containing the handoff ID,
context date, and fingerprint. Doctor uses only that fixed first-line protocol; it does not infer
state by parsing arbitrary Markdown. For each handoff it reports `missing_export`, `stale_export`,
`invalid_export_metadata`, or `current_export`. A different display-only generation timestamp is
not stale.

## Doctor checks

Doctor reports, but never repairs:

- manifest, required-directory, repository, reference, and symbolic-link problems;
- pending or approved candidates, future/expired/expiring current documents, and inactive or
  archived authority counts;
- missing, stale, invalid, unknown, or Git-tracked exports;
- high-confidence credential assignments, PEM private-key headers, and common token shapes;
- configured Git remote names and modified tracked authority files.

The expiry warning window is seven days, inclusive. Secret findings contain only a relative path,
rule name, and redacted message. Exact fictional fixtures may be allowlisted as
`relative/path:rule` in `.home-secret-scan-allowlist`; directory-wide exclusions are not used.
The bounded scanner rejects non-regular inputs and regular files larger than 1 MiB instead of
reading them. Doctor checks Git only when the supplied workspace is itself a normal Git root and
disables optional Git locks, repository filesystem monitors, and hooks for every command. Export
diagnosis reads only a no-follow, 4 KiB-bounded metadata first line, never the Markdown body.

Run the scanner independently with:

```bash
python scripts/scan_secrets.py .
```

This is a defense-in-depth aid, not a guarantee that a workspace contains no sensitive data.

## Version-control policy

- Commit `home.yaml`, authority files, handoffs, and deliberate candidate records.
- Ignore generated `exports/*.md` by default; they can be deleted and rebuilt.
- Doctor reports tracked generated Markdown but never runs `git rm` or changes the index.
- `home init` never runs `git init`, adds a remote, or generates personal profiles.

## Development

For local development from a checkout:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Then run the local quality checks:

```bash
python scripts/check.py
pre-commit run --all-files
```

The pre-commit configuration uses local system-language hooks for schema drift, Ruff, mypy,
pytest, and the redacted secret scanner. `scripts/check.py` also validates the fictional example,
builds it twice inside its workspace, and rejects fingerprint differences. GitHub Actions runs
the same gate on Python 3.11 with `contents: read` permission; it does not publish, upload
authority data, or modify schemas.

## Current limitations

- Local files only; there is no database or cloud sync.
- One build selects one handoff and one context date.
- No automatic candidate approval or authority-file mutation.
- Markdown is the only renderer.
- Schema version `1.0` is the only accepted protocol version.
- Version `0.1.0a4` is published on PyPI. Future PyPI publications still require explicit
  approval and a separate protected publishing action.

## Roadmap

Possible later increments include schema migration tooling, richer renderer plugins, explicit
export garbage collection, and compatibility testing on additional Python versions. They are
outside the `0.1.0a4` scope.

## License

Apache-2.0. See [LICENSE](LICENSE). The project owner should confirm the license before public
release.
