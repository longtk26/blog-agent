# Epic 12 — S3 Diagram Storage

| | |
|---|---|
| **Milestone** | M3.2 |
| **Depends on** | Epic 7/10 (diagram assets, PNG renders), Epic 8 (Dev.to publishing) |
| **Status** | Implemented 2026-11-11: awaiting owner review |

## Goal

Diagrams in published articles live on S3 (`blog-agent-longtk26`, ap-southeast-1) with URLs that never expire. This
replaces uploading them to the Sanity CDN, which matters because the website will stop reading Sanity (Epic 13) and
will render the Dev.to bodies instead.

## Decision: public prefix, not presigned URLs
The owner asked for 100-year presigned URLs. **S3 rejects any presigned URL longer than 7 days**:
`AuthorizationQueryParametersError: X-Amz-Expires must be less than 604800 seconds`, verified 2026-11-11. That limit
applies to SigV4, and SigV2 isn't available for new regions. Options were a public `diagrams/` prefix, CloudFront with
OAC, or a website route that re-signs the URL. The owner chose the **public prefix**. Anonymous `s3:GetObject` is
allowed on `diagrams/*` only; listing the bucket and every other key stay private (both return 403, verified).

## Stories

| # | Story | Pts |
|---|---|---|
| S1 | `S3AssetUploader` (`IAssetUploader`): content-addressed keys `diagrams/<sha256[:24]>.<ext>`, skip if the object exists, `Cache-Control: immutable`, SVG sanitised | 3 |
| S2 | Shared `resolve_asset()` (moved out of `SanityPublisher`); `prefer_raster=True` picks the diagram's PNG | 2 |
| S3 | Config `IMAGE_HOST=auto|s3|sanity`, `AWS_ACCESS_KEY`/`AWS_SECRET_KEY`, `S3_BUCKET`, `S3_REGION`, `S3_PREFIX`, `S3_PUBLIC_BASE_URL`; Dev.to publisher uses S3 when configured | 1 |
| S4 | `make s3-setup` (dry run) / `APPLY=1`: ensure the public-read grant on the prefix only, then smoke-test it | 2 |
| S5 | Dev.to render: strip `<b>`/`</b>` inside ```` ```mermaid ```` fences (Dev.to shows them as literal text); owner request | 1 |

### Acceptance criteria
- Dev.to bodies link diagrams as `https://<bucket>.s3.<region>.amazonaws.com/diagrams/<hash>.png`, and anonymous GET returns 200 `image/png`.
- Publishing the same diagram twice reuses the same object; an edited diagram gets a new URL.
- With S3 not configured (or `IMAGE_HOST=sanity`), behaviour is unchanged: Sanity CDN uploads.
- Sanity documents are unchanged; they still need Sanity asset `_ref`s.

## Implementation notes (2026-11-11)
- **Code:** `publishing/infrastructure/adapters/s3_asset_uploader.py`, `asset_resolver.py` (new);
  `sanity_publisher.py` (`_resolve_asset` delegates, same behaviour); `adapters/__init__.py` (uploader choice);
  `configs/config.py`; `publishing/scripts/setup_s3_public_prefix.py`; `boto3==1.44.0` in `requirements.txt`.
  Installing boto3 moved `python-dateutil` 3.0.0 → 2.9.0.post0 (`botocore` needs <3). Every dependent package accepts that.
- **Bucket state:** by the time the script ran, the bucket already had Block Public Access off and a `PublicReadDiagramsOnly`
  policy on `diagrams/*`, presumably set by the owner. The script detects an equivalent grant and changes nothing. It also
  never touches the ACL flags. `BucketOwnerEnforced` already disables ACLs; turning `BlockPublicAcls`/`IgnorePublicAcls`
  back on would be a harmless extra hardening.
- **Fixed on the way (pre-existing bug):** Dev.to `main_image` detection required `![alt](url)`, but every rewritten image is
  `![alt](url "title")`, so no body image was ever chosen as the cover. The regex now accepts an optional title, so the
  first raster diagram becomes the Dev.to cover image.
- **Mermaid `<b>`:** the Mermaid generator bolds titles with `<b>` for the website. Only the Dev.to render strips them; `<br/>`
  and text outside Mermaid fences are untouched.

### Verified
- `tests/unit/test_s3_asset_uploader.py`: 13 tests (key and URL format, idempotency, SVG sanitising, custom prefix/base URL,
  error mapping, PNG preference, Sanity default, Dev.to render + cover, host resolution). A Mermaid `<b>` test was added to `test_devto_renderer.py`.
- Unit suite 433 passed; `make test-integration` 469 passed. The Dev.to golden hash for `fine_tuning_concepts` changed (`1e20b0d8…` → `e14cf72e…`) only because its Mermaid blocks contain `<b>` tags, which are now stripped; the implementation part is unchanged.
- Live: a real diagram PNG uploaded from the host and from the rebuilt api container; anonymous GET 200 `image/png`,
  `public, max-age=31536000, immutable`; bucket root and a non-prefix key return 403.
- In the container, a stored revision rendered for Dev.to (no POST): `asset://` → S3 PNG URL (200); that PNG became `main_image`;
  8 `<b>` tags in its Mermaid block → 0.

### Not verified
- An actual publish to dev.to with the new body; it creates or updates a real article, so it waits for the owner.
- Thumbnails still go to Sanity only (Dev.to never received them). Moving them to S3 belongs with Epic 13.
