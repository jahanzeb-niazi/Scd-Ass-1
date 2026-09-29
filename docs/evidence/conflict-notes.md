# Deliberate merge conflict: notes

**What conflicted.** Both of us changed the same line, the default of `rate_limit_requests` in
`backend/app/config.py`, on branches cut from the same `dev`: `feat/rate-limit-12` raised it to 12 requests per
minute, `feat/rate-limit-8` lowered it to 8 and rewrote its comment. `feat/rate-limit-8` merged first, so merging
`dev` into `feat/rate-limit-12` stopped with a content conflict on that line
(`merge-conflict-markers.png`).

**What won and why.** We kept **10 per minute**, neither branch's value. 10 is the value we chose when designing the
limiter and the one the README's API table documents. It sits below the free-tier requests-per-minute of our Gemini
project (the assignment's §2.4 puts free tiers "on the order of tens of requests per minute"), so one client cannot
exhaust the shared quota on its own. 12 would let two busy clients push us into provider 429s and fallbacks; 8
would reject legitimate bursts, such as several neighbours reporting the same water main, for no quota benefit that
10 does not already give.

**How we checked it.** After editing out the markers we ran the backend tests (`test_rate_limit_returns_429_with_retry_after`
in `backend/tests/test_api_complaints.py` checks the request past the limit is a 429 with `Retry-After`) and
checked by hand that the 11th POST within a minute returns 429, then committed the merge
(`merge-conflict-resolved.png` shows the graph).
