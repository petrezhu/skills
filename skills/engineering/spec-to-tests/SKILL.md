---
name: spec-to-tests
description: "Turn a spec, its requirements, and the code that implements them into a structured, traceable test system: the project's Tests.md with user flows, capability matrix, failure matrix, automated vs manual mapping, failure records, and regression relations."
disable-model-invocation: true
---

# Spec To Tests

The bottleneck in vibe coding is rarely code generation speed. It is verification efficiency. This skill turns manual testing from "explore and find problems" into "verify against a matrix". It builds and maintains the project's `Tests.md`, a living test map that stays in sync with the spec, the code, and what actually breaks.

Never let the AI do 100% of testing. Let the AI structure the test space: what to test, how to test it, how to judge the result, how to record failure. Automation takes the repetitive work, humans take the last mile that needs human judgment.

DONE means:

```text
Code Complete
+ Automated PASS
+ Manual PASS
+ Regression PASS
```

"Code is implemented" is not "feature is complete". "The agent says it is done" is not DONE.

## When to run it

Run this after `to-spec` has published a spec, or any time a spec or requirements document exists in the project. It has two phases:

- **Phase A, build:** a spec exists and the tests are not built yet. Generate the test system so implementation has a target to hit.
- **Phase B, verify:** implementation has finished. Run the automated tests that exist, update results, and hand the user the manual checklist.

Run it in the project root. `Tests.md` lives at the project root.

## Process

### Phase A: build the test system

1. Read the spec and requirements. If they came from `to-spec`, the user stories are the raw material for Layer 1.
2. Read the existing `Tests.md`, if there is one. Extend it, never replace it wholesale.
3. Read the relevant code and code changes. Map requirements to what was actually built.
4. Identify **user flows** (Layer 1): the paths a real user walks.
5. Identify **modules and capabilities** (Layer 2): what the flows cannot reach.
6. Generate the **failure matrix** (Layer 3): the conditions that actually fail users, picked by feature risk.
7. Convert behaviors that state themselves naturally into BDD / Gherkin. Do not force the rest.
8. Assign stable **Test IDs**.
9. Map each test to **automated or manual**.
10. Update `Tests.md`.
11. Identify **impacted regression tests**: which existing tests this change may have invalidated.
12. Report **coverage gaps**: requirements with no test behind them.

### Phase B: verify after implementation

13. Inspect the automated tests available for the affected areas.
14. Run the relevant automated tests when possible.
15. Report PASS / FAIL / BLOCKED per Test ID.
16. Produce the remaining manual test checklist, each item executable as written.

## The Tests.md shape

`Tests.md` is the project's test map. It is not a bug list and not a Playwright file dump. Organize it in three layers:

```text
User Flow
    -> Module / Capability
        -> Failure Matrix
```

Never organize the top level by file, class, or function. Code modules are only the second-layer axis.

- **User Flow:** can a real user complete their task end to end?
- **Module / Capability:** are the critical capabilities covered, including the ones flows never touch?
- **Failure Matrix:** do the exception, boundary, environment, and recovery paths behave?

## Test IDs and statuses

Every test has a unique, stable ID. The prefix reflects the capability domain, never a file name:

```text
AUTH-001   AUTH-002   DASH-001   DASH-002   API-001   UI-001
```

Status vocabulary is exactly three values:

```text
PASS    FAIL    BLOCKED
```

An execution attribute may accompany it:

```text
AUTOMATED    MANUAL    HYBRID
```

Do not invent a richer status system. PASS / FAIL / BLOCKED is the whole state machine.

## Layer 1: user flows

Write the paths a user actually walks:

```text
enter the product
-> complete a task
-> view the result
-> modify the result
-> go back
-> refresh
-> continue
```

Not:

```text
test DashboardService.create()
test DashboardService.update()
```

Example:

```markdown
## FLOW-01 first visit

- TEST-001 page loads
- TEST-002 loading ends
- TEST-003 default state is correct
- TEST-004 no obvious console error
- TEST-005 state survives refresh

## FLOW-02 create dashboard

- TEST-006 create succeeds
- TEST-007 empty name
- TEST-008 over-long name
- TEST-009 duplicate name
- TEST-010 double-click save
- TEST-011 create failure shows a message
- TEST-012 created item survives refresh
```

Every test must be executable by a person as written, and mappable to an automated test where it belongs.

## Layer 2: module / capability

Cover what user flows cannot reach. Typical groupings:

```text
AUTH    login, logout, session, permission
DATA    create, read, update, delete
API     validation, error handling, retry, timeout
UI      modal, dropdown, form, notification, loading
```

This layer builds the `Capability -> Test -> Code` link. It must not degrade into a test per function. Spend it on:

- core business logic
- state transitions
- data consistency
- permission boundaries
- external dependencies
- high-risk code paths
- modules that keep regressing

## Layer 3: failure matrix

For each important feature, probe the conditions that genuinely fail users. Default dimensions:

```text
Input          normal, empty, invalid, boundary, over-long, special chars,
               duplicate, missing field

User action    repeat click, rapid actions, cancel, back, refresh, re-enter,
               close window, exit midway

State          first use, existing data, no data, partial data, stale data,
               duplicate data, mid-transition

Network        normal, slow, timeout, 4xx, 401/403, 404, 500, offline,
               empty response, malformed response

Environment    different browsers, viewports, mobile, weak network,
               failed asset loads, resource pressure, concurrent operations
```

Pick dimensions by feature risk. Never generate a test explosion to feel thorough.

## BDD / Gherkin

When a behavior states itself naturally as a scenario, write it that way:

```gherkin
Scenario: dashboard survives reload
  Given the user is logged in
  When the user creates a dashboard
  And refreshes the page
  Then the dashboard still exists
```

Gherkin's job is one shared language for requirement, test, and assertion. Do not force every test into it; simple cases stay simple structured test cases.

## Traceability

Every important requirement must answer:

```text
Is this requirement tested?
Which Test IDs cover it?
Which are automated, which manual?
What does a failure here affect?
What needs regression after a fix?
```

Produce the matrix:

| Spec | Test ID | Type | Automation | Result |
| --- | --- | --- | --- | --- |
| create dashboard | DASH-001 | E2E | Playwright | PASS |
| create dashboard | DASH-002 | Manual | Manual | PASS |
| persistence | DATA-004 | E2E | Playwright | FAIL |

## Automated vs manual

Automated tests exist to run an already-decided test stably and repeatedly. Map them by shape:

```text
Playwright / E2E   -> core user flows
Unit               -> pure logic, algorithms, state transitions
Integration        -> key interactions between modules
Visual / a11y      -> UI properties a machine can judge
```

Automate what is high-frequency, core-path, regression-prone, clearly assertable, or expensive to do by hand.

Keep manual what needs a human: visual quality, interaction feel, real user paths, the overall sense of a multi-step task, product experience an AI cannot judge, and exploratory testing.

For writing the automated tests, Call the Skill tool with `tdd` and work at pre-agreed seams.

## Manual test template

A manual test is a minimal executable unit. The user's job is to follow it, not to think about what to test:

```markdown
### DASH-003

**Purpose:** dashboard survives reload

**Precondition**
User is logged in

**Steps**
1. Create a dashboard
2. Enter `Test`
3. Click Save
4. Refresh the page

**Expected**
Dashboard `Test` still exists

**Type**
MANUAL / HIGH

**Result**
PASS / FAIL / BLOCKED
```

## Failure recording

A FAIL gets a structured record. "There is a bug" is never enough. Minimum:

```text
Test ID
Steps
Expected
Actual
Evidence
Environment
```

```markdown
## BUG-024

Test: DASH-003
Status: OPEN

### Steps
1. Create dashboard
2. Save
3. Reload

### Expected
Dashboard remains

### Actual
Dashboard disappears

### Evidence
- Screenshot
- Console
- Network

### Environment
Chrome / macOS

### Suspected Area
Persistence

### Fix
TBD
```

Every failure binds to a Test ID, so the agent can locate the context directly.

## Regression

After a fix, "the reported problem went away" is not enough. Regression scope is:

```text
Failed Test
+ Related Tests
+ Affected User Flow
```

```text
DASH-003 FAIL
    -> fix
    -> re-run DASH-003
    -> run DASH-001 / DASH-002 / DASH-004
    -> run FLOW-02
```

Build relations between tests so the regression scope is derivable from `Tests.md` instead of guessed.

## Change-driven updates

When the spec, code, or user flows change, decide before anything else:

```text
Which tests are now invalid?
Which tests need adding?
Which tests need modifying?
Which tests need regression?
```

`Tests.md` must never become a historical relic. It evolves with the product or it lies.

## Risk priorities

Generate by risk, never by volume:

```text
P0  core business, data corruption, permissions, serious regression
P1  core user flows
P2  common exceptions and boundaries
P3  low-probability scenarios
```

Forbidden: one function -> a dozen mechanical input combinations -> zero user value. Coverage theater. Every test must answer one question: if this behavior breaks, what happens to the user or the system?

## Output summary

Always end with the counts:

```text
New Tests: 12
Updated Tests: 5
Automated: 8
Manual: 9
Regression Required: 6
Coverage Gaps: 3
```

## Definition of Done

A feature is DONE only when:

```text
[x] Code complete
[x] Relevant automated tests PASS
[x] Relevant manual tests PASS
[x] Failure cases reviewed
[x] Related regression PASS
[x] No BLOCKED test without explicit acceptance
```

## Relations to other skills

- **Upstream:** `to-spec` produces the spec whose user stories become Layer 1. Run it before this skill.
- **Automation:** when mapping tests to code, Call the Skill tool with `tdd` to write the automated ones at pre-agreed seams.
- **Failure analysis:** when a FAIL needs a root cause, Call the Skill tool with `diagnosing-bugs`.
- **Acceptance:** after `implement` finishes, run Phase B here before `code-review` closes out the diff.
- The BDD conversion and the traceability matrix are folded into this skill. If they ever grow enough to stand alone, split them out; until then they stay here.

## Core principle

```text
Build fast. Know what to test. Test systematically.
Record failures precisely. Fix. Re-test.
```

The goal is not that the AI runs all tests. It is that the AI structures the test space, automation owns the repetition, and the human only does the last mile that genuinely needs human judgment.
