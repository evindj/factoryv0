---
feature: {{feature}}
---

# Revisions: {{feature}}

The approval loop. A later stage that finds a problem in an approved document doesn't work around it. It reopens the document:
`.factory/factory revise <spec|verification|architecture|api|data|oo> --from <stage> "<why>"`.
An open revision blocks production code. Re-approving the document closes it. Every later document must then be
re-confirmed by the human (`approve <doc> --yes` after reviewing the upstream diff).

| ID | Opened | Doc | Triggered by | Reason | Status | Closed by |
|----|--------|-----|--------------|--------|--------|-----------|
