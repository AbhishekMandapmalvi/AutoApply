# API Reference

AutoApply exposes a REST API at `http://localhost:5000`. All responses are JSON.

## Bot Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bot/start` | Start the bot |
| POST | `/api/bot/pause` | Pause the bot |
| POST | `/api/bot/stop` | Stop the bot |
| GET | `/api/bot/status` | Get bot status, counters, and uptime |
| POST | `/api/bot/review/approve` | Approve pending application (review mode) |
| POST | `/api/bot/review/skip` | Skip pending application (review mode) |
| POST | `/api/bot/review/edit` | Edit cover letter and apply (review mode) |
| GET | `/api/bot/schedule` | Get schedule configuration |
| PUT | `/api/bot/schedule` | Update schedule configuration |

**GET `/api/bot/status` response**:
```json
{
  "status": "running",
  "stop_flag": false,
  "jobs_found_today": 12,
  "applied_today": 5,
  "errors_today": 0,
  "start_time": "2026-03-09T10:30:00+00:00",
  "uptime_seconds": 3600.5,
  "awaiting_review": false,
  "ai_available": true,
  "schedule_enabled": false
}
```

### Review Mode Endpoints

When the bot is in `review` or `watch` mode, it pauses before each application and waits for user input. Use these endpoints to respond.

**POST `/api/bot/review/approve`** — Apply with generated documents as-is. Returns 409 if no review is pending.

**POST `/api/bot/review/skip`** — Skip this job and move to the next. Returns 409 if no review is pending.

**POST `/api/bot/review/edit`** — Edit the cover letter, then apply.

Request body:
```json
{
  "cover_letter": "Updated cover letter text..."
}
```

Returns 400 if `cover_letter` is missing. Returns 409 if no review is pending.

### Schedule Endpoints

**GET `/api/bot/schedule`** — Get current schedule configuration.

**Response**:
```json
{
  "enabled": false,
  "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
  "start_time": "09:00",
  "end_time": "17:00"
}
```

**PUT `/api/bot/schedule`** — Update schedule configuration. Partial updates supported.

Request body:
```json
{
  "enabled": true,
  "days_of_week": ["mon", "wed", "fri"],
  "start_time": "10:00",
  "end_time": "16:00"
}
```

- `days_of_week`: Array of `"mon"`, `"tue"`, `"wed"`, `"thu"`, `"fri"`, `"sat"`, `"sun"`. Returns 400 for invalid day names.
- `start_time` / `end_time`: `"HH:MM"` in 24-hour format. Returns 400 for invalid format. Overnight windows (e.g., `"22:00"` to `"06:00"`) are supported.

When `enabled` is set to `true`, the scheduler starts a background thread that checks every 60 seconds whether the bot should be running. The scheduler only auto-stops bots it auto-started — manually started bots are never interrupted.

## Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/applications` | List applications (filterable) |
| GET | `/api/applications/export` | Download all applications as CSV |
| GET | `/api/applications/:id` | Get full application details |
| PATCH | `/api/applications/:id` | Update status and/or notes (partial updates supported) |
| GET | `/api/applications/:id/cover_letter` | Get cover letter text and file path |
| GET | `/api/applications/:id/events` | Get activity timeline events for this application |
| GET | `/api/applications/:id/resume` | Download resume PDF |
| GET | `/api/applications/:id/description` | View saved job description (HTML) |

### GET `/api/applications`

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter by status (e.g., `applied`, `rejected`) |
| `platform` | string | — | Filter by platform (e.g., `linkedin`, `indeed`) |
| `search` | string | — | Search in job titles and company names |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Skip this many results |

**Response**: Array of application objects.

### GET `/api/applications/:id`

Returns the full application object with all fields.

**Response**:
```json
{
  "id": 1,
  "external_id": "linkedin_12345",
  "platform": "linkedin",
  "job_title": "Software Engineer",
  "company": "Acme Corp",
  "location": "New York, NY",
  "salary": "$120,000 - $150,000",
  "apply_url": "https://linkedin.com/jobs/12345",
  "match_score": 85,
  "resume_path": "/path/to/resume.pdf",
  "cover_letter_path": "/path/to/cover_letter.txt",
  "cover_letter_text": "Dear Hiring Manager...",
  "status": "applied",
  "error_message": null,
  "applied_at": "2026-03-09T14:30:00",
  "updated_at": "2026-03-09T14:30:00",
  "notes": null
}
```

Returns 404 if the application does not exist.

### PATCH `/api/applications/:id`

**Request body** (JSON) — partial updates supported, all fields optional:
```json
{
  "status": "interview",
  "notes": "Phone screen scheduled for Monday"
}
```

Both `status` and `notes` are optional. Omitted fields keep their current values. Returns 404 if the application does not exist.

### GET `/api/applications/:id/events`

Returns feed events matching the application's job title and company, ordered newest first.

**Response**:
```json
[
  {
    "id": 42,
    "event_type": "APPLIED",
    "job_title": "Software Engineer",
    "company": "Acme Corp",
    "platform": "linkedin",
    "message": "Applied to Software Engineer at Acme Corp",
    "created_at": "2026-03-09T14:30:00"
  }
]
```

Returns 404 if the application does not exist.

## Profile / Experience Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile/experiences` | List all experience files with content |
| POST | `/api/profile/experiences` | Create a new experience file |
| PUT | `/api/profile/experiences/:filename` | Update file content |
| DELETE | `/api/profile/experiences/:filename` | Delete a file |
| GET | `/api/profile/status` | Get file count, total words, AI availability |

### POST `/api/profile/experiences`

**Request body**:
```json
{
  "filename": "senior_engineer_acme.txt",
  "content": "Worked at Acme Corp as Senior Engineer..."
}
```

Filenames must match: letters, numbers, hyphens, underscores, spaces, and `.txt` extension.

### PUT `/api/profile/experiences/:filename`

**Request body**:
```json
{
  "content": "Updated content here..."
}
```

## Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get current configuration |
| PUT | `/api/config` | Update configuration (partial merge supported) |

PUT merges your changes with existing config — you only need to send the fields you want to change.

**Example** — change just the daily limit:
```json
{
  "bot": {
    "max_applications_per_day": 25
  }
}
```

**Example** — set application screening answers:
```json
{
  "profile": {
    "screening_answers": {
      "work_authorization": "Yes",
      "visa_sponsorship": "No",
      "years_experience": "5",
      "desired_salary": "150000",
      "willing_to_relocate": "Yes",
      "start_date": "Immediately",
      "gender": "Decline to Self Identify",
      "ethnicity": "Decline to Self Identify",
      "veteran_status": "I am not a veteran",
      "disability_status": "I don't wish to answer"
    }
  }
}
```

Screening answers are used by the Workday and Ashby appliers to pre-fill common application questions. All fields are optional — omitted fields are left blank on the application form.

## Feed Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/feed` | Recent bot activity events |

### GET `/api/feed`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Maximum number of events to return |

**Response** (newest first):
```json
[
  {
    "id": 42,
    "event_type": "APPLIED",
    "job_title": "Software Engineer",
    "company": "Acme Corp",
    "platform": "linkedin",
    "message": "Applied to Software Engineer at Acme Corp",
    "created_at": "2026-03-09T14:30:00"
  }
]
```

## Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/summary` | Totals grouped by status and platform |
| GET | `/api/analytics/daily` | Daily application counts |

### GET `/api/analytics/daily`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | 30 | Number of days to include |

**Response**:
```json
[
  {"date": "2026-03-08", "count": 12},
  {"date": "2026-03-09", "count": 8}
]
```

## Setup

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/setup/status` | Check if first-run wizard is needed |

**Response**:
```json
{
  "is_first_run": true,
  "ai_available": true
}
```

## WebSocket Events

AutoApply uses Socket.IO for real-time updates.

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Server → Client | Sends current bot status on connection |
| `bot_status` | Server → Client | Bot status update (same shape as GET `/api/bot/status`) |
| `feed_event` | Server → Client | Live bot activity (job found, filtered, applied, error, etc.) |

### `feed_event` payload

```json
{
  "type": "APPLIED",
  "job_title": "Software Engineer",
  "company": "Acme Corp",
  "platform": "linkedin",
  "message": "Applied to Software Engineer at Acme Corp"
}
```

Event types: `FOUND`, `FILTERED`, `GENERATING`, `APPLYING`, `APPLIED`, `REVIEW`, `SKIPPED`, `CAPTCHA`, `ERROR`.

### `REVIEW` event payload (review/watch mode only)

```json
{
  "type": "REVIEW",
  "job_title": "Software Engineer",
  "company": "Acme Corp",
  "platform": "linkedin",
  "match_score": 85,
  "cover_letter": "Dear Hiring Manager...",
  "apply_url": "https://linkedin.com/jobs/...",
  "message": "Review: Software Engineer at Acme Corp (score 85)"
}
```

## Lifecycle (used by Electron shell)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Readiness probe — returns `{"status": "ok"}` |
| POST | `/api/shutdown` | Graceful shutdown (localhost only, returns 403 otherwise) |

These endpoints are used by the Electron desktop shell to manage the Python backend lifecycle.

## AI Provider

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/validate` | Validate an API key against a provider |

### POST `/api/ai/validate`

**Request body**:
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": ""
}
```

- `provider`: One of `"anthropic"`, `"openai"`, `"google"`, `"deepseek"`. Required.
- `api_key`: The API key to validate. Required.
- `model`: Optional model override. Leave empty to use the provider's default.

**Response**:
```json
{
  "valid": true
}
```

Returns 400 if `provider` or `api_key` is missing, or if the provider is not supported.

## Knowledge Base

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/kb/upload` | Upload a career document for KB extraction |
| POST | `/api/kb/upload/async` | Upload asynchronously (returns task ID) |
| GET | `/api/kb/upload/status/:task_id` | Poll async upload status |
| GET | `/api/kb/stats` | KB summary statistics |
| GET | `/api/kb` | List KB entries (paginated, filterable) |
| GET | `/api/kb/:id` | Get a single KB entry |
| PUT | `/api/kb/:id` | Update a KB entry |
| DELETE | `/api/kb/:id` | Soft-delete a KB entry |
| GET | `/api/kb/documents` | List uploaded documents |
| POST | `/api/kb/preview` | Preview a resume from KB entries |
| POST | `/api/kb/ats-score` | Score KB entries against a JD for ATS compatibility |
| GET | `/api/kb/ats-profiles` | List available ATS platform profiles |
| POST | `/api/kb/feedback` | Submit outcome feedback for effectiveness learning |
| GET | `/api/kb/effectiveness` | Get entries ranked by effectiveness score |
| GET | `/api/kb/presets` | List saved resume presets |
| POST | `/api/kb/presets` | Create a resume preset |
| PUT | `/api/kb/presets/:id` | Update a preset |
| DELETE | `/api/kb/presets/:id` | Delete a preset |

### POST `/api/kb/upload`

Upload a career document (PDF, DOCX, TXT, MD) for AI extraction into KB entries.

**Request**: `multipart/form-data` with `file` field.

**Constraints**: Max 10 MB. Extensions: `.pdf`, `.docx`, `.txt`, `.md`.

**Response 200**:
```json
{
  "entries_created": 8,
  "message": "Processed resume.pdf: 8 entries created"
}
```

**Response 400**: No file, empty filename, or unsupported type.

### POST `/api/kb/upload/async`

Same as `/api/kb/upload` but returns immediately with a task ID. Use `/api/kb/upload/status/:task_id` to poll for completion.

**Response 202**:
```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "processing"
}
```

### GET `/api/kb/upload/status/:task_id`

**Response 200**:
```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "completed",
  "filename": "resume.pdf",
  "entries_created": 8,
  "message": "Upload completed: 8 entries created"
}
```

Status values: `processing`, `completed`, `failed`. Returns 404 for unknown task IDs.

### GET `/api/kb`

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | Filter by category (`experience`, `skill`, `education`, `certification`, `project`, `summary`) |
| `search` | string | — | Full-text search in entry text |
| `limit` | int | 50 | Results per page (max 500) |
| `offset` | int | 0 | Skip this many results |

**Response 200**:
```json
[
  {
    "id": 1,
    "category": "experience",
    "text": "Built REST APIs serving 10k requests per second",
    "subsection": "Senior Engineer — Acme Corp",
    "job_types": "[\"backend\", \"fullstack\"]",
    "tags": "[\"python\", \"api\"]",
    "effectiveness_score": 0.75,
    "usage_count": 12,
    "created_at": "2026-03-10T14:30:00"
  }
]
```

### GET `/api/kb/:id`

Returns a single KB entry. Returns 404 if not found.

### PUT `/api/kb/:id`

Update a KB entry's text, category, subsection, job_types, or tags.

**Request body** (all fields optional):
```json
{
  "text": "Updated entry text",
  "category": "skill",
  "subsection": "Technical Skills",
  "job_types": "[\"backend\"]",
  "tags": "[\"python\"]"
}
```

Returns 404 if not found.

### DELETE `/api/kb/:id`

Soft-deletes a KB entry (sets `is_active = 0`). Returns 404 if not found.

### POST `/api/kb/ats-score`

Score KB entries against a job description for ATS compatibility.

**Request body**:
```json
{
  "jd_text": "We are looking for a senior backend engineer...",
  "platform": "greenhouse",
  "entry_ids": [1, 2, 3]
}
```

- `jd_text`: Required. The job description text.
- `platform`: Optional. ATS platform for vendor-specific weights (default: `"default"`).
- `entry_ids`: Optional. Score only these entries (defaults to all active entries).

**Response 200**:
```json
{
  "score": 78,
  "components": {
    "keyword_match": 85,
    "section_completeness": 80,
    "skill_match": 70,
    "content_length": 75,
    "format_compliance": 90
  },
  "matched_keywords": ["python", "rest api", "postgresql"],
  "missing_keywords": ["kubernetes", "terraform"],
  "matched_skills": ["python", "sql"],
  "missing_skills": ["go", "rust"],
  "platform": "greenhouse"
}
```

### GET `/api/kb/ats-profiles`

**Response 200**:
```json
{
  "profiles": ["default", "greenhouse", "lever", "workday", "ashby", "icims", "taleo"]
}
```

### POST `/api/kb/feedback`

Submit outcome feedback for an application to update effectiveness scores.

**Request body**:
```json
{
  "application_id": 42,
  "outcome": "interview"
}
```

- `outcome`: One of `"interview"`, `"rejected"`, `"no_response"`.

**Response 200**:
```json
{
  "success": true,
  "updated": 5
}
```

### GET `/api/kb/effectiveness`

Returns KB entries ranked by effectiveness score (entries that lead to interviews rank higher).

**Response 200**: Array of entry objects with `effectiveness_score`, `usage_count`, `last_used_at`.

### POST `/api/kb/presets`

**Request body**:
```json
{
  "name": "Backend Engineer",
  "entry_ids": [1, 5, 8, 12, 15],
  "template": "modern"
}
```

- `name`: Required, non-empty string.
- `entry_ids`: Required, array of integers.
- `template`: Optional, defaults to `"classic"`.

**Response 201**:
```json
{
  "id": 1,
  "name": "Backend Engineer",
  "entry_ids": [1, 5, 8, 12, 15],
  "template": "modern"
}
```

### POST `/api/kb/preview`

Preview a resume compiled from KB entries.

**Request body**:
```json
{
  "template": "classic",
  "jd_text": "Optional job description for auto-selection...",
  "entry_ids": [1, 2, 3]
}
```

Returns PDF bytes with `Content-Type: application/pdf`.

## Reuse Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/reuse-stats` | KB assembly metrics |

### GET `/api/analytics/reuse-stats`

**Response 200**:
```json
{
  "total_assemblies": 45,
  "total_entries_used": 312,
  "unique_entries_used": 28,
  "interviews_from_kb": 5,
  "avg_effectiveness": 0.42,
  "top_categories": [
    {"category": "experience", "count": 180},
    {"category": "skill", "count": 90}
  ]
}
```

## Error Responses

All errors return JSON:
```json
{
  "error": "Description of what went wrong"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request — missing or invalid input |
| 404 | Not found — resource doesn't exist |
| 405 | Method not allowed |
| 500 | Internal server error |
