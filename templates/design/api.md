---
feature: {{feature}}
applies: undecided  # yes | no (no requires reason:)
reason:             # why this phase does not apply (only when applies: no)
artifacts: design/api/openapi.yaml   # comma-separated, relative to the feature dir; hashed into the approval
---

# API design: {{feature}}

Input: approved spec.md, verification.md and design/architecture.md.
"API" means every interface other code depends on: HTTP/REST (OpenAPI), gRPC (`.proto`), events/messages (AsyncAPI), CLI, or a library's public API (`.pyi` stub / Java interface in `design/api/`).
The machine-readable artifact **is** the contract. Editing it invalidates this approval.

## 1. Style & consumers
<!-- Which style and why. Who calls it. Compatibility promises. -->

## 2. Operations
| Operation | Input | Output | Errors | Idempotent? | AuthZ | Covers AC |
|-----------|-------|--------|--------|-------------|-------|-----------|
|           |       |        |        |             |       |           |

## 3. Error model
<!-- Error format (e.g. RFC 9457 problem+json / exception hierarchy), codes, retryable vs not. -->

## 4. Versioning & compatibility
<!-- Versioning scheme, what counts as breaking, deprecation policy. -->

## 5. Cross-cutting
<!-- Pagination, filtering, idempotency keys, rate limits, timeouts the caller should use, authn/z, size limits. -->

## 6. Examples
<!-- One request/response (or call/return) per operation, including one error. -->

## 7. Decisions
| ID      | Decision | Alternatives considered | Why |
|---------|----------|-------------------------|-----|
| D-API-1 |          |                         |     |

## 8. Design-conformance checks
The implementation must match the artifact. Prefer checks generated from it:
- Python: schemathesis / openapi-core response validation, mypy `stubtest` against the `.pyi`
- Java: swagger-request-validator / RestAssured with the OpenAPI file, compile-time conformance to the interface
- Both: breaking-change diff (oasdiff, buf breaking) against the previous released contract

| ID        | Decision | Dimension | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|-----------|----------|-----------|-------------------------|------------------------|------------|--------------------|
| DC-API-01 | D-API-1  | contract  |                         |                        | yes        |                    |

## Revision history
<!-- Reopened after approval? List the revision IDs from ../revisions.md and what changed, e.g. "R-2: added bulk-get (from oo)". -->
