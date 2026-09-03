## What it does

`spec-to-userflow` turns a [spec](https://www.aihero.dev/ai-coding-dictionary/spec)'s user stories into the project's `UserFlow.md`: the map of every journey a user can walk, with screens and their functional states, decision branches and failure paths, exit points, risk grades, and story traceability.

It does not map the code; it maps the walks. Screens and states are first-class, and file names and functions are forbidden. A flow step that would name a file is too deep, and the skill says so. The [agent](https://www.aihero.dev/ai-coding-dictionary/agent) writes the product's journey map, not an implementation plan.

## When to reach for it

You invoke this by typing `/spec-to-userflow`; the agent won't reach for it on its own.

Reach for it when the spec exists but the journeys are unmapped:

| Where you are | What to run |
| --- | --- |
| Spec exists, journeys unmapped | `/spec-to-userflow`: build `UserFlow.md` |
| Journeys mapped, need test coverage | [spec-to-tests](https://aihero.dev/skills-spec-to-tests), which consumes the map |
| One broken interaction, no map yet | [prototype](https://aihero.dev/skills-prototype) |

## Prerequisites

A spec or requirements document: the one [to-spec](https://aihero.dev/skills-to-spec) publishes, or any requirements the project already has. `UserFlow.md` is written to the project root and needs no issue tracker.

## The map is the walks, not the widgets

The leading idea is the **flow map**: flows ordered by the user's real journey, each step written as a user action, a system response, and the screen state that results. The three-part step is the whole trick. A step that only says what the user does (or only what the system does) is half a step, and the missing half is where the breakage hides.

The highest-value output is the **screen inventory**: every screen and every functional state it can be in (loading, empty, error, partial, stale, populated). A screen that only ever renders one state ships broken the first time the data is empty or the request fails. The inventory is a checklist against `spec-to-tests`, so a state nobody designed becomes a test nobody wrote.

## Happy path only is a broken flow

Every flow names its decision branches, its failure paths, and its abandon points. Sub-flows carry the parent's number and a letter (FLOW-01-A). Two-way traceability closes the loop: every user story lands in at least one flow step, and any story no flow reaches goes to the gap report instead of silently disappearing.

## Common questions

**Isn't this the same as spec-to-tests Layer 1?**

No, and the boundary is the point. `UserFlow.md` describes what the user does and sees; `Tests.md` verifies each step. `spec-to-tests` consumes the flow map rather than inventing its own, so the journeys have one source of truth. Where `UserFlow.md` is a product artifact, `Tests.md` is a test artifact.

**Why not put the flows in the spec?**

The spec is a snapshot of what was decided, and it goes stale the moment implementation teaches you something. `UserFlow.md` is living, like `Tests.md`: it re-walks itself when the spec, code, or flows change.

**Do CLI and API projects need it?**

Yes, with one substitution: steps describe resource and state transitions instead of pages. The shape, the grades, and the traceability are identical.

## It's working if

- Every user story reaches a flow step, and the orphans are listed in the gap report.
- No P0 flow has an unstated failure path.
- The screen inventory lists states beyond the happy one, for every screen.
- The flows change when the spec changes.

## Where it fits

`spec-to-userflow` is the chain step between the spec and everything that consumes it:

```txt
grill-with-docs → to-spec → spec-to-userflow → spec-to-tests → to-tickets → implement → spec-to-tests → code-review
```

Upstream, [to-spec](https://aihero.dev/skills-to-spec) produces the user stories this skill walks. Downstream, [spec-to-tests](https://aihero.dev/skills-spec-to-tests) converts each FLOW-NN into per-step test cases, and [to-tickets](https://aihero.dev/skills-to-tickets) groups its tickets by flow. When you're unsure which skill or flow fits, [ask-matt](https://aihero.dev/skills-ask-matt) routes you.
