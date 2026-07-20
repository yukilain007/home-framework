# Use a minimal workspace manifest

## Status

Accepted

## Context

Initialization and diagnostics need a reliable way to distinguish a HOME Framework workspace
from an arbitrary non-empty directory. Inferring this from authority files would be ambiguous and
unsafe.

## Decision

Every workspace has a strict `home.yaml` with kind and schema version, a safe non-personal name,
the minimum framework version, and one relative default export directory. Pydantic is the schema
authority. Absolute paths, parent traversal, unknown fields, and symbolic-link escape are refused.

## Consequences

Existing examples require a manifest. The manifest remains intentionally small and is not a
general preferences, identity, secret, or plugin configuration store.
