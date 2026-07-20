# Generated files are disposable

## Status

Accepted

## Context

Editing generated Markdown would create a second authority source and make builds irreproducible.

## Decision

Exports are derived artifacts, start with a generated-file warning, and are ignored by Git in the
fictional example. Authority YAML files and the selected date are sufficient to rebuild them.
Generated Markdown is untracked by default, and doctor reports an accidentally tracked export
without changing Git.

## Consequences

Consumers must edit authority files rather than exports. Build metadata may change, while the
fingerprint remains stable for identical semantic inputs.
