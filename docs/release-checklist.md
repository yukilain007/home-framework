# Alpha release checklist

This checklist records the release candidate and published verification for package version
`0.1.0a5`. The project remains an alpha pre-release; future package uploads and hosted releases
require separate approval.

## v0.1.0-alpha.5

- [x] Metadata review completed
- [x] Packaging review completed
- [x] Security review completed
- [x] Release notes prepared
- [x] Signed tag approved and verified
- [x] GitHub Release published as a pre-release
- [x] PyPI publication completed through Trusted Publishing

## Release candidate verification

### Source verification

- [x] Python 3.11 validation (`3.11.15`, official `python:3.11-slim` container)
- [x] Python 3.12 validation (`3.12.13`, local isolated environment)
- [x] JSON Schema drift check
- [x] Ruff format and lint
- [x] mypy strict source check
- [x] pytest suite
- [x] redacted secret scan
- [x] deterministic repeated-build fingerprint
- [x] clean Git working tree after committed audit fixes

### Build artifact verification

- [x] sdist build
- [x] wheel build
- [x] `twine check` for both distributions
- [x] clean installation from the built wheel
- [x] installed console-script and subcommand help
- [x] fresh fictional workspace smoke test
- [x] generated export exclusion and archive-content checks

### Metadata verification

- [x] Distribution metadata reviewed for private names, paths, email addresses, and public URLs
- [x] Wheel and sdist content boundaries reviewed
- [x] README and changelog state the alpha.5 release is published
- [x] Confirm the PyPI Trusted Publisher configuration
- [x] Confirm Apache-2.0 is the intended license for public release
- [x] Confirm public author metadata
- [x] Confirm the signed annotated tag `v0.1.0-alpha.5`

## Published release verification

### PyPI install verification

- [x] Install the newly published package in a clean environment and run its release-specific
      smoke test. Record command exit status, validation count, selection result, and deterministic
      fingerprint in the freeze record.
- [x] Verify `docs/demo.md` only against its explicitly named artifact (`0.1.0a4`). Do not use its
      historical fingerprint as a cross-version baseline.
- [x] Confirm the CLI behaviour in `docs/guides/zero-tech-user-guide.zh-CN.md` against the guide's
      explicitly named applicable version; update it only after a separately verified run.
- [x] Confirm the scope statement in `docs/guides/daily-context-management.zh-CN.md` remains
      accurate for any version it explicitly names.

### Public artifact verification

- [x] Review the published PyPI project page, wheel, and sdist for accurate public metadata and
      intended content boundaries.

### Freeze record

- [x] Create the release freeze record after the published artifact verification is complete.

## Requires public remote

- [x] Choose the GitHub owner and repository name
- [x] Add and review the public repository URL in project metadata
- [x] Run the GitHub-hosted Python 3.11 workflow successfully for the existing public baseline
- [x] Approve the Alpha.5 preparation implementation push
- [x] Confirm the annotated tag points to the approved Alpha.5 commit
- [x] Approve the PyPI upload and GitHub Release as separate actions

## Apache-2.0 provenance for future releases

- [ ] Confirm `LICENSE`, `NOTICE`, `README.md`, and `pyproject.toml` consistently identify
      Apache-2.0 and the official project source.
- [ ] Confirm all tracked package source files retain complete SPDX copyright and license headers.
- [ ] Confirm the built wheel and sdist contain the declared license files and Apache-2.0 metadata.
- [ ] Verify a signed annotated tag before creating a GitHub Release or publishing an artifact.
- [ ] Confirm the GitHub Release is immutable after publication.
- [ ] Publish and record artifact attestations plus a verified SHA256 manifest.
- [ ] After a stable release, record the Software Heritage archive URL or SWHID in its freeze
      record.
