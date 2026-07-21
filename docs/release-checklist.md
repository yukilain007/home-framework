# Alpha release checklist

This checklist covers the local release candidate for package version `0.1.0a3`. If separately
approved, the matching annotated Git tag would be `v0.1.0-alpha.3`. The project is pre-release and
not yet published; completing local checks does not authorize a tag, package upload, or hosted
release.

## v0.1.0-alpha.3

- [x] Metadata review completed
- [x] Packaging review completed
- [x] Security review completed
- [x] Release notes prepared
- [ ] Tag approval pending
- [ ] PyPI publication approval pending

## Automated

- [x] Python 3.11 validation (`3.11.15`, official `python:3.11-slim` container)
- [x] Python 3.12 validation (`3.12.13`, local isolated environment)
- [x] JSON Schema drift check
- [x] Ruff format and lint
- [x] mypy strict source check
- [x] pytest suite
- [x] redacted secret scan
- [x] deterministic repeated-build fingerprint
- [x] sdist build
- [x] wheel build
- [x] `twine check` for both distributions
- [x] clean installation from the built wheel
- [x] installed console-script and subcommand help
- [x] fresh fictional workspace smoke test
- [x] generated export exclusion and archive-content checks
- [x] clean Git working tree after committed audit fixes

## Manual

- [x] Distribution metadata reviewed for private names, paths, email addresses, and public URLs
- [x] Wheel and sdist content boundaries reviewed
- [x] README and changelog state the candidate is not published
- [ ] Confirm ownership of the `home-framework` package name on PyPI
- [ ] Confirm Apache-2.0 is the intended license for public release
- [x] Confirm public author metadata
- [ ] Approve creation of annotated tag `v0.1.0-alpha.3`

## Requires public remote

- [x] Choose the GitHub owner and repository name
- [x] Add and review the public repository URL in project metadata
- [x] Run the GitHub-hosted Python 3.11 workflow successfully for the existing public baseline
- [x] Approve the Alpha.3 implementation push
- [ ] Confirm a future annotated tag points to the approved Alpha.3 commit
- [ ] Approve any PyPI upload or GitHub Release as a separate action
