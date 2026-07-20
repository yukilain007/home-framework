# Changelog

All notable changes to HOME Framework are documented here.

The project follows Semantic Versioning. Prerelease APIs may change before `1.0.0`.

## Unreleased

### 0.1.0a2 release candidate

- Added a strict workspace manifest and safe, idempotent `home init`.
- Added machine-readable export metadata and deterministic stale-export detection.
- Added `home doctor` lifecycle, export, security, and Git hygiene diagnostics.
- Added a bounded redacted secret scanner, local quality runner, pre-commit hooks, and CI.
- Added local release-candidate checks for Python 3.11, distribution archives, and clean wheel
  installation. No package, tag, remote, or hosted release has been published.

## 0.1.0a1 - 2026-07-20

- Added strict, versioned core, current, candidate, and handoff models.
- Added repository loading with aggregated YAML, schema, ID, and reference diagnostics.
- Added fail-closed deterministic compilation and SHA-256 fingerprints.
- Added disposable Markdown exports and `home validate` / `home build` commands.
- Added generated JSON Schemas and a fully fictional example repository.
