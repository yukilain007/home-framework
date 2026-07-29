# HOME Framework Demo

This is a small, reproducible demo of a **purpose-scoped Markdown Context Handoff**: reviewed
local context compiled for one task, then shown to a human before they decide whether to share it
with a compatible AI tool.

> The stable installable package used here is the pre-release `home-framework==0.1.0a4`. It is an
> existing PyPI distribution and does not contain the later Apache provenance hardening from commit
> `4cb4da9adbb0311c6e5f1c226f6e22adf880c5ec`.

**Verified PyPI artifact:** `0.1.0a4`

## Verified PyPI run

Run in a fresh Python 3.12.13 virtual environment on 2026-07-26:

```bash
python -m pip install home-framework==0.1.0a4

home init example-home --name example-home
home validate example-home
home build example-home \
  --handoff project.execution \
  --as-of 2026-07-20
home doctor example-home --as-of 2026-07-20
```

All four `home` commands exited with status `0`.

- `home init` created the fictional workspace.
- `home validate` reported `Validated 3 documents with 0 warnings.`
- `home build` selected two reviewed documents and wrote
  `example-home/exports/project.execution.md`.
- `home doctor` reported `0 errors and 0 warnings` for that export.

**Context fingerprint:** `fcae86c77892749362faf3eba7d8a2a281bdba528f09c7bbab176ceaa2b882dd`

## Generated Context Handoff

The generated file contains reviewed project guidance, not a transcript. Its key content was:

```markdown
# Fictional project execution context

> Continue a fictional local implementation.

## Stable core

### `workflow.clear`

Use clear language for the fictional Atlas Notebook project.

## Current context

### `project.status`

The fictional Atlas Notebook project is ready for local validation.
```

The full output also contains a handoff ID, context date, and schema version. It is a derived file:
review it first, then decide whether to give it to an external, compatible AI tool.

## Fictional handoff scenario

A developer is moving a software project between two AI workflows. The reviewed project goal is
to complete a local validation pass; the current implementation status is that the validation
workflow is ready; and one constraint is that generated exports must stay disposable.

A proposed `Candidate` suggests adding an external issue-triage tool. It remains a proposal until
human review promotes it to approved authority. The Candidate is not an approved fact and does not
enter the final Context Handoff automatically.

## HOME does / does not

HOME validates reviewed local authority files and compiles deterministic, purpose-scoped Context
Handoffs. Only reviewed authority files participate in compilation. It does not read chat history
automatically, promote Candidates automatically, or upload files. The user decides what leaves the
local workspace and whether a reviewed handoff is shared with a compatible AI tool.

![HOME context handoff flow](https://raw.githubusercontent.com/yukilain007/home-framework/main/docs/assets/home-context-handoff-demo.svg)
