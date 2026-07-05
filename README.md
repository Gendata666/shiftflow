# ShiftFlow — AI Shift-Scheduling Assistant

ShiftFlow turns a manager's natural-language description of scheduling rules — in Bulgarian or English — into a mathematically verified work schedule. The manager writes rules the way they would explain them to a person; a constraint solver builds the schedule; an independent verifier proves every rule holds and reports honestly when a rule is mathematically impossible to satisfy.

**Design law: the AI translates; the solver thinks.** The language model never writes a schedule cell. It only converts prose into a structured rulebook (and back into explanations). Everything numerical — generation, checking, repair — is deterministic, testable code that costs zero AI tokens to run.

| | |
|---|---|
| Live frontend | https://shiftflow-ten-sage.vercel.app |
| Live API | https://shiftflow-api.digitalnebula.net (`/docs` for the OpenAPI browser) |
| Repository | github.com/Gendata666/shiftflow |
| Status | Pilot (free-tier AI, self-hosted backend — see [Deployment](#deployment)) |

---

## 1. Tech stack

| Layer | Technology | Why |
|---|---|---|
| Solver | **Google OR-Tools CP-SAT** (Python) | Industry standard for rostering; exact feasibility proofs and violation counting — required for "if impossible, get as close as possible and say so" |
| AI — manager copilot | **Gemini** (`gemini-3.5-flash`, free tier) or **Claude Opus 4.8** — switchable via `LLM_PROVIDER` | Structured outputs + tool use; identical contracts on both providers |
| AI — employee messages | **Claude Haiku 4.5** | High volume, low complexity, ~$0.001/message |
| API | **FastAPI** (async) + SQLAlchemy 2 async + asyncpg | SSE streaming chat, typed Pydantic boundaries |
| Background compute | `ProcessPoolExecutor` | CP-SAT is CPU-bound; solves must not block the event loop |
| Database | **PostgreSQL** + **Alembic** migrations | Single schema source (`apps/api/alembic/`) |
| Frontend | **Next.js 14** (App Router) + Tailwind | Streaming chat UI, schedule grid, spec confirmation cards |
| Exports | **openpyxl** (xlsx) + **ReportLab** (PDF, embedded DejaVu for Cyrillic) | Reproduce the client-approved printable layout |
| Monorepo | Turborepo + pnpm | `apps/web` (Next.js) + `apps/api` (FastAPI) |
| CI | GitHub Actions | pytest suite + Next build on every push/PR |

---

## 2. Architecture

```
Manager (web chat, BG/EN)              Employee (Telegram)
        │  SSE streaming                      │  webhook
        ▼                                     ▼
┌─ AI Copilot ─────────────┐        ┌─ Parser (Haiku) ────────┐
│ Gemini / Claude           │        │ free text → Preference  │
│ tools: get_spec,          │        └───────────┬─────────────┘
│  apply_spec_update,       │                    │ manager approves
│  generate_schedule,       │                    ▼
│  get_verification_report  │        OffRequest rule in the spec
└───────────┬───────────────┘
            ▼
   ScheduleSpec  (versioned JSON rulebook, Pydantic-validated)
            │
            ▼
   CP-SAT Engine v2  (worker process, zero AI tokens)
   solve strict → if INFEASIBLE: relax tagged rules tier by tier → re-solve
            │
            ▼
   Verifier (independent re-check of every rule)
            │ violated auto-repair rule? → escalate to hard → re-solve (≤3×)
            ▼
   Schedule + rule-by-rule findings (BG/EN)
            │
            ▼
   DB → grid UI  /  Excel  /  printable PDF
```

### Why this shape

Research (and the client's own experience asking ChatGPT for schedules) shows LLMs produce plausible-but-wrong schedules and constraints. ShiftFlow removes that failure mode structurally:

1. **The AI can only emit rules** in a fixed, validated vocabulary (`ScheduleSpec`). A hallucinated field fails Pydantic validation loudly — it can never reach the solver.
2. **The manager confirms the interpretation** (rules + explicit assumptions) before anything runs.
3. **The verifier is independent of the solver** — pure Python re-checks every rule against the output grid, so even a solver bug cannot produce a silently wrong schedule.

### Token economy

| Mechanism | Effect |
|---|---|
| AI writes rules, never schedules | Solve/verify/repair loops cost $0; regenerate as often as you like |
| Model tiering | Flash/Opus only for manager briefs & chat (low frequency); Haiku for employee messages |
| Structured outputs | Schema-constrained JSON → no malformed-reply retry loops |
| The model never reads the grid | Chat answers come from precomputed compact summaries (per-staff stats, findings), not 112 schedule cells |
| Briefs parsed as diffs | Follow-up briefs return only what changed; the cumulative rulebook is never re-derived |

Typical cost per tenant/month on the paid path: **$1–3**. On the Gemini free tier (pilot): **$0**.

---

## 3. The rulebook: `ScheduleSpec`

`apps/api/packages/scheduler/spec.py` — the contract between AI and solver. A spec holds the venue, horizon, staff, **shift catalog** (each shift: start/end minutes, `preferred` vs fallback, colors, allowed weekdays) and a list of **rules**.

### Rule types

| Type | Expresses | Real-brief example |
|---|---|---|
| `weekly_quota` | Exact per-week shift counts per duration + rest days | "всяка седмица: 2×8ч + 2×10ч + 3×12ч, без почивен ден" |
| `day_shift_restriction` | Only certain shifts allowed on matching days | "петък/събота/неделя всички работят само 12-часови смени" |
| `coverage` | Min/max staff **present during a time window** (hour-of-day granularity) | "никой не затваря сам" → min 2 in 22:00–00:00; "двама затварят в 00:00 през уикенда" → min 2 max 2 |
| `start_spread` | Max N staff starting within a time window per day | "не допускай всички да бъдат първа смяна" |
| `sequence` (forbid) | Consecutive-day pattern to avoid | "16:00–00:00 → на следващия ден 08:00–16:00: максимално да се избягва" |
| `sequence` (require) | Pattern that must occur per staff/week | "всеки да получи 08–16 → 16–00 веднъж; С1=Джедая, С2=Васил…" |
| `fairness` | Matching shifts spread evenly across staff | "късните смени да се разпределят равномерно" |
| `off_request` | Approved day off for one person | Employee Telegram request, after manager approval |

### Enforcement semantics (per rule)

- `enforcement: "hard"` — must hold ("задължително", "никога")
- `enforcement: "soft"` + `weight` — minimized, violations counted ("максимално да се избягва")
- `relaxable: true` — a hard rule the **infeasibility ladder** may demote to a penalty when the model is infeasible ("ако е математически невъзможно — възможно най-близко"); relaxed rules are *reported*, never silently dropped
- `auto_repair: true` — post-generation audit rule ("провери и преработи, докато бъде спазено"): if violated, the orchestrator escalates it to hard and re-solves (bounded at 3 iterations)

### Versioning & merging

Specs are **cumulative and versioned**. A follow-up brief is parsed as a **diff** (`SpecUpdateDraft`: add/replace/remove shifts and rules) applied by `apply_update()` with a version bump — prior rules persist unless explicitly changed. This mirrors how real clients iterate ("запази всички вече зададени ограничения, но добави…"). Every version is stored (`schedule_specs` table) for a full audit trail.

---

## 4. Solver, verifier, orchestrator

**Engine v2** (`packages/scheduler/engine.py`) is a **rule-handler registry**: each rule type has one handler that adds CP-SAT constraints (hard) or penalty terms (soft). Structural facts built in: exactly one assignment (shift or the reserved `OFF` pseudo-shift) per staff-day; shift-level weekday restrictions; a small penalty on non-preferred shifts. Objective: weighted sum of all penalties (relaxed-rule violations weigh 10× soft rules).

**Infeasibility ladder** (`solve_with_relaxation`): solve strict → if INFEASIBLE, demote relaxable hard rules (lowest `relax_priority` first, cumulatively) → re-solve. The result always names which rules were relaxed and how many violations remain.

**Verifier** (`packages/scheduler/verifier.py`): a second, solver-independent implementation of every rule check. Produces `Finding`s: rule id, status (`ok` / `violated` / `relaxed`), violation count, offending cells (`staff@date`), message in Bulgarian and English.

**Orchestrator** (`packages/scheduler/orchestrator.py`): solve → verify → escalate violated `auto_repair` soft rules to hard-but-relaxable → re-solve. Result: `GenerateReport` — assignments + findings + which rules were escalated/relaxed.

**Adding a client-specific constraint type** = one new rule class in `spec.py` + one engine handler + one verifier mirror + tests. Core engine, copilot and UI stay untouched, and the new rule becomes available to every tenant.

---

## 5. The AI copilot

`apps/api/app/services/copilot.py` (provider dispatch) + `gemini_llm.py` (Gemini implementation).

### Providers

| `LLM_PROVIDER` | Model | Use |
|---|---|---|
| `gemini` (default) | `GEMINI_MODEL` env, default `gemini-3.5-flash` | Free-tier pilot (~10 req/min, 1,500/day). Upgrade path: `gemini-3.1-pro-preview` (paid) — env change only |
| `anthropic` | `claude-opus-4-8` | Production quality; needs a funded `ANTHROPIC_API_KEY` |

Both implement identical contracts; switching providers changes nothing else in the system.

### Two AI boundaries

1. **Brief → rules** (`parse_brief`, `parse_brief_update`). One structured-outputs call constrained to the `SpecDraft` / `SpecUpdateDraft` schema (times as `"HH:MM"` strings — LLMs are reliable with clock times, not minute arithmetic; `"00:00"` as an end time means midnight). The draft is converted and re-validated deterministically. The model must also list its **assumptions**, which the UI shows for confirmation.
2. **Conversational copilot** (`CopilotSession`). A streaming tool-use loop with four tools:
   - `get_spec` — read the current rulebook (compact JSON overview)
   - `apply_spec_update` — apply a confirmed diff (validated; bad input returns an error *into* the loop, not a crash)
   - `generate_schedule` — run the full solve→verify→repair pipeline (seconds, $0)
   - `get_verification_report` — re-read the last report

   The model answers questions like *"защо Афродита затваря 3 уикенда?"* from precomputed per-staff stats — it is never shown the raw grid, and it may not claim a rule holds unless the verification summary says so.

### Employee channel

Telegram webhook (`app/routers/bots.py`): staff link their account with a 6-digit OTP (issued only to the authenticated user), then send free-text requests ("Не мога в събота 18 юли"). Claude Haiku parses them into structured `Preference` rows; the manager approves; approved off-requests become `off_request` rules in the spec.

---

## 6. API reference

Base: `https://shiftflow-api.digitalnebula.net` — interactive docs at `/docs`. Auth: JWT bearer (`/api/auth/register`, `/login`, `/refresh`); manager role required for copilot routes. Multi-tenant: every query is scoped by the JWT's tenant.

| Endpoint | Purpose |
|---|---|
| `POST /api/copilot/specs/parse` | Brief → interpreted DRAFT spec (+ summary + assumptions) |
| `POST /api/copilot/specs/{id}/confirm` | Manager approves interpretation → ACTIVE |
| `POST /api/copilot/specs/{id}/update` | Follow-up brief → diff → new DRAFT version |
| `GET  /api/copilot/specs/{id}` | Read spec (overview + full JSON) |
| `POST /api/copilot/specs/{id}/generate` | Solve + verify; returns run id, summary, assignments |
| `GET  /api/copilot/runs/{id}` | Full report of a run (findings, assignments) |
| `GET  /api/copilot/runs/{id}/export.xlsx` / `.pdf` | Deliverables |
| `POST /api/copilot/chat` | One chat turn, streamed as SSE events (`text`, `tool`, `spec_updated`, `report`, `done`) |
| `POST /api/bots/telegram/otp` | OTP for the authenticated user to link Telegram |
| `POST /api/bots/telegram/webhook` | Telegram updates (secret-token verified) |
| `/api/auth /staff /venues /shift-types /schedules /preferences /export /analytics` | Legacy CRUD from v0.1 (still served) |

### Key tables

`tenants`, `users` (roles OWNER/MANAGER/STAFF), `staff_profiles`, `schedule_specs` (**versioned rulebooks** — spec JSON + source brief + AI summary), `schedule_runs` (**solver executions** — full `GenerateReport` JSON), `preferences` (employee requests), plus legacy `venues`, `shift_types`, `schedules`, `shift_assignments`, `audit_logs`.

---

## 7. Using the system (manager walkthrough)

1. **Sign in** → *AI Copilot* in the sidebar.
2. **Paste the brief** — plain language, Bulgarian or English, as detailed as you like. Set the start date and number of days. Click **Интерпретирай заданието**.
3. **Review the interpreted rules card**: every rule shows an enforcement badge — **задължително** (hard) / **max. близко** (hard-but-relaxable) / **желателно** (soft) / **авто-поправка** (auto-repair) — and the AI lists its **assumptions** in an amber box. *Read the assumptions.* If something is off, write a follow-up brief; it merges as a diff.
4. **Потвърди правилата** → **Генерирай график**. Solving takes seconds.
5. **Read the verification panel**: green `OK` per rule = proven. **невъзможно — минимизирано** = the rule was mathematically impossible in full; the count shows how often it had to be violated (this is the honest "as close as possible" the brief asked for). Red = violated soft rule.
6. **Export** — Excel (week blocks, duration colors, legend, per-week quota columns, a "Проверка" sheet) or printable A4 PDF with the verification report.
7. **Iterate in chat** — ask why, request changes ("добави правило: никой не работи повече от 5 поредни дни"), regenerate. Every change creates a new spec version.
8. **Employee requests** arrive in *Preferences*; approving one injects it into the spec for the next generation.

---

## 8. Local development

```bash
# Backend
cd apps/api
pip install -r requirements.txt
cp .env.example .env             # set SECRET_KEY, DATABASE_URL, GEMINI_API_KEY
alembic upgrade head
python -m uvicorn app.main:app --port 8010

# Frontend
cd apps/web
pnpm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8010" > .env.local
pnpm dev                          # Next picks the first free port — check the output

# Tests (32 = unit + golden briefs + property-based + renderers)
cd apps/api && python -m pytest tests/ -q
```

Gotchas on the dev machine: ports 3000 (Open WebUI), 8000 (TBS CRM) and 5432 (shared Postgres container) are taken — hence 3001/8010. `NEXT_PUBLIC_*` vars are baked at compile time: after changing `.env.local`, restart `pnpm dev` (and `rm -rf .next` if in doubt). CORS origins live in `apps/api/.env` (`CORS_ORIGINS` JSON list).

### Testing philosophy

- **Golden acceptance tests** (`tests/test_golden_briefs.py`): both real client briefs expressed as specs; every requirement asserted, including that the two failure examples from the original hand-delivered schedule (a lone closer; everyone on first shift) are impossible.
- **Property-based tests** (`tests/test_property.py`): random rulebooks → the pipeline must never crash, and solver and verifier must agree on every hard rule.
- **Pipeline tests**: impossible specs return explicit relaxation reports (never crash); auto-repair escalation; off-request → OFF day with elastic quota.
- **Renderer tests**: xlsx layout parity, Cyrillic PDF.

---

## 9. Deployment

### Current pilot topology ($0/month)

```
Vercel (frontend, auto-deploy from main)
   └─→ https://shiftflow-api.digitalnebula.net
         = named Cloudflare tunnel → uvicorn :8010 on the dev machine
              └─→ Postgres (docker, db "shiftflow")
```

- `scripts/serve-prod.sh` + user cron (`@reboot`, every 5 min) keeps API, tunnel and DB container alive.
- **Limitation:** the backend lives on the dev machine — if it's off, the live site's API is down. Acceptable for internal testing only.

### Production path (when the pilot converts)

1. **Neon** Postgres (free tier) — `alembic upgrade head` against it.
2. **Render/Railway** for the API (the frontend env previously pointed at `shiftflow-api.onrender.com` — deploying under that name would also work). Set `SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, `LLM_PROVIDER`, `CORS_ORIGINS`.
3. Flip `NEXT_PUBLIC_API_URL` on Vercel **via the REST API only** (the dashboard has corrupted env values before) and redeploy.

---

## 10. Security notes

- JWT auth (15-min access / 7-day refresh), bcrypt password hashes, per-tenant row scoping on every query.
- Telegram OTP is issued only to the authenticated user (JWT-derived identity — an earlier version accepted an arbitrary `user_id`, fixed in `15c751e`).
- Webhook verified via `X-Telegram-Bot-Api-Secret-Token`.
- Secrets live in env files (gitignored) / platform env stores; never in the repo.
- AI safety: model output is schema-validated, human-confirmed, and independently verified — the AI has no write path to a schedule.

## 11. Roadmap (not yet built)

WhatsApp/Viber channels · demand forecasting · payroll/labor-code compliance packs · shift-swap marketplace · Stripe billing activation (schema ready) · mobile app · per-tenant export branding.
