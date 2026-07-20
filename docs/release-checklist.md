# Alpha release checklist

This checklist covers the local release candidate for package version `0.1.0a2`. If approved,
the matching annotated Git tag is `v0.1.0-alpha.2`. The project is pre-release and not yet
published; completing local checks does not authorize a tag, push, package upload, or hosted
release.

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

- [x] Distribution metadata reviewed for private names, paths, email addresses, and invented URLs
- [x] Wheel and sdist contents reviewed
- [x] README and changelog state the candidate is not published
- [ ] Confirm `home-framework` as the final public package name; registry availability is unverified
- [ ] Confirm Apache-2.0 is the intended license for public release
- [ ] Confirm the public owner or organization name, if package metadata should name one
- [ ] Approve release notes
- [ ] Approve creation of annotated tag `v0.1.0-alpha.2`

## Requires public remote

- [ ] Choose the GitHub owner and repository name
- [ ] Add and review the public repository URL in project metadata
- [ ] Run the GitHub-hosted Python 3.11 workflow successfully
- [ ] Approve the first push
- [ ] Confirm the pushed branch and annotated tag point to the approved commit
- [ ] Approve any PyPI upload or GitHub Release as a separate action
