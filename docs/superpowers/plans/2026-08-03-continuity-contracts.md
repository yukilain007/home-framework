# Continuity Contracts Implementation Plan

> **For agentic workers:** Implement task-by-task with a failing test before each production change.

**Goal:** Add optional, human-reviewed continuity contracts to HOME without changing the default
workspace, model-agnostic boundaries, or candidate isolation rules.

**Architecture:** Add a strict Pydantic contract family in `models.py`, load it through a separate
`continuity/` repository seam, and make compilation opt-in through `handoff.include.continuity_ids`.
Keep memory candidates and recall decisions inspect-only. Extend renderer, doctor, CLI, schemas and
the initializer's opt-in examples without adding a runtime dependency.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, Typer, JSON Schema generated from Pydantic.

## Global Constraints

- Current user input has priority over stored context.
- Persona autonomy is an anchor, not a script.
- Window state cards are notes, not commands or task lists.
- Candidates are never automatically promoted or compiled.
- No chat UI, model API, database, React, Electron, or vendor-specific fields.
- Existing workspaces and default `home init` remain backward compatible.
- Implementation is clean-room independent under the existing Apache-2.0 project.

## Tasks

1. **Contract models and failing model tests**
   - Add strict models and aliases for the six contract kinds.
   - Test required fields, date ranges, candidate lifecycle, recall action invariants, strict
     booleans, unknown-field rejection, and alias serialization.

2. **Repository seam and schema generation**
   - Add optional `continuity/` discovery without changing existing document directories or count.
   - Add `continuity_ids` to handoff selection and cross-reference diagnostics.
   - Register six schema files in `scripts/export_schemas.py` and update committed schemas through
     the existing drift checker.

3. **Compiler and renderer**
   - Select only explicitly named renderable contracts.
   - Refuse memory candidates and recall decisions in a handoff, even when a candidate is accepted.
   - Render persona, window, lifeline and maintenance sections with stable ordering and explicit
     labels that preserve their note/anchor semantics.

4. **CLI, doctor and opt-in initializer examples**
   - Add read-only `home inspect` output for continuity contracts.
   - Extend `validate` counts only when continuity files are present.
   - Add doctor warnings for unreviewed candidates, disabled current-reality precedence, and
     maintenance channels without human review.
   - Add `home init --with-continuity` fictional examples; keep default init unchanged.

5. **Documentation, examples and full verification**
   - Add a protocol guide, example YAML, and tests for inspect/validate/build/doctor behavior.
   - Run schema drift, formatting, lint, mypy, pytest, provenance, deterministic build and secret
     scan. Review the diff for absence of external implementation text.
