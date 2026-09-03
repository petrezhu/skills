## What it does

`spec-to-tests` turns a [spec](https://www.aihero.dev/ai-coding-dictionary/spec) and the code that implements it into the project's `Tests.md`: a structured, traceable test map of user flows, a capability matrix, a failure matrix, and the automated vs manual split, with failure records and regression relations.

It does not test the product for you. By the time you reach for it the deciding is done and the code exists; its job is to structure the test space so that manual testing stops being free exploration and becomes verification against a matrix, and every failure lands as a structured record bound to a Test ID. "Code complete" stops meaning "done": DONE requires automated PASS, manual PASS, and regression PASS.

## When to reach for it

You invoke this by typing `/spec-to-tests`; the [agent](https://www.aihero.dev/ai-coding-dictionary/agent) won't reach for it on its own.

Reach for it when a spec or requirements document exists and you need the test side of the build:

| Where you are | What to run |
| --- | --- |
| Spec exists, tests not built | `/spec-to-tests`: build the matrix (Phase A) |
| Implementation finished | `/spec-to-tests`: verify: run automated, score PASS / FAIL / BLOCKED, hand over the manual checklist (Phase B) |
| One hard bug, no spec | [diagnosing-bugs](https://aihero.dev/skills-diagnosing-bugs), not this skill |
| Writing the automated tests themselves | [tdd](https://aihero.dev/skills-tdd), which this skill drives at pre-agreed seams |

## Prerequisites

A spec or requirements document: the one [to-spec](https://aihero.dev/skills-to-spec) publishes, or any requirements the project already has. For Phase B, the implementation needs to exist. `Tests.md` is written to the project root and needs no issue tracker.

## The test matrix is the artifact

The leading idea is the **test matrix**: three layers, from the user down. User flows verify a real person can walk their path end to end. The capability matrix covers what flows never touch: permissions, state transitions, external dependencies. The failure matrix probes the conditions that actually fail users: empty input, double clicks, stale data, timeouts, weak networks.

Nothing is organized by file or function. Tests carry stable IDs (`DASH-001`), three statuses (PASS / FAIL / BLOCKED), and an execution attribute (AUTOMATED / MANUAL / HYBRID). A FAIL is never "there's a bug": it is steps, expected, actual, evidence, environment, bound to its Test ID so the agent can locate the context directly.

## Manual tests are checklists, not essays

The manual tests this skill writes answer the slowest part of vibe coding: after the AI ships code, you found a problem and had to describe it from scratch, with no list to check against. Each manual test is a minimal executable unit: purpose, precondition, steps, expected. Your job is to follow it and tick PASS or FAIL, not to think about what to test.

## Common questions

**Isn't this just Playwright with extra steps?**

No. Automated tests are one output of the matrix, not the matrix. Playwright owns the core flows a machine can judge; the matrix also owns everything a machine cannot: visual quality, interaction feel, and the multi-step tasks only you can sign off. Most of the matrix is manual by design, because the point is to make human testing fast, not to replace it.

**Doesn't `Tests.md` go stale the moment the spec changes?**

Only if nothing maintains it. Change-driven update is part of the skill: when the spec, code, or flows change, it re-derives which tests are invalid, which need adding, and which need regression, before anything else. A test map that stops evolving lies.

**When do I run it, before or after implementation?**

Both, and they are different phases. Phase A builds the matrix from the spec, so implementation has a target. Phase B runs after implementation to verify: automated tests scored, manual checklist handed over. DONE needs both.

## It's working if

- You can tick a Test ID PASS or FAIL without once thinking about what to test.
- A failure lands as a structured record with evidence, bound to its Test ID, instead of a chat message describing symptoms.
- After a fix, the regression scope (related tests plus the affected flow) is derivable from the file rather than guessed.
- The spec changes and `Tests.md` changes with it.

## Where it fits

`spec-to-tests` is a chain step in the main build flow, and it appears twice:

```txt
grill-with-docs → to-spec → spec-to-tests → to-tickets → implement → spec-to-tests → code-review
```

Upstream, [to-spec](https://aihero.dev/skills-to-spec) produces the spec whose user stories become the flow layer. Downstream, [to-tickets](https://aihero.dev/skills-to-tickets) cuts the spec into tickets, and [tdd](https://aihero.dev/skills-tdd) writes the automated tests this skill mapped. When you're unsure which skill or flow fits, [ask-matt](https://aihero.dev/skills-ask-matt) routes you.
