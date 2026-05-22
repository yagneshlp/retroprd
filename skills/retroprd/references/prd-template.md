# PRD Template Reference

Use this template when the repo's AGENTS.md does not specify a PRD format, or when the
repo's format is underspecified.

---

## Default PRD format

```markdown
# PRD-NNN: [Title]

**Type:** feature | cr | bug | infra
**Status:** Shipped | In Progress | Draft
**Author:** [builder name or "Unknown — reconstructed"]
**Date:** YYYY-MM-DD
**Implemented by:** [Claude Code | Builder | Unknown]
**Reconstruction confidence:** High | Medium | Low
**Evidence sources:** git commits | code reading | transcript | inferred

---

## Summary

[1-2 sentences: what this change is and why it was done]

---

## Problem

[What was broken or missing before this change? Who was affected? What was the user
experience / developer experience before?]

---

## Change

[What was built? How does it work? What were the key implementation decisions?
Be specific — name the files, the patterns used, the data shapes.]

### Key decisions

- [Decision 1]: [Why this approach vs the alternative]
- [Decision 2]: [...]

### Files created or modified

| File | Change |
|---|---|
| `src/...` | Created — [purpose] |
| `src/...` | Modified — [what changed] |

---

## Root cause (bug PRDs only)

[What was the actual failure mode? What conditions triggered it?]

### Fix

[What was changed and why this fix is safe / doesn't regress other behavior]

---

## Testing notes

[How was this verified? Manual testing, automated tests added, edge cases checked?
If none — say "No automated tests added." This is honest and useful to future agents.]

---

## Known limitations / follow-up

[Anything deferred? Edge cases not handled? Things to come back to?]
```

---

## Type definitions

| Type | When to use |
|---|---|
| `feature` | Net new capability added to the product |
| `cr` | Change request — modification to an existing feature |
| `bug` | A defect fixed |
| `infra` | Infrastructure, tooling, deployment, configuration changes |

---

## Confidence calibration guide

| Level | What it means |
|---|---|
| **High** | Strong git commit messages + transcript evidence. The "Problem" and "Change" sections reflect documented reasoning, not inference. |
| **Medium** | Good code evidence. The "Change" section is accurate; the "Problem" section may be partially inferred from context. |
| **Low** | Mostly code reading. The whole PRD is inferred. Builder should verify and correct. |

---

## Common PRD anti-patterns to avoid

**Too vague:**
> "Improved the authentication system."

**Better:**
> "Added session expiry handling to the JWT middleware. Previously, expired tokens returned a 500;
> now they return a 401 with a `token_expired` error code and the client redirects to login."

---

**Padding where evidence is thin:**
> "This feature significantly improves the user experience by providing a more intuitive interface
> that aligns with modern design principles."

**Better:**
> "Added a modal confirmation step before deletion. No transcript evidence for the specific
> motivation — inferred from pattern of similar flows in the codebase."

---

**Missing the why:**
> "Added Stripe integration."

**Better:**
> "Added Stripe Checkout integration for one-time payments. Chose Checkout (hosted page) over
> custom payment form to avoid PCI scope complexity at this stage."
