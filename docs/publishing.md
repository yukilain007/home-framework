# Publishing HOME Framework

> **Status: PyPI publication disabled.** This repository contains preparation for a future
> release flow. The required PyPI project and Trusted Publisher configuration do not yet exist;
> neither is created by this document or workflow.

## Trusted Publishing

HOME Framework is designed to publish through PyPI Trusted Publishing. The GitHub Actions job
uses OpenID Connect (OIDC) to request a short-lived publishing identity. It does not store or use
a long-lived PyPI credential in the repository or GitHub Actions configuration.

The workflow is [.github/workflows/publish.yml](../.github/workflows/publish.yml). Its first-stage
trigger is `workflow_dispatch`, so a maintainer must start it manually from an exact release tag.
A job guard skips publication when the selected Git ref is not a tag.

The `v0.1.0-alpha.3` tag predates this workflow preparation commit and must not be used to test or
run this publishing path. Only a future release tag whose commit contains this workflow is eligible.

The `pypi` GitHub Environment is the approval boundary. Before the first publication, maintainers
should configure required reviewers for that environment and separately configure the matching
project and Trusted Publisher on PyPI.

## Approval flow

1. Complete the release-candidate audit and create the approved Git tag.
2. Approve creation or use of the matching PyPI project as a separate action.
3. Configure the PyPI Trusted Publisher for this repository, workflow, and `pypi` environment.
4. Configure GitHub Environment reviewers and protection rules.
5. Manually run the publish workflow with the approved release tag selected as the Git ref.
6. Review the environment approval request, then verify the published files and metadata.

The workflow must not be run until steps 2–4 have been explicitly approved and completed.
Building or validating distributions locally does not authorize publication.

## Release stages

### Alpha

Alpha releases are early prereleases. They require an explicit alpha version, reviewed tag,
release notes, quality checks, and separate publication approval. Interfaces may change.

### Beta

Beta releases begin only after the alpha goals are met and the remaining compatibility risks are
documented. They use an explicit beta version and follow the same tag, review, and approval flow.

### Stable

Stable releases omit the prerelease suffix. They require explicit stability approval, completed
compatibility and migration review, final release notes, and the same protected publishing path.

No stage is published automatically when a GitHub Release is created. A future release-triggered
workflow requires a separate design review and approval.
