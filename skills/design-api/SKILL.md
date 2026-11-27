---
name: design-api
description: Design stage 3b of the software factory. Write design/api.md and its machine-readable contract (OpenAPI, AsyncAPI, .proto, or a .pyi stub / Java interface for library APIs), hashed into the approval, plus DC-API conformance checks. Use after design/architecture.md is approved.
---

# Stage 3b: API design

Prerequisites: spec, verification and architecture approved. Run `.factory/factory stage api`.

"API" means any interface other code depends on: HTTP, gRPC, events/messages, CLI, or the public API of a library or module.

## Procedure
0. **Check upstream first.** Read every earlier approved document. If this phase can't be designed well without changing one of them (a missing operation, an entity the schema lacks, a resiliency assumption that doesn't hold, an AC that is infeasible), stop. Propose `.factory/factory revise <doc> --from api "<why>"` to the user, and do not compensate locally. Draft this phase once the revision is approved.
1. **Draft with the `api-designer` subagent.** It fills `design/api.md` and writes the contract artifact under `design/api/`:
   - HTTP: `design/api/openapi.yaml` (start from `${CLAUDE_PLUGIN_ROOT}/templates/design/openapi.yaml`)
   - events: `asyncapi.yaml`; gRPC: `*.proto`
   - library: a `.pyi` stub or a Java interface file with the public signatures and docstrings/Javadoc
   List each file (or a directory) in the `artifacts:` frontmatter. Approval hashes them, so editing any of them invalidates it.
2. **Cover every AC.** Each operation names the AC(s) it serves. Each error path in the spec maps to a documented error.
3. **Settle the cross-cutting rules:**
   - the error model (problem+json or an exception hierarchy)
   - versioning, and what counts as a breaking change
   - idempotency keys for unsafe retries (consistent with architecture section 6)
   - pagination, limits, authn/z
4. **Conformance checks** (`DC-API-NN`), generated from the artifact wherever possible:
   - Python: schemathesis or openapi-core response validation; mypy `stubtest` for `.pyi` stubs
   - Java: swagger-request-validator / RestAssured against the OpenAPI file; the implementation `implements` the approved interface
   - breaking-change diff (oasdiff, buf breaking) against the last released contract
5. **Not applicable?** No new or changed interface → `applies: no` with a `reason:`.
6. **Approval.** Summarise the operations, the error model and the compatibility promise. Ask the user to run `! .factory/factory approve api`.
