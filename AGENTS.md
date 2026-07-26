# HOME Framework maintenance rules

This file governs repository maintenance by AI agents and other automation. It does not change
the Apache-2.0 license or add restrictions to use, modification, distribution, or forks.

## Provenance integrity

- Do not remove, replace, or silently alter `LICENSE`, `NOTICE`, copyright notices, or SPDX
  headers without explicit maintainer approval.
- Keep the public package licensed under Apache-2.0 unless the maintainer explicitly approves a
  future relicensing decision.
- Do not rewrite historical tags, freeze records, GitHub Releases, or published package artifacts.

## Release operations

- Treat signed annotated tags, release provenance, and artifact checksums as release integrity
  records. Do not create, move, or delete them without explicit maintainer approval.
- Do not publish packages, upload artifacts, create releases, or change repository release
  settings unless the maintainer explicitly requests that external action.
