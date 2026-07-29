# Alpha release checklist

This checklist covers the local release candidate for package version `0.1.0a5`. If separately
approved, the matching annotated Git tag would be `v0.1.0-alpha.5`. The project is pre-release and
not yet published; completing local checks does not authorize a tag, package upload, or hosted
release.

## v0.1.0-alpha.5

- [ ] Metadata review completed
- [ ] Packaging review completed
- [ ] Security review completed
- [ ] Release notes prepared
- [ ] Tag approval pending
- [ ] GitHub Release approval pending
- [ ] PyPI publication approval pending

## Release candidate verification

### Source verification

- [ ] Python 3.11 validation (`3.11.15`, official `python:3.11-slim` container)
- [ ] Python 3.12 validation (`3.12.13`, local isolated environment)
- [ ] JSON Schema drift check
- [ ] Ruff format and lint
- [ ] mypy strict source check
- [ ] pytest suite
- [ ] redacted secret scan
- [ ] deterministic repeated-build fingerprint
- [ ] clean Git working tree after committed audit fixes

### Build artifact verification

- [ ] sdist build
- [ ] wheel build
- [ ] `twine check` for both distributions
- [ ] clean installation from the built wheel
- [ ] installed console-script and subcommand help
- [ ] fresh fictional workspace smoke test
- [ ] generated export exclusion and archive-content checks

### Metadata verification

- [ ] Distribution metadata reviewed for private names, paths, email addresses, and public URLs
- [ ] Wheel and sdist content boundaries reviewed
- [ ] README and changelog state the candidate is not published
- [ ] Confirm the PyPI Trusted Publisher configuration
- [ ] Confirm Apache-2.0 is the intended license for public release
- [ ] Confirm public author metadata
- [ ] Approve creation of annotated tag `v0.1.0-alpha.5`

## Published release verification

### PyPI install verification

- [ ] Install the newly published package in a clean environment and run its release-specific
      smoke test. Record command exit status, validation count, selection result, and deterministic
      fingerprint in the freeze record.
- [ ] Verify `docs/demo.md` only against its explicitly named artifact (`0.1.0a4`). Do not use its
      historical fingerprint as a cross-version baseline.
- [ ] Confirm the CLI behaviour in `docs/guides/zero-tech-user-guide.zh-CN.md` against the guide's
      explicitly named applicable version; update it only after a separately verified run.
- [ ] Confirm the scope statement in `docs/guides/daily-context-management.zh-CN.md` remains
      accurate for any version it explicitly names.

### Public artifact verification

- [ ] Review the published PyPI project page, wheel, and sdist for accurate public metadata and
      intended content boundaries.

### Freeze record

- [ ] Create the release freeze record after the published artifact verification is complete.

## Requires public remote

- [x] Choose the GitHub owner and repository name
- [x] Add and review the public repository URL in project metadata
- [x] Run the GitHub-hosted Python 3.11 workflow successfully for the existing public baseline
- [ ] Approve the Alpha.5 preparation implementation push
- [ ] Confirm a future annotated tag points to the approved Alpha.5 commit
- [ ] Approve any PyPI upload or GitHub Release as a separate action

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
