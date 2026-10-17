# Document content integrity migration

The crawler now publishes document assets and content through the LMS Worker. Queue/blob bookkeeping still uses the existing Cloudflare D1 credential. That shared credential has not been revoked or changed.

## Runtime contract

- Set `DOCUMENT_INGEST_TOKEN` only after deploying the matching LMS routes and additive content migration.
- `DOCUMENT_INGEST_BASE_URL` is an HTTPS origin (defaults to `https://tailieu.beekip.vn`). The scheduled workflow forwards the repository secret and variable with these names.
- Asset requests are binary POSTs to `/api/internal/documents/assets?key=...` with `Content-Type`, `X-Content-Sha256` and Bearer authentication. PDF limit is 50 MiB; cover limit is 2 MiB. The Worker creates only absent assets and reuses existing byte-identical assets; different bytes must return 409.
- Content requests POST JSON `schemaVersion:1` to `/api/internal/documents/ingest`; format and provenance are explicit. Description limit is 12,000 Unicode code points, title 200, short description 500; oversize input fails without truncation.
- Incoming render status is pending. Only the LMS compiler may certify rendering. Missing/conflicting source evidence is marked for review while existing public documents remain readable.
- An existing source identity is checked by source URL UUID / source key prefix before uploads. Source/slug conflicts fail for review. The endpoint must return the existing identity without overwriting edited content.

## Remote preflight authentication

Run the scheduled workflow manually with `mode=preflight` before enabling ingest. It requires `DOCUMENT_INGEST_TOKEN` in addition to the existing Cloudflare account/database/bucket/token secrets. The production origin is fixed to `https://tailieu.beekip.vn`; `DOCUMENT_INGEST_BASE_URL` must agree with the verified app origin.

Remote preflight requires D1 columns `description_format`, `source_provenance_json`, and `content_quality_json`. After the existing private cover proof, it sends two fixed invalid requests with the dedicated ingest token, using a separate HTTP client, a 15-second timeout, no redirects and response bodies limited to 4 KiB:

- Empty JSON `{}` to `/api/internal/documents/ingest` must return HTTP 422 with `Unsupported schemaVersion.`
- Empty bytes to `/api/internal/documents/assets?key=invalid-preflight-key` must return HTTP 422 with `Invalid asset key or SHA-256.`

Both deployed validators reject these requests before accessing D1 or R2. No valid document, asset key, digest or file is supplied. A wrong token, redirect, unexpected success or changed validation response fails preflight. Cloudflare credentials are never sent to the app. `--local-read-only` remains the earlier resource/cover check: it neither requires nor verifies the ingest token and is not a release activation gate.

## Legacy local workspace

`integrations/legacy-crawler` versions the bounded source snapshot and hashes from the local workspace without Git metadata. It contains no corpus, environment file or credential. Do not deploy historical `cloud-export` or `outputs/cloud_setup_backup` copies; those are inactive historical snapshots, not the reviewed source.

The old one-off direct SQL script and old unvalidated DocumentProcessingPipeline are retired. Bulk adapters use the new endpoints. Offline SQL export is an administrative artifact with validated full input and no replacement upsert; it is not an automated publication transport.

## Verification and activation

Offline tests cover province alias boundaries, contradictory evidence, historical source labels, exact body preservation, source joins, missing credential behavior, no direct SQL/asset fallback, and no uploads for a changed slug on an existing source. Existing PDF/sanitizer/agent regressions also pass.

No local scheduler/process, remote workflow, secret, D1 data, R2 asset, indexing state or deployment was changed during source verification. At inspection time no local Python/Node Beekip crawler process or matching Windows ScheduledTask was found. Remote scheduler enablement remains to be verified by the release operator. Deploy the LMS first, smoke the new endpoints in staging, then activate the producer with its distinct secret; do not re-enable old direct publication copies.
