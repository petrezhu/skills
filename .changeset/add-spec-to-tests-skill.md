---
"mattpocock-skills": patch
---

Add the `spec-to-tests` skill (engineering bucket, user-invoked). It turns a spec and the code that implements it into the project's `Tests.md`: a three-layer test matrix (user flows, capability matrix, failure matrix) with stable Test IDs, automated vs manual mapping, structured failure records, and regression relations. It runs in two phases: build the matrix after `/to-spec`, and verify after implementation.
