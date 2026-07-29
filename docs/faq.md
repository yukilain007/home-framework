# Frequently Asked Questions

HOME is a local-first framework for managing, reviewing, and transferring human-owned AI
context.

HOME is not an AI model, memory service, RAG system, or chat history importer.

## Is HOME an AI memory system?

Not in the usual sense. AI memory systems often ask: “How can a system remember information about
a user?” HOME asks: “What information has the user reviewed and allowed to become reusable
context?”

Its working distinctions are simple:

```text
conversation != fact
suggestion != approval
history != permission
```

HOME validates reviewed authority files, then compiles selected information into a handoff for one
purpose. It does not automatically turn a conversation into reusable context.

## Is HOME a RAG system?

No. RAG focuses on retrieval:

```text
documents → retrieval → model context
```

HOME focuses on context authorization:

```text
information → review → approved authority → purpose-scoped handoff
```

RAG helps find information. HOME helps decide what context should be carried forward.

## Does HOME replace ChatGPT, Claude, local models, or AI agents?

No. HOME is a context layer. It does not provide:

- model inference;
- a chat UI;
- hosting; or
- agent execution.

It prepares reviewed context that a compatible tool can use.

## Why not automatically save every conversation?

Conversations can contain temporary information, incorrect model assumptions, sensitive material,
or statements that should not represent long-term context. Not every statement should be carried
forward.

HOME separates:

- **candidate** — a proposal that is not compiler input;
- **approved authority** — reviewed information that may be selected for a build; and
- **handoff** — a purpose-scoped output compiled from selected authority.

## Can HOME work with local models?

Yes. Any tool that can accept text or files can consume a Context Handoff. HOME does not require a
particular model provider, but the operator remains responsible for deciding what to provide to
each tool.

## Does HOME make AI private?

No. HOME provides control over what context is prepared and shared. It does not guarantee private
model providers, secure networks, or zero data processing by external services.

## How is HOME different from a prompt template?

A prompt template says: “Send this instruction every time.” HOME provides:

- structured context;
- reviewed authority;
- deterministic compilation; and
- a purpose-scoped handoff.

This makes the selected context inspectable before it is provided to another tool.

## Why human review?

The goal is not maximum memory. The goal is controlled continuity.

The user decides what represents:

- themselves;
- their project; and
- their current goals.

## Current status

HOME Framework is currently alpha. The current release is `home-framework==0.1.0a5`.
Capabilities and interfaces may change.

## Short version

HOME does not try to make AI remember everything. It helps users decide what context is worth
carrying forward.
