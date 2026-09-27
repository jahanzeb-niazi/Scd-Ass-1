import { useState, type FormEvent } from "react";
import { ApiError, submitComplaint, type ComplaintCreated } from "../api/client";
import { CategoryBadge, PriorityBadge, ProviderTag, StatusBadge } from "../components/Badges";
import { Spinner } from "../components/Spinner";
import { shortId } from "../format";
import { useElapsedSeconds } from "../hooks";
import { LIMITS, validateComplaint, type ComplaintForm, type FormErrors } from "../validation";

const EMPTY: ComplaintForm = { text: "", location: "", reporter_contact: "" };

export function SubmitPage() {
  const [form, setForm] = useState<ComplaintForm>(EMPTY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [result, setResult] = useState<ComplaintCreated | null>(null);
  const elapsed = useElapsedSeconds(submitting);

  function update<K extends keyof ComplaintForm>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setServerError(null);
    const clientErrors = validateComplaint(form);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      const created = await submitComplaint({
        text: form.text.trim(),
        location: form.location.trim(),
        reporter_contact: form.reporter_contact.trim() || null,
      });
      setResult(created);
      setForm(EMPTY);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400 && err.fieldErrors.length > 0) {
          const mapped: FormErrors = {};
          for (const fe of err.fieldErrors) {
            if (fe.field === "text" || fe.field === "location" || fe.field === "reporter_contact") {
              mapped[fe.field] = fe.message;
            }
          }
          setErrors(mapped);
        }
        // The server's own words: field problems, or "Try again in N s" on 429.
        setServerError(err.message);
      } else {
        setServerError("Something unexpected went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (result) return <TriageResultCard result={result} onReset={() => setResult(null)} />;

  const textLength = form.text.trim().length;

  return (
    <section className="page page--narrow">
      <header className="page__head">
        <p className="eyebrow">Citizen intake</p>
        <h1>Report a problem</h1>
        <p className="lede">
          Describe what is wrong in your own words — English, Urdu-English, however you speak. We read
          it, sort it and send it to the right team. You do not need to pick a category.
        </p>
      </header>

      <form className="panel form" onSubmit={onSubmit} noValidate aria-busy={submitting}>
        <div className={`field ${errors.text ? "field--invalid" : ""}`}>
          <label htmlFor="text">What is the problem?</label>
          <textarea
            id="text"
            name="text"
            rows={6}
            value={form.text}
            maxLength={LIMITS.text.max + 200}
            placeholder="e.g. Burst water main flooding Street 12 since fajr, water entering ground floors"
            onChange={(e) => update("text", e.target.value)}
            aria-invalid={Boolean(errors.text)}
            aria-describedby="text-help text-error"
            disabled={submitting}
          />
          <div className="field__meta">
            <span id="text-help" className="muted">
              Include what, since when, and whether anyone is at risk.
            </span>
            <span className={textLength > LIMITS.text.max ? "count count--over" : "count"}>
              {textLength}/{LIMITS.text.max}
            </span>
          </div>
          {errors.text && (
            <p id="text-error" className="field__error" role="alert">
              {errors.text}
            </p>
          )}
        </div>

        <div className={`field ${errors.location ? "field--invalid" : ""}`}>
          <label htmlFor="location">Where?</label>
          <input
            id="location"
            name="location"
            value={form.location}
            placeholder="Street, block, area — e.g. Street 12, Block 4, Gulshan-e-Iqbal"
            onChange={(e) => update("location", e.target.value)}
            aria-invalid={Boolean(errors.location)}
            aria-describedby="location-error"
            disabled={submitting}
          />
          {errors.location && (
            <p id="location-error" className="field__error" role="alert">
              {errors.location}
            </p>
          )}
        </div>

        <div className={`field ${errors.reporter_contact ? "field--invalid" : ""}`}>
          <label htmlFor="reporter_contact">
            Contact <span className="muted">(optional)</span>
          </label>
          <input
            id="reporter_contact"
            name="reporter_contact"
            value={form.reporter_contact}
            placeholder="Phone or email, if you want a follow-up"
            onChange={(e) => update("reporter_contact", e.target.value)}
            aria-invalid={Boolean(errors.reporter_contact)}
            aria-describedby="contact-help contact-error"
            disabled={submitting}
          />
          <span id="contact-help" className="muted small">
            Your contact is stored for the municipal team only. It is never sent to the AI service.
          </span>
          {errors.reporter_contact && (
            <p id="contact-error" className="field__error" role="alert">
              {errors.reporter_contact}
            </p>
          )}
        </div>

        {serverError && (
          <div className="notice notice--error" role="alert">
            {serverError}
          </div>
        )}

        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit complaint"}
          </button>
          {submitting && (
            <div className="triage-wait">
              <Spinner label={`Reading and triaging your complaint… ${elapsed}s`} />
              <p className="muted small">
                An AI model is classifying it. This usually takes a few seconds and can take up to
                about 20 if the service is busy — if it does not answer, a rule-based classifier takes
                over, so your complaint is never lost.
              </p>
            </div>
          )}
        </div>
      </form>
    </section>
  );
}

function TriageResultCard({ result, onReset }: { result: ComplaintCreated; onReset: () => void }) {
  return (
    <section className="page page--narrow">
      <header className="page__head">
        <p className="eyebrow">Received</p>
        <h1>Thank you — your complaint is logged</h1>
        <p className="lede">
          Reference <code className="ref">{shortId(result.id)}</code>. Here is how it was sorted.
        </p>
      </header>

      <article className="panel result" aria-label="Triage result">
        <dl className="result__grid">
          <div>
            <dt>Category</dt>
            <dd>
              <CategoryBadge value={result.category} />
            </dd>
          </div>
          <div>
            <dt>Priority</dt>
            <dd>
              <PriorityBadge value={result.priority} />
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <StatusBadge value={result.status} />
            </dd>
          </div>
        </dl>

        <div className="result__summary">
          <h2 className="label">AI summary</h2>
          <p>{result.ai_summary ?? "—"}</p>
        </div>

        <p className="result__provenance">
          Triaged by <ProviderTag value={result.triaged_by} /> in{" "}
          <strong>{result.triage_latency_ms} ms</strong>
          {result.triage.cache_hit && <span className="chip">duplicate — served from cache</span>}
        </p>

        {result.triage.fallback && (
          <p className="notice notice--warn">
            The AI classifier was unavailable for this one (busy, slow or unreachable), so a rule-based
            classifier sorted it instead. An operator will review it either way.
          </p>
        )}

        <details className="result__text">
          <summary>What you wrote</summary>
          <p>{result.text}</p>
          <p className="muted">{result.location}</p>
        </details>

        <div className="row">
          <button type="button" className="btn btn--primary" onClick={onReset}>
            Report another problem
          </button>
        </div>
      </article>
    </section>
  );
}
