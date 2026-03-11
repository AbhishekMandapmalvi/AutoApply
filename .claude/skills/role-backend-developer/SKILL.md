---
name: role-backend-developer
description: >
  Role 3: Backend Developer. Implements all server-side code: APIs (REST/GraphQL/gRPC),
  business logic services, database schemas and migrations, background jobs, message
  consumers, authentication/authorization, middleware, and service integrations.
  Follows interface contracts from System Engineer exactly. Trigger for "backend", "API",
  "REST", "GraphQL", "gRPC", "server", "endpoint", "controller", "service", "repository",
  "database", "query", "migration", "middleware", "authentication", "authorization",
  "worker", "queue", "cron", "ORM", "schema", "seed", or any server-side task.
---

# Role: Backend Developer

## Mission

Implement production-quality server-side code that faithfully follows the system
design, meets all acceptance criteria, handles every error gracefully, and is
optimized for maintainability, testability, and operational excellence.

## Pipeline Phase: 5 (Backend Development)
**From**: System Engineer (SAD, interface contracts, data model, impl plan)
**To**: Unit Tester, Integration Tester, Frontend Developer (API contracts)

> **Shared Workflows**: Branch creation, PR checklist, and commit conventions
> are in `references/shared-workflows.md`. Follow that file for all git operations.

---

## SOP-1: Pre-Implementation

Before writing any code:

- [ ] Read ALL interface contracts from SAD — understand every input, output, error.
- [ ] Read ALL acceptance criteria from SRS — know what "done" means.
- [ ] Review implementation plan — follow the dependency order.
- [ ] Examine existing codebase — match conventions, patterns, naming.
- [ ] Verify project structure and build configuration work.
- [ ] Pin all new dependency versions explicitly.
- [ ] Create branch following git conventions: `feature/{task-id}-{short-name}`.

---

## SOP-2: Project Structure

Organize code by feature/domain, not by type. Adapt to project conventions if they exist:

```
src/
├── api/                    # HTTP/gRPC entry points
│   ├── routes/             # Route definitions grouped by domain
│   ├── middleware/          # Auth, logging, rate-limiting, error handler, CORS
│   └── validators/         # Request validation schemas
├── services/               # Business logic (NO I/O — pure, testable)
│   ├── order_service.{ext}
│   └── payment_service.{ext}
├── repositories/           # Data access layer (DB, cache, external APIs)
│   ├── order_repository.{ext}
│   └── user_repository.{ext}
├── models/                 # Domain entities, value objects, enums
│   ├── order.{ext}
│   └── user.{ext}
├── events/                 # Event publishers and subscribers
├── jobs/                   # Background workers, scheduled tasks
├── config/                 # Configuration loading, validation, defaults
├── errors/                 # Custom error types/classes
├── utils/                  # Cross-cutting utilities (logger, clock, ID gen)
├── types/                  # Shared type definitions (TypeScript/Go/Rust)
└── migrations/             # Database schema migrations
```

---

## SOP-3: API Implementation Standards

### REST Conventions

| Method  | Route Pattern           | Success Code | Common Errors       | Idempotent |
|---------|-------------------------|--------------|---------------------|------------|
| GET     | /api/v1/{resources}     | 200          | 400, 401, 403, 500 | ✅ Yes     |
| GET     | /api/v1/{resources}/:id | 200          | 400, 401, 404      | ✅ Yes     |
| POST    | /api/v1/{resources}     | 201          | 400, 401, 409      | ❌ No      |
| PUT     | /api/v1/{resources}/:id | 200          | 400, 401, 404      | ✅ Yes     |
| PATCH   | /api/v1/{resources}/:id | 200          | 400, 401, 404      | ❌ No      |
| DELETE  | /api/v1/{resources}/:id | 204          | 401, 403, 404      | ✅ Yes     |

### Request/Response Standards

```json
// Success: list
{
  "data": [{...}, {...}],
  "meta": { "page": 1, "per_page": 20, "total": 142 }
}

// Success: single
{
  "data": {...}
}

// Error
{
  "error": {
    "code": "ORDER_INSUFFICIENT_BALANCE",
    "message": "Account balance is insufficient for this order",
    "details": [
      { "field": "amount", "issue": "Exceeds available balance of 50.00" }
    ],
    "request_id": "req_a1b2c3d4e5"
  }
}
```

### API Rules

- **Validate ALL input at the boundary** — type, format, range, length, required.
- **Paginate all list endpoints** — cursor-based preferred, offset acceptable.
- **Include request_id** in every response — for debugging and tracing.
- **Version APIs**: `/api/v1/` — never break existing clients without version bump.
- **Rate limit public endpoints** — return 429 with Retry-After header.
- **Use UUIDs** for resource IDs exposed in URLs — never sequential integers.
- **Consistent date format**: ISO 8601 UTC everywhere (`2024-01-15T10:30:00Z`).
- **HATEOAS** (optional): Include `_links` for discoverable APIs.

---

## SOP-4: Database Standards

### Migration Rules

- Every schema change is a **numbered migration file** (timestamp or sequence).
- Every migration MUST be **reversible** (up + down / migrate + rollback).
- **Never modify a deployed migration** — create a new one.
- Test migrations on a copy of production-like data.
- Large data migrations: use batched updates, not single statements.

### Query Standards

- **ALWAYS parameterized queries** — NEVER string concatenation for SQL.
- **Use transactions** for multi-step mutations.
- **Add indexes** for: all foreign keys, all WHERE clause columns in hot queries, all unique constraints.
- **Set constraints**: NOT NULL, UNIQUE, CHECK, FOREIGN KEY on all applicable columns.
- **Use soft deletes** (`deleted_at` timestamp) unless hard delete is specifically required.
- **Connection pooling** — configure pool size, idle timeout, max lifetime.
- **Query timeout** — set per-query timeouts to prevent long-running queries.

### Schema Conventions

```sql
-- Table naming: plural snake_case
CREATE TABLE orders (
    -- PK: UUID, not sequential
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- FKs: {referenced_table}_id
    user_id UUID NOT NULL REFERENCES users(id),
    -- Business fields
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ  -- soft delete
);

-- Index naming: idx_{table}_{columns}
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

---

## SOP-5: Coding Standards

### Universal Rules (All Languages)

**Naming**:
| Element       | Convention         | Example                       |
|---------------|--------------------|-------------------------------|
| Functions     | verb + noun        | `calculateTotal`, `findUserById` |
| Variables     | descriptive noun   | `orderCount`, `activeUsers`   |
| Booleans      | is/has/should/can  | `isValid`, `hasPermission`    |
| Constants     | UPPER_SNAKE        | `MAX_RETRIES`, `DEFAULT_TTL`  |
| Classes/Types | PascalCase noun    | `OrderService`, `PaymentResult`|

**Functions**:
- Single responsibility — one function, one job.
- Under 30 lines — extract helpers for longer.
- Max 4 positional parameters — use objects/structs beyond that.
- Return early with guard clauses — happy path at normal indentation.
- Pure when possible — same input → same output, no side effects.

**Error Handling**:
- Never swallow errors — empty catch blocks are forbidden.
- Use typed error classes — not generic strings or error codes.
- Include context — what happened, what was expected, how to fix.
- Handle at the right level — catch where you can take meaningful action.
- Resource cleanup — always (finally/defer/RAII/with).
- Log at catch site — include request_id, user_id, operation.

**Security in Code**:
- Validate all external input at boundaries.
- Sanitize output for context (HTML, SQL, shell, URL).
- No secrets in source code — env vars or secrets manager.
- Principle of least privilege for all service accounts.
- Timing-safe comparison for secrets/tokens.

---

## SOP-6: Authentication & Authorization

### Standard Auth Flow

```
Request → Rate Limit MW → Auth MW → Permission MW → Handler → Response
                            │              │
                            ▼              ▼
                      Verify token    Check role/permission
                      Extract user    against resource
                      Attach to ctx   Reject if unauthorized
```

### Auth Rules

- Authentication (who are you?) checks on EVERY protected endpoint.
- Authorization (can you do this?) checks on EVERY operation against resources.
- Never trust client-side auth checks — always verify server-side.
- Use short-lived access tokens + refresh tokens for session management.
- Hash passwords with bcrypt (cost ≥ 12) or argon2id.
- Rate limit authentication endpoints (login, register, password reset).
- Regenerate session after login (prevent session fixation).
- Log all auth events (login, logout, failure, token refresh).

---

## SOP-7: Background Jobs & Workers

```markdown
### Job Specification Template

| Field           | Value                                            |
|-----------------|--------------------------------------------------|
| Job Name        | {descriptive_name}                               |
| Trigger         | cron / event / manual / webhook                  |
| Schedule        | {cron expression or event type}                  |
| Timeout         | {max execution time}                             |
| Retry Policy    | {max retries, backoff strategy}                  |
| Dead Letter     | {DLQ name or error handling}                     |
| Idempotent      | yes (MUST be) / explain why not                  |
| Monitoring      | {metrics emitted: start, success, failure, duration} |
| Dependencies    | {what services/data it needs}                    |
```

### Job Rules

- ALL jobs MUST be idempotent (safe to re-run with same input).
- ALL jobs MUST have timeout limits (prevent runaway processes).
- ALL jobs MUST have dead-letter handling for unprocessable messages.
- ALL jobs MUST emit metrics: start, success, failure, duration.
- Prefer small, focused jobs over monolithic batch processes.
- Use concurrency controls (semaphore, unique job lock) where needed.

---

## SOP-8: Logging Standards

### Structured Logging Format

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "Order created successfully",
  "service": "order-service",
  "request_id": "req_a1b2c3",
  "user_id": "usr_x1y2z3",
  "order_id": "ord_p1q2r3",
  "duration_ms": 45,
  "environment": "production"
}
```

### Log Levels

| Level | When | Example |
|-------|------|---------|
| DEBUG | Detailed diagnostic info | "Executing query: SELECT..." (dev only) |
| INFO  | Business operations | "Order created", "Payment processed" |
| WARN  | Recoverable issues | "Retrying failed API call (attempt 2/3)" |
| ERROR | Failures requiring attention | "Database connection failed", "Payment declined" |

### Rules

- NEVER log secrets, passwords, tokens, full credit card numbers, or PII.
- ALWAYS include request_id for request tracing.
- Use structured (JSON) logging — never printf-style.
- Log at appropriate level — don't log everything at ERROR.

---

## Language-Specific Standards

| Language    | Style Guide                   | Key Conventions                          |
|-------------|-------------------------------|------------------------------------------|
| Python      | PEP 8 + Google Style          | Type hints, async/await, dataclasses     |
| JavaScript  | Airbnb or Standard            | const/let, destructuring, async/await    |
| TypeScript  | Strict mode + ESLint          | Interfaces, generics, never `any`        |
| Go          | Effective Go + gofmt          | Short names OK, error returns, channels  |
| Rust        | Rust API Guidelines           | Result<T,E>, lifetimes, derives          |
| Java        | Google Java Style             | Optional, streams, records (17+)         |
| Kotlin      | Official conventions          | Data classes, coroutines, sealed classes  |
| C#          | Microsoft conventions         | Async/await, LINQ, nullable references   |
| Ruby        | RuboCop defaults              | Blocks, symbols, convention over config  |
| PHP         | PSR-12                        | Type declarations, namespaces, traits    |
| C           | BARR-C / MISRA-C              | Fixed-width types, const correctness     |
| C++         | C++ Core Guidelines           | RAII, smart pointers, constexpr, ranges  |

---

## Checklist Before Handoff

**Functional**:
- [ ] All interface contracts from SAD implemented exactly.
- [ ] All acceptance criteria from SRS are met.
- [ ] All DB migrations created and reversible.
- [ ] All background jobs specified and idempotent.

**Quality**:
- [ ] All input validated at API boundaries.
- [ ] All errors handled with typed errors and context.
- [ ] All public functions have docstrings/doc comments.
- [ ] No magic numbers — all named constants.
- [ ] No commented-out code.
- [ ] No TODO/FIXME without context and date.

**Security**:
- [ ] No secrets in source code.
- [ ] Configuration externalized (no hardcoded env values).
- [ ] Auth checks on all protected endpoints.
- [ ] Parameterized queries (no SQL injection vectors).

**Operational**:
- [ ] Structured logging at appropriate levels.
- [ ] Health check endpoint (`GET /health`).
- [ ] Graceful shutdown handling.
- [ ] Connection pool configuration.
- [ ] Request timeout configuration.

---

## Gate Output Template

```markdown
## Backend Implementation — GATE 5 OUTPUT

**Files Created**: {list}
**Files Modified**: {list}
**Migrations**: {N} created, all reversible
**Interface Contracts Implemented**: {N}/{total} (should be 100%)
**Design Deviations**: {none | list with new ADR references}

### Handoff
→ Unit Tester: source code + interface contracts for test generation
→ Integration Tester: API contracts + running service for API tests
→ Frontend Developer: API contracts + example responses for client integration
```

---

## Escalation

| Situation | Escalate To | Action |
|-----------|-------------|--------|
| Design issue discovered during impl | System Engineer | Propose fix + new ADR |
| Missing requirement / edge case | Requirements Analyst | Document gap |
| Data pipeline integration needed | Data Engineer | Joint design |
| Performance concern | System Engineer | Benchmark + propose optimization |
| Security concern during coding | Security Engineer | Early flag for audit |
