# Engineering Notes

Answers to the 8 questions in §5.2 of the assignment. Generic answers score
zero — every answer below must be replaced with your own reasoning AND a
reference to your own file(s) and line(s), not a restatement of the spec.

## 1. Three things that differ between your laptop and a CI runner

TODO(you): Name three concrete differences (e.g. no pre-pulled Ollama model,
no populated Redis/Postgres state, different CPU/memory ceiling) and, for
each, point to the exact line in a Dockerfile or manifest that freezes it
against that difference (e.g. `backend/Dockerfile:L<N>`'s HEALTHCHECK,
`.github/workflows/ci.yml`'s `TRIAGE_PROVIDER: simulated` env line).

## 2. Where your pipeline sits on the CI/CD maturity ladder

TODO(you): Reference Lecture 03 slide 32's ladder by name/rung. Justify which
rung `ci.yml` + `cd.yml` actually reach (e.g. "continuous delivery, not
continuous deployment" if there's still a manual gate somewhere — or the
reverse if there genuinely isn't). Name the next rung and what it would buy you.

## 3. The exact line guaranteeing build-once-deploy-many

TODO(you): Point to the specific line(s) — likely in `frontend/src/config.ts`
or `frontend/nginx.conf` (whichever option you implemented, per ADR 0002) —
and explain what breaks without it (an environment-specific frontend image).

## 4. What does "correct" mean for a probabilistic component, and how did you keep CI deterministic?

TODO(you): Reference Lecture 01 slide 34. Explain your answer in terms of
`backend/app/providers/triage/simulated.py` and the
`TRIAGE_PROVIDER=simulated` pin in CI — "correct" for `LLMTriage` can't mean
byte-identical output every run, so what does your test suite actually assert
instead?

## 5. Your HPA lag

TODO(you): Report an actual number of seconds between offered load rising
(from your k6/hey run) and replicas rising (from your `kubectl get hpa -w`
capture). Where did the time go (metrics-server scrape interval? HPA's own
sync period? pod startup + readiness probe time?) and what would reduce it?

## 6. Why VPA is in Off mode

TODO(you): Describe the HPA/VPA conflict in your own words (both raise/lower
CPU signals that feed back into each other) — see the comment already in
`k8s/base/vpa.yaml` for the mechanism, but write your own explanation here,
not a copy of it.

## 7. Where does your `internal: true` network leave the LLM-calling service?

TODO(you): Reference `compose.yaml`'s network definitions. `backend` sits on
both `edge` and `internal` — explain concretely why that placement resolves
the problem (backend needs outbound internet for Groq/Gemini, but
database/cache must not be reachable from outside).

## 8. The failure that cost you more than an hour

TODO(you): This one can't be templated — write the real story. Symptoms, what
you wrongly believed first, and the exact command or log line that finally
told you the truth. This question is explicitly designed to catch a
templated/AI-generated answer; don't submit one.
