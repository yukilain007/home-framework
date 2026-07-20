# Privacy model

HOME Framework is local-first and human-controlled. It turns reviewed authority files into a
purpose-scoped export; it does not collect conversations or decide what should become memory.

## Human review

Core and current documents are authority only because a human operator places them in those
directories. Candidate documents remain proposals regardless of their review metadata and are
never compiler inputs. Promotion is an external human action, not an automated framework action.

## Default refusal

- A handoff with no ID or scope selectors chooses nothing.
- Only `public` sensitivity is allowed by default.
- `private` requires an explicit handoff allowlist entry.
- `secret` is always refused.
- Inactive, archived, future, and expired authority content is excluded.
- Any repository error prevents a build.

## Authority and exports

Authority YAML files are the source of truth. Markdown exports are generated projections and can
be deleted and rebuilt. Export files are ignored by Git in the fictional example.

## Data movement

The framework performs no network operations, does not call an LLM API, and does not search chat
history or neighboring directories. It reads the workspace path explicitly supplied to the CLI
and writes only a checked output path inside that workspace.

`home doctor` and the local secret scanner walk only the supplied workspace. They do not follow
symbolic links, inspect neighboring paths, upload findings, or print complete matched values.
Non-regular files and regular files over 1 MiB are not read. Git checks run only for a normal
`.git` directory rooted inside that workspace, disable optional locks, filesystem monitors, and
hooks, and never modify the worktree or index; parent repositories and linked-worktree metadata
are intentionally ignored. Stale-export checks open without following a final symbolic link and
read only a 4 KiB-bounded metadata first line.

## Workspace lifecycle

`home init` creates only public fictional examples and a minimal non-personal manifest. It does
not initialize Git, infer authority, create candidates, or generate profiles. A non-empty unknown
directory is refused, and a failed initialization rolls back only paths created by that attempt.

Machine-readable export metadata describes a derived artifact, not memory, identity, consent, or
continuous consciousness. Stale detection compares declared authority inputs and a fixed date; it
does not reconstruct missing context.

## Fictional data

All bundled examples were written as fictional, low-sensitivity test material. Contributors must
not adapt real private records into examples by merely changing names.
