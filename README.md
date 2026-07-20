# HOME Framework

HOME Framework is a local-first Python toolkit that validates reviewed authority files and
compiles deterministic, purpose-scoped context handoffs.

> **Alpha:** the current package version is `0.1.0a2`. File formats and command output may change
> before the first stable release.
>
> **Pre-release / not yet published to PyPI.** Latest source tag: `v0.1.0-alpha.2`.

HOME Framework is **not an automatic memory system**. It does not preserve or prove continuous AI
consciousness, infer consent, read chat history, or send workspace content to third-party
services.

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

## Installation

HOME Framework requires Python 3.11 or newer.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

The public package name remains provisional and has not been checked against a package registry.

## Quickstart

Create a new fictional workspace without initializing Git or creating a remote:

```bash
home init example-home --name example-home
```

The generated workspace contains two public fictional authority documents and one handoff, so it
can validate and build immediately. Repeating `home init` on a valid workspace is safe and does
not overwrite files. A non-empty unknown directory is refused.

Validate the bundled fictional repository:

```bash
home validate examples/fictional-assistant
```

Build a context for a fixed date:

```bash
home build examples/fictional-assistant \
  --handoff project.execution \
  --as-of 2026-07-20
```

The default output is
`examples/fictional-assistant/exports/project.execution.md`. Repeating a build with the same
authority files, handoff, and context date produces the same fingerprint. The real generation
timestamp is display metadata and is not part of the fingerprint.

Inspect lifecycle, export, security, and Git hygiene for the same date:

```bash
home doctor examples/fictional-assistant --as-of 2026-07-20
home doctor examples/fictional-assistant --as-of 2026-07-20 --strict
```

Without `--as-of`, build and doctor use the local date. Tests and reproducible automation should
always provide it. Doctor returns `1` when an error exists. Warnings return `0` normally and `1`
under `--strict`; informational diagnostics never change the exit status.

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
  minimum_version: 0.1.0a2
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
- GitHub-hosted CI has not been exercised until a public remote exists.

## Roadmap

Possible later increments include schema migration tooling, richer renderer plugins, explicit
export garbage collection, and compatibility testing on additional Python versions. They are
outside the `0.1.0a2` scope.

## License

Apache-2.0. See [LICENSE](LICENSE). The project owner should confirm the license before public
release.
