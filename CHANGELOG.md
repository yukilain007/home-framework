# Changelog

All notable changes to HOME Framework are documented here.

The project follows Semantic Versioning. Prerelease APIs may change before `1.0.0`.

## Unreleased

## [0.1.0a3] - 2026-07-21

### 0.1.0a3 release candidate

- Hardened public package metadata with the reviewed maintainer identity.
- Added the public project homepage, repository, and issue tracker URLs.
- Added reviewed development-status, Python-version, audience, and topic classifiers.
- Excluded internal development records from source distributions.
- Added an inert manual workflow template in preparation for future Trusted Publishing.

## [0.1.0a2] - 2026-07-20

### 0.1.0a2 release candidate

This release candidate was frozen as `v0.1.0-alpha.2` on 2026-07-20.

### Added

- Versioned authority, workspace and handoff models.
- Deterministic context compilation and Markdown exports.
- Safe workspace initialization and health diagnostics.
- Stale-export detection and machine-readable export metadata.
- Path, symlink, secret and repository-boundary protections.
- Python 3.11 quality gates and GitHub Actions validation.

### Security

- Public repository history was rebuilt from a reviewed source snapshot.
- Private HOME content and internal development history were excluded.
- Secret content is always denied from exports.

## 0.1.0a1 - 2026-07-20

- Added strict, versioned core, current, candidate, and handoff models.
- Added repository loading with aggregated YAML, schema, ID, and reference diagnostics.
- Added fail-closed deterministic compilation and SHA-256 fingerprints.
- Added disposable Markdown exports and `home validate` / `home build` commands.
- Added generated JSON Schemas and a fully fictional example repository.
