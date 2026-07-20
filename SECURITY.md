# Security policy

## Supported version

HOME Framework is an alpha project. Security fixes target the latest `0.1.x` prerelease.

## Reporting

Do not place private authority content, credentials, or identifying paths in a public report.
Until a public project host and private reporting channel are configured, keep vulnerability
reports local and provide only a minimal, fictional reproduction to maintainers.

## Security boundaries

- The CLI does not make network requests.
- The CLI does not read chat history or discover repositories outside the supplied path.
- YAML is loaded with `yaml.safe_load` and validated with strict Pydantic models.
- Unknown fields and unsupported schema versions fail validation.
- Build refuses repositories with validation errors.
- Symbolic links in the workspace root path, authority directories, and authority files are
  rejected before repository content is read.
- `secret` content is never exportable.
- The manifest default export directory and every custom `--output` must remain inside the
  workspace and cannot contain symbolic-link components.
- Markdown output is written with a same-directory temporary file and atomic replacement.
  Initialization publishes files with atomic no-replace semantics and never overwrites a path
  created concurrently.
- `home doctor` and `scripts/scan_secrets.py` scan only regular files beneath the supplied
  workspace, do not follow symbolic links, reject files over 1 MiB, and redact matched values.
- Doctor uses read-only Git commands with optional locks disabled. It inspects Git only when the
  supplied workspace itself contains a normal `.git` directory; it does not discover parent
  repositories or follow linked-worktree metadata outside the workspace. Repository-configured
  filesystem monitors and hooks are disabled for every diagnostic Git command.
- Export diagnosis opens the generated file without following a final symbolic link and reads at
  most 4 KiB from its first line; Markdown bodies are never loaded for stale detection. Platforms
  without no-follow file opening fail closed instead of silently weakening this boundary.
- Secret scanning uses high-confidence patterns and exact path/rule allowlisting. It is a
  defense-in-depth aid rather than proof that data is safe to publish.

These controls do not replace operating-system permissions. Anyone who can edit authority files
or the local package can change the inputs or implementation. Review file ownership and source
control access before using the framework with non-public data.
