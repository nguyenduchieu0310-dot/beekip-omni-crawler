# Legacy crawler source integration

This directory versions the bounded source changes from the legacy local crawl workspace, which has no Git metadata. No corpus, database, environment file or credential is included. The `source/` directory is the reviewable complete source for the changed files. `manifest.json` records SHA-256 identities. The legacy directory has no Git baseline; temporary pre-edit captures were not retained across tool processes, so no original-source patch is claimed. A null previous hash means no trustworthy baseline is available, not that the file was absent. Review the complete source snapshots alongside the modern Git diff.

Document PDFs and covers are sent as exact binary bytes plus SHA-256 to the Worker asset endpoint, which owns conditional R2 creation. No document asset management API PUT or Wrangler upload fallback remains. Source identity is checked before uploads so a changed slug cannot replace an existing source PDF.

Live document publication now requires `DOCUMENT_INGEST_TOKEN` and posts a version 1 JSON request to `DOCUMENT_INGEST_BASE_URL/api/internal/documents/ingest`. Missing configuration fails before asset upload. Document publication cannot fall back to direct D1 or the legacy HTTP API. The one-off publisher and obsolete unvalidated pipeline are retired. Offline SQL export remains an explicit administrative artifact, rejects oversize or unproven source input and does not replace existing rows; do not feed it to an automated production writer.

The dedicated publication token is separate from the existing Cloudflare credential. Crawler queue/blob ledger operations still use D1; no shared credential was revoked by this change. The modern source scheduled workflow forwards the new secret but no local task, process, repository secret or remote workflow was changed or executed.

Deploy the LMS endpoint and content schema before enabling the updated producers. Existing manifest rows missing format/provenance must be regenerated from their original payload or joined uniquely to `crawler_state.db`; ambiguous joins remain pending. Generated render QA is `pending`, not a manufactured success. The server compiles content and stamps its own result.

Tests in the modern `tests/test_document_*.py` cover the source contract and reported province error. No production mutation was used during verification.
