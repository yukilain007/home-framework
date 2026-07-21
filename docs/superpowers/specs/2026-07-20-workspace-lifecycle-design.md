# Workspace lifecycle and diagnostics design

## Status

Approved for the workspace lifecycle implementation on 2026-07-20.

## Goal

Extend the deterministic authority pipeline with safe workspace creation, a versioned workspace
manifest, machine-readable export metadata, stale-export detection, local diagnostics, secret
scanning, and reproducible local and CI quality gates.

## Boundaries

- All operations are local to the workspace path explicitly supplied by the operator.
- No command creates a Git repository, remote, tag, release, network request, or authority data
  derived from a real person.
- Authority YAML is version-controlled source material. Markdown exports are disposable and
  ignored by default.
- Pydantic models remain the authority for all generated JSON Schemas.
- `secret` authority is never exportable. `private` authority requires explicit handoff consent.

## Architecture

### Workspace identity

`home.yaml` contains only a safe workspace name, schema version, minimum framework version, and
default export directory. `WorkspaceManifest` rejects unknown fields, unsafe names, absolute
paths, empty paths, and parent traversal. The repository loader validates the manifest before
loading authority documents and exposes it on `RepositorySnapshot`.

### Safe initialization

`home init PATH` prepares the complete write plan before touching the destination. It accepts a
missing path or an existing empty directory, creates a small fictional public authority set that
can validate and build immediately, and treats an already-valid workspace as an idempotent
success. Non-empty unknown directories and symbolic-link targets are refused. A failed write
rolls back only files and directories created by that invocation.

### Export protocol

`ExportMetadata` serializes as canonical JSON in the first Markdown line under the fixed prefix
`home-framework-export`. The marker contains schema version, handoff ID, context date, and
fingerprint; `generated_at` remains human-readable and is excluded from the fingerprint. Parsing
is deliberately limited to that first line and never attempts general Markdown or HTML parsing.

All default and custom output paths must resolve inside the workspace. Existing symbolic-link
components and a symbolic-link target are refused. Rendering completes before an atomic
same-directory replacement, so repository or write failures do not replace a valid export.

### Doctor and stale detection

`home doctor PATH --as-of YYYY-MM-DD` aggregates the existing `Diagnostic` type across four
areas: workspace structure, authority lifecycle, handoff exports, and security/Git hygiene. It
recompiles every handoff for the explicit date and classifies its default export as missing,
stale, invalid metadata, or current. A seven-day inclusive window defines expiring current
documents. Informational diagnostics do not affect exit status; errors always return 1 and
warnings return 1 only under `--strict`.

Secret scanning walks only regular files beneath the workspace without following symbolic links.
It reports the relative file and rule name, never the matched value. An exact path-and-rule
allowlist supports fictional test fixtures without excluding whole directories.

### Quality automation

`scripts/check.py` is the cross-platform local quality entry point. It regenerates schemas,
checks drift, runs Ruff, mypy, pytest, validates the fictional example, builds it twice into a
temporary in-repository directory, and compares fingerprints. Local pre-commit hooks invoke the
same focused commands. GitHub Actions runs the same checks on Python 3.11 with read-only contents
permission and adds the local secret scanner; it never publishes or uploads authority content.

## Error handling

- Repository, manifest, output-boundary, and detected-secret violations are errors.
- Missing/stale exports and actionable lifecycle states are warnings.
- Current exports, configured remotes, and clean lifecycle counts are informational.
- Diagnostics contain stable codes, workspace-relative paths, optional locations, and messages
  that do not reveal secret values.
- Commands never repair, delete, stage, or untrack user files automatically.

## Test strategy

Tests follow red-green-refactor and use temporary fictional workspaces. Coverage includes strict
manifest validation, initialization rollback and idempotence, metadata round trips, all export
states, lifecycle diagnostics, Git and non-Git workspaces, high-confidence secret patterns,
symbolic-link containment, output preservation, schema drift, CLI exit codes, and repeated-build
fingerprints. The original `0.1.0a1` tests remain in place and are extended rather than removed.
