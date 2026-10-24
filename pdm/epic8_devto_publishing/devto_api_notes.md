# DEV Community / Forem API Notes (E8-S1 Spike)

These notes document the capabilities, endpoints, and behaviors of the DEV Community (Forem) API verified live against the API in October 2026.

## 1. Authentication & Base URL

- **Base URL**: `https://dev.to/api`
- **Authentication**: Sent as the `api-key` HTTP header.
  - Secret: `DEV_TO_API_KEY` stored in `blog-agent/.env`.
  - **Security rule**: The API key must never be logged, printed in error messages, or included in client traces.
- **Content Negotiation / API Version Header**:
  - `Accept: application/vnd.forem.api-v1+json`
  - `Content-Type: application/json`

## 2. Endpoints

### 2.1 List Own Articles (including drafts)
- **Endpoint**: `GET /api/articles/me/all`
- **Query params**:
  - `page`: integer (default: `1`)
  - `per_page`: integer (default: `30`, max up to `1000`)
- **Response**: Array of article objects.
  - Unpublished drafts appear first, followed by published posts in reverse chronological order.
  - Each item includes `id`, `title`, `published`, `canonical_url`, `url`, `body_markdown`, `tag_list`, `published_at`, `cover_image`, `slug`.
- **Use in Idempotency**:
  Before creating a new article, `DevtoPublisher` queries `GET /api/articles/me/all` and checks if an existing article matches the exact `canonical_url` or `title`. If found, it adopts the existing `id` and issues `PUT` instead of `POST`.

### 2.2 Create Article
- **Endpoint**: `POST /api/articles`
- **Status code on success**: `201 Created`
- **Request payload**:
  ```json
  {
    "article": {
      "title": "Article Title",
      "body_markdown": "Markdown content...",
      "published": false,
      "tags": ["ai", "python"],
      "canonical_url": "https://leon-pham.vercel.app/posts/my-post",
      "description": "Short excerpt...",
      "main_image": "https://cdn.sanity.io/images/..."
    }
  }
  ```
- **Response**: Returns article object containing `id`, `url`, `path`, `published_at`, etc. Note: For drafts (`published: false`), the article's edit URL is `https://dev.to/dashboard` and draft preview is available at `url`.

### 2.3 Update Article
- **Endpoint**: `PUT /api/articles/{id}`
- **Status code on success**: `200 OK`
- **Request payload**:
  ```json
  {
    "article": {
      "title": "Updated Title",
      "body_markdown": "Updated Markdown...",
      "published": false,
      "tags": ["ai", "finetuning"],
      "canonical_url": "https://leon-pham.vercel.app/posts/my-post",
      "main_image": "https://cdn.sanity.io/images/..."
    }
  }
  ```

### 2.4 Unpublish Article
- **Endpoints**:
  - `PUT /api/articles/{id}/unpublish`
  - Or `PUT /api/articles/{id}` with `{"article": {"published": false}}`
- **Hard Deletion**:
  - `DELETE /api/articles/{id}` returns `404 Not Found`. Forem's REST API does not provide hard deletion; unpublishing and setting `published: false` archives the post.

## 3. Fields & Rules

| Field | Type | Rules |
|---|---|---|
| `title` | string | Stripped of markdown heading prefixes (e.g. leading `# `). |
| `body_markdown` | string | Rendered markdown without the leading H1. |
| `published` | boolean | `false` creates/updates as a private draft. `true` publishes live. |
| `tags` | array[str] | **Max 4 tags**. Must be lowercase alphanumeric without spaces or `#`. Invalid tags or >4 tags trigger 422 Unprocessable Entity. |
| `canonical_url` | string | Full URL pointing to original source (e.g. `https://leon-pham.vercel.app/posts/<slug>`). |
| `main_image` | string (URL) | **Raster images only** (PNG, JPG, WebP). SVGs are rejected. If cover is SVG, convert to PNG or omit from `main_image`. |
| `description` | string | Optional short summary (100–160 chars). |
| `series` | string | Optional series identifier. |
| `organization_id` | integer | Optional organization ID (omitted for personal blog). |

## 4. Rate Limiting & Error Handling

- **Rate Limits**:
  - Forem restricts requests within small time windows (e.g. ~30 requests per 30 seconds).
  - Status code: `429 Too Many Requests`.
  - When hit, response may include `Retry-After` header.
  - **Handling**: Retried up to 3 times with exponential backoff (`0.5s`, `1.0s`, `2.0s` or honoring `Retry-After`).
- **Validation Errors (4xx)**:
  - Return HTTP 422 with JSON `{ "error": "...", "status": 422 }`.
  - **Handling**: Treated as non-retryable errors (`retryable=False`). Fails immediately with the server error message exposed to the user.

## 5. Live Spike Verification Result

- Verified on 2026-10-24 using owner's API key:
  1. `GET /api/articles/me/all` successfully listed articles and their published states.
  2. `POST /api/articles` successfully created a draft article (`published: false`, ID `4911219`).
  3. `PUT /api/articles/4911219` successfully updated draft body.
  4. Post verified in draft mode (`published: False`) and title archived.
