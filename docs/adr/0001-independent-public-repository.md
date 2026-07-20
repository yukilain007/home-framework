# Independent public repository

## Status

Accepted

## Context

A public framework must not inherit private instance files, source-control objects, paths, or
history.

## Decision

HOME Framework is developed in an independent repository with a new Git history. Private instance
repositories are not remotes, submodules, subtrees, fixtures, or migration sources.

## Consequences

Reusable ideas must be rewritten as generic contracts. Public examples must be created from
fictional material, and changes cannot depend on private history.
