# Architecture

## Pipeline

HOME Framework separates authority, validation, selection, and presentation:

```text
workspace manifest and YAML authority files
  → repository loader and bounded path checks
  → Pydantic models and cross-file diagnostics
  → compiler
  → immutable CompiledContext
  → Markdown renderer
  → atomic CLI write
```

## Module boundaries

### `models`

Defines strict data structures and object-local invariants. Pydantic models are the code authority
for the generated JSON Schemas.

### `initializer`

Plans and creates a complete fictional workspace without overwriting existing files or creating
Git state. It owns initialization rollback and idempotence checks.

### `repository`

Discovers recognized YAML files under a supplied root, parses them, validates directory/kind
agreement, and reports duplicate IDs and dangling handoff references. It collects independent
diagnostics rather than stopping at the first error.

### `compiler`

Selects only reviewed core and current documents that satisfy activity, date, scope or explicit
ID, and sensitivity constraints. Candidates never enter this layer. The compiler returns an
immutable result with a deterministic fingerprint.

### `renderer`

Transforms a compiled result into text. It does not discover files, validate data, or repeat
selection logic.

### `export_metadata`

Owns the canonical first-line metadata protocol and missing/stale/invalid/current export
classification. It opens exports without following the final symbolic link and reads at most 4
KiB from the first line; it does not parse or load general Markdown bodies.

### `security`

Walks only regular files of at most 1 MiB inside one explicit workspace, rejects symbolic-link
traversal and special files before reading, applies high-confidence secret rules and exact
allowlisting, and returns redacted diagnostics.

### `doctor`

Aggregates repository, lifecycle, export, security, and bounded Git diagnostics for a fixed date.
It checks only a Git repository rooted at the workspace and disables optional Git locks. It is
read-only and reuses the repository `Diagnostic` structure.

### `cli`

Coordinates validation, compilation, rendering, exit codes, diagnostics, and atomic output. It
does not define data contracts or selection semantics.

### `quality`

Provides small subprocess, schema-drift, and fingerprint primitives for local scripts and CI.

## Determinism

The fingerprint hashes canonical JSON containing the validated handoff, selected and sorted
documents, and `as_of` date. JSON keys are sorted and compactly encoded as UTF-8. The real
generation timestamp is excluded.

Sorting is stable:

1. core before current;
2. priority descending within a kind;
3. ID ascending as the final key.

## Workspace and output boundaries

`home.yaml` is validated before authority files. Its export directory is a strict relative path.
Default and custom output paths are normalized, checked for lexical and resolved containment, and
checked component-by-component for symbolic links before the atomic write. Export metadata is
derived from `CompiledContext`; the real generation timestamp remains outside the fingerprint.
