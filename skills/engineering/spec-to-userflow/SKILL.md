---
name: spec-to-userflow
description: "Turn a spec's user stories into the project's UserFlow.md: every journey a user can walk, its screens and functional states, branches and failure paths, exit points, risk grades, and story traceability."
disable-model-invocation: true
---

# Spec To Userflow

The spec says what the user wants. The flow map says how the user walks to get it. In vibe coding the breakages concentrate in the walks: a screen state that was never designed (empty, error, stale), a branch nobody wired, a path nobody walked. This skill builds `UserFlow.md`, the project's journey map, and keeps it current.

The flow map is a product artifact, never a code artifact. Screens, states, transitions. No file names, no functions. A step that would name a file is too deep.

## When to run it

Run this after `to-spec` has published a spec (or any time a spec or requirements document exists), and before `spec-to-tests` and `to-tickets`. The journeys are what both of them consume.

## Process

1. Read the spec: the user stories are the raw material, the implementation decisions sketch the routes and entry points.
2. Read `CONTEXT.md` and any ADRs; use the project's domain vocabulary throughout, and respect decisions already recorded.
3. Read the existing `UserFlow.md` if there is one. Extend it, never replace it wholesale.
4. Identify the actors: who walks these paths (visitor, logged-in user, admin).
5. Identify the entry points: routes, URLs, first screens, CLI commands.
6. Walk each journey. Happy path first, then the decision branches, then the failure paths.
7. Inventory every screen the journey touches and its functional states (loading, empty, error, partial, stale, populated).
8. Grade each flow by risk: P0 to P3.
9. Trace every user story to at least one flow step; find the orphans.
10. Write or update `UserFlow.md`.
11. Report the summary and the gaps.

## The UserFlow.md shape

```text
Flow sections (FLOW-01, FLOW-02, ...)
Screen inventory
Story traceability
Gap report
```

Flows are ordered by the user's real journey, not alphabetically.

## Flow anatomy

```markdown
## FLOW-01 first visit

**Priority:** P0
**Entry:** `/` (landing)
**Goal:** reach the dashboard in a usable state

| Step | User action | System response | Screen / state |
| --- | --- | --- | --- |
| 1 | open `/` | app loads | landing, loading |
| 2 | wait | loading ends, default content | landing, loaded |
| 3 | (optional) refresh | state survives | landing, loaded |

**Branches**
- load fails -> error state with retry (FLOW-01-A)
- first visit, no data -> empty state with guidance

**Exit**
- dashboard visible (success)
- error screen with retry (failure)

**Stories:** US-01, US-03
**Tests:** (filled in by `spec-to-tests`)
```

Every step is one user-visible beat: what the user does, what the system does back, and the screen state that results. If a step cannot be described without a file or function, it is too deep.

## Branches and failure paths

A flow with only a happy path is a broken flow. Every flow names:

```text
decision branches  what happens when the user picks the other option
failure paths      what happens when loading fails, saving fails, auth fails
abandon points     where the user quits halfway and what is left behind
```

Name sub-flows with the parent's number and a letter: FLOW-01-A, FLOW-01-B.

## Screen states

Screen states are where vibe coding breaks. A screen that only ever renders one state ships broken the first time the data is empty or the request fails. The map carries an inventory:

```markdown
## Screen inventory

| Screen | States |
| --- | --- |
| landing | loading, loaded, empty, error |
| dashboard | empty, populated, stale, syncing, error |
```

The inventory is a checklist against the failure matrix in `spec-to-tests`: a state nobody designed becomes a test nobody wrote.

## Risk grades

```text
P0  core journey: the product is unusable without it
P1  primary tasks
P2  secondary tasks and common edges
P3  rare paths
```

This vocabulary is shared with `spec-to-tests` verbatim, so a P0 flow becomes P0 tests.

## Story traceability

Both directions:

```text
every user story lands in at least one flow step
every flow step traces to a story, or is marked implicit
```

Implicit steps are the edge and failure paths the stories never mention but the product still needs. Orphan stories (stories no flow reaches) go to the gap report, not silently dropped.

## Non-UI products

For a CLI or an API, replace screens with state: steps describe resource and state transitions instead of pages. The shape is the same.

## Change-driven updates

When the spec, code, or flows change, decide before anything else:

```text
Which flows are now invalid?
Which flows need adding or re-walking?
Which stories are newly orphaned?
```

`UserFlow.md` must never become a historical relic.

## Output summary

Always end with the counts:

```text
New Flows: 4
Updated Flows: 1
Screen States: 12
Orphan Stories: 2
P0 Flows: 2
```

## Relations to other skills

- **Upstream:** `to-spec` produces the user stories this skill walks. Tell the user to run `/to-spec` first when no spec exists.
- **Downstream:** `spec-to-tests` consumes the flow map: its Layer 1 converts FLOW-NN into per-step test cases instead of inventing its own flows. Tell the user to run `/spec-to-tests` next.
- **Tickets:** `to-tickets` groups its tickets by flow. Tell the user to run `/to-tickets` after.
- **Unsettled interaction:** when a flow's interaction cannot be settled on paper, Call the Skill tool with `prototype` and answer it with throwaway code.

## Core principle

```text
The spec says what the user wants.
The flow map says how the user walks to get it.
A flow map that misses a state ships a broken screen.
```
