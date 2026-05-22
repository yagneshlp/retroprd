# ADR Examples Reference

Architectural Decision Records (ADRs) capture *why* a technical decision was made, not just what
was decided. This is their entire value. A list of decisions without reasoning is nearly worthless.

Use these examples to calibrate the level of specificity and reasoning depth you should aim for.

---

## Good ADR examples

### ADR-001: Chose Supabase over Prisma + custom Postgres

**Date:** Approximate — early project (first 10 commits)
**Status:** Decided

**Context:**
The project needed a database with auth built in. The builder was a solo operator who needed to
move fast and didn't want to manage infrastructure. Two real options were evaluated.

**Decision:**
Use Supabase (hosted Postgres + auth + storage + realtime) rather than a self-managed Postgres
with Prisma as the ORM.

**Alternatives considered:**
- Prisma + Railway Postgres: more control over schema migrations, but requires managing auth
  separately (Clerk or Auth.js) and wiring up storage manually
- PlanetScale: MySQL-based, no native Postgres types, would require query changes later

**Consequences:**
- Auth is solved out of the box (Row Level Security, JWT integration)
- Migrations are done through Supabase dashboard rather than Prisma migrate — this is a tradeoff:
  easier now, harder to reproduce exactly in CI later
- Vendor lock-in is real but acceptable at this stage given the speed gain

---

### ADR-002: Used App Router (Next.js 13+), not Pages Router

**Date:** Project start
**Status:** Decided

**Context:**
New Next.js project. Pages Router is stable and well-documented. App Router is newer, more complex,
but aligns with React Server Components direction.

**Decision:**
Use App Router from the start.

**Alternatives considered:**
- Pages Router: more tutorials, more stable, easier mental model. Would have been lower-risk.

**Consequences:**
- Server Components reduce client-side JS significantly — important for LCP
- Layouts and nested routing are cleaner
- Some third-party libraries have rough App Router support (specifically: react-query setup is
  different, context providers need "use client" wrappers)
- Documentation online is thinner — debugging took longer than expected on 2-3 occasions

**(Reconstruction note: this decision is inferred from directory structure. No explicit discussion
found in transcripts. Builder should verify.)**

---

### ADR-003: Skipped test suite in Phase 1, introduced Vitest in Phase 2

**Date:** Phase 2 (approximately commit 45-50)
**Status:** Decided

**Context:**
Phase 1 was pure speed. No tests were written. By Phase 2, a bug in the payment flow was caught
only in production. Decision point: add tests now or keep moving.

**Decision:**
Add Vitest for unit tests on the payment and auth logic only. Do not try to add E2E tests yet.

**Alternatives considered:**
- Jest: more ecosystem, but Vitest is faster and natively supports ESM without config pain
- Playwright (E2E): would catch more bugs, but the setup cost was too high at this point
- Skip tests entirely: rejected after the production payment bug

**Consequences:**
- Critical paths now have test coverage
- E2E is still a gap — UI changes could break flows silently
- Vitest config is in `vitest.config.ts` — CI runs `vitest run` before deploy

---

## Common ADR mistakes to avoid

**Too thin:**
> "ADR-004: We use TypeScript."
> Context: TypeScript is better.
> Decision: TypeScript.

(This adds no value. Skip ADRs for decisions that have no meaningful alternative at this stage.)

**Missing consequences:**
> "ADR-005: Chose Redis for caching."
> Decision: Use Redis.

(This doesn't tell future agents anything. What does Redis being in the stack mean for
deployment? For local dev? For what gets cached? What's the eviction policy?)

**Reconstructing without flagging uncertainty:**
> "ADR-006: The builder decided to use edge functions because of latency concerns."

(If you don't have evidence for *why*, say so. "Reason inferred from deployment config — no
transcript record found.")

---

## ADR identification heuristics

When reading git history, these patterns suggest an ADR-worthy decision:

| Signal | Likely ADR |
|---|---|
| A major dependency added in a single commit | Library/framework choice |
| A large refactor commit with message like "switch to X" | Architecture pivot |
| A folder structure that doesn't follow obvious convention | Custom organization decision |
| Env variables for an external service | Third-party integration decision |
| A comment in the code like "// tried X, didn't work because..." | Technical constraint |
| Two similar files where one is clearly the "old" approach | Migration decision |
| A commit that removes a large amount of code | Deliberate simplification |
