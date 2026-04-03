---
title: "Cloudflare Workers Subrequest Limit — Post-mortem"
date: 2026-04-03T00:00:00+07:00
draft: false
---

## TL;DR

Deploying a Jira time-report API on Cloudflare Pages (Workers edge runtime) caused **silent data loss** for 25 out of 57 issues. The root cause was Cloudflare Workers' **50-subrequest-per-invocation limit** on the free tier. Fixed by embedding worklogs in the JQL search response instead of making separate API calls per issue.

---

## The Problem

When selecting all 9 Jira boards on the time report page, team member "Ngọc Định Nguyễn" showed **8h** instead of the correct **30.5h**. Selecting only boards 36+37 showed the correct value.

## Investigation Timeline

### Attempt 1: Sequential board processing (failed)

**Hypothesis:** The combined JQL query across all boards was silently dropping some projects.

**Fix tried:** Query each board independently in a `for` loop, merge results.

**Result:** Same data loss. The issue wasn't in the JQL query — all 57 issues were found correctly.

### Attempt 2: Deduplication bug (failed)

**Hypothesis:** A `processedIssueKeys` Set was marking issues as "done" even when their worklog fetch failed. Later boards seeing the same issue would skip it.

**Fix tried:** Remove cross-board deduplication, deduplicate worklogs by ID in the aggregation step instead.

**Result:** Fixed a real bug, but data still lost on Cloudflare. Worked perfectly locally.

### Attempt 3: Rate limiting / batch size (failed)

**Hypothesis:** Jira API rate limit (429) causing worklog fetches to silently return `[]`.

**Fix tried:**
- Reduce batch size from 10 → 3, increase delay 100ms → 400ms
- Add 3-attempt retry with exponential backoff for 429/5xx

**Result:** Still failed on Cloudflare. Worked locally. The `setTimeout` delays were eating into Cloudflare's CPU time budget.

### Attempt 4: Full parallel, no sleep (failed)

**Hypothesis:** `setTimeout` is unreliable on Cloudflare Workers edge runtime.

**Fix tried:** Fire all 57 worklog requests in parallel with `Promise.all`, no delays.

**Result:** Same data loss on Cloudflare (42/79 worklogs). Locally: 2.5s, all data correct.

### Attempt 5: Concurrency limiter (failed)

**Hypothesis:** 57 concurrent requests overwhelming something.

**Fix tried:** Semaphore pattern — process in chunks of 5-8, no `setTimeout`.

**Result:** Same. At this point, added debug logging to surface the actual error.

### Breakthrough: Error surfacing

Added sentinel objects to track which issues failed and **why**:

```
STATUS: Failed 25 issues (sample error: status=none msg=Too many subrequests 
by single Worker invocation. To configure this limit, refer to 
https://developers.cloudflare.com/workers/wrangler/configuration/#limits)
```

**The error was not a Jira rate limit.** It was a **Cloudflare platform limit**.

### Attempt 6: wrangler.toml `[limits]` (failed)

**Fix tried:** Add `[limits] subrequests = 1000` to `wrangler.toml`.

**Result:** This setting requires a paid Workers plan and **doesn't apply to Pages** on the free tier.

### Attempt 7: Embed worklogs in JQL response (SUCCESS)

**Insight:** Instead of making 57 separate `/issue/{key}/worklog` API calls, request the `worklog` field directly in the JQL search. Jira embeds worklogs in each issue's response.

**Fix:** Add `'worklog'` to the JQL `fields` array, then extract worklogs from `issue.fields.worklog.worklogs[]`. Only fall back to the dedicated worklog endpoint when Jira truncates (total > returned count).

**Subrequest count:** 9 board JQL calls + ~0-5 fallback calls = **~9-14 total** (well under 50 limit).

**Result:** All data correct on Cloudflare. Ngọc Định = 30.5h ✓.

---

## Key Lessons

### 1. Cloudflare Workers has a hard 50-subrequest limit (free tier)

Every `fetch()` call from your Worker counts as a subrequest. This includes:
- API calls to external services (Jira, GitHub, etc.)
- Even failed/retried requests count

The limit is **per invocation**, not per second. You can't work around it with batching or delays.

**Paid plan:** 1000 subrequests (configurable via `wrangler.toml`).

### 2. The error is silent by default

When you hit the limit, subsequent `fetch()` calls throw a generic error with `status=none`. There's no special HTTP status code or header — it looks like a network failure. If your code catches errors and returns `[]`, the data loss is completely invisible.

### 3. setTimeout is problematic on edge runtime

Cloudflare Workers count `setTimeout` delays toward CPU time limits. A pattern like "batch of 5 + 400ms delay" that works locally can cause different failures on the edge (timeouts, unexpected behavior).

### 4. Embed data in search queries when possible

Instead of:
```
1 search query → N results → N individual detail queries
```

Use:
```
1 search query with extra fields → N results with details embedded
```

Most APIs (Jira, GitHub, etc.) support requesting additional fields in search/list endpoints. This is always preferable on platforms with subrequest limits.

### 5. Local testing doesn't catch platform limits

The code worked perfectly locally (Node.js has no subrequest limit). Always test on the actual deployment platform, especially for:
- Subrequest/fetch limits
- CPU time limits
- Memory limits
- Response size limits

### 6. Debug logging should surface errors, not hide them

The original code:
```typescript
catch (error) {
  return []; // silently swallow
}
```

Should have been:
```typescript
catch (error) {
  sendStatus(controller, `Failed: ${error.message}`);
  return [];
}
```

Surface errors in the response stream so the UI can show them.

---

## Architecture Before vs After

### Before (66 subrequests)
```
Board 1 → JQL search → issue list     ─┐
Board 2 → JQL search → issue list      │  9 requests
...                                     │
Board 9 → JQL search → issue list     ─┘

Issue 1 → GET /worklog                 ─┐
Issue 2 → GET /worklog                  │  57 requests
...                                     │
Issue 57 → GET /worklog                ─┘

Total: 66 subrequests ❌ (exceeds 50 limit)
```

### After (9 subrequests)
```
Board 1 → JQL search (with worklog field) → issues + worklogs  ─┐
Board 2 → JQL search (with worklog field) → issues + worklogs   │  9 requests
...                                                              │
Board 9 → JQL search (with worklog field) → issues + worklogs  ─┘

Extract worklogs from issue.fields.worklog (no API call needed)
Fallback: only if worklog.total > worklogs.length (rare)

Total: ~9 subrequests ✓
```

---

## Performance Comparison

| Metric | Sequential (v1) | Parallel+sleep (v2) | Embedded (final) |
|--------|-----------------|---------------------|-------------------|
| Subrequests | 66 | 66 | ~9 |
| Local time | 25s | 20s | 2.5s |
| Cloudflare | ❌ data loss | ❌ data loss | ✓ correct |
| Ngọc Định hours | 8h (wrong) | 8h (wrong) | 30.5h (correct) |

---

*Date: 2026-04-03 | Project: jira-report | Platform: Cloudflare Pages (Workers edge runtime)*
