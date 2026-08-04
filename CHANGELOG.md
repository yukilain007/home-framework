# Changelog

All notable changes to HOME Framework are documented here.

The project follows Semantic Versioning. Prerelease APIs may change before `1.0.0`.

## Unreleased

### 0.2.0a1 development line

- Added user-controlled continuity contracts with explicit separation from memory, identity, and
  consciousness claims.
- Added immutable `HandoffPackage` creation, verification, atomic local export, and a
  provider-neutral local Markdown adaptation boundary.
- Added package CLI workflows that require explicit approval and never deliver or upload content.
- `render_markdown()` now requires an explicit timezone-aware `generated_at` input. This removes
  the hidden system-clock dependency and makes identical explicit inputs deterministic; direct
  callers must update to pass the timestamp.

## [0.1.0a5] - 2026-07-28

### 0.1.0a5 release candidate

- Added a full Simplified Chinese README with absolute documentation links.
- Added the zero-technical-background user guide and the daily context management guide.
- Added the developer FAQ and the context handoff demo walkthrough.
- Hardened Apache-2.0 provenance with SPDX headers across tracked package sources and a
  distribution provenance check.
- Synchronized release-status and installation documentation without changing the existing
  published artifact.

## [0.1.0a4] - 2026-07-22

### 0.1.0a4 release candidate

- Bumped the package and example workspace compatibility version for the first PyPI candidate.
- Synchronized current release documentation and version consistency checks.
- Recorded the configured Trusted Publisher while retaining explicit approval before publication.
- Published the first `home-framework` distributions through GitHub Actions OIDC and PyPI Trusted
  Publishing.

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
