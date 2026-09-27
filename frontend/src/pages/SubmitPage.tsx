import { useState, type FormEvent } from "react";
import { api, ApiError, RateLimitedError } from "../api/client";
import type { ComplaintOut } from "../api/types";

/**
 * Submit view (§2.1). Required behavior:
 *   - Free-text complaint, location, optional contact
 *   - Client-side validation that MIRRORS server rules without REPLACING them
 *     (i.e. still handle the server's 400 response; don't assume client-side
 *     checks are sufficient)
 *   - Show the returned category, priority, AI summary, and which provider produced it
 *   - Render the loading state honestly — "AI calls take seconds"
 */
export function SubmitPage() {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [reporterContact, setReporterContact] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ComplaintOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  // TODO(you): mirror the backend's constraints for inline hints, e.g.:
  // const textTooShort = text.length > 0 && text.length < 10;
  // const textTooLong = text.length > 2000;
  // Show these as hints, but do NOT block submission solely on client-side
  // checks — still handle server 400s (the source of truth).

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      // TODO(you): call api.createComplaint({ text, location, reporter_contact: reporterContact || null })
      // and setResult(response) on success.
      throw new Error("not implemented");
    } catch (err) {
      if (err instanceof RateLimitedError) {
        // TODO(you): show a specific "you're submitting too fast, retry in Ns" message
        setError(`Rate limited. Try again in ${err.retryAfterSeconds ?? "a few"} seconds.`);
      } else if (err instanceof ApiError) {
        // TODO(you): if err.status === 400, render the field-level errors from err.body
        setError("Could not submit complaint. Please check your input.");
      } else {
        setError("Unexpected error. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>Report a Complaint</h1>
      <form onSubmit={handleSubmit}>
        {/* TODO(you): wire these inputs' value/onChange to the state above */}
        <label>
          Complaint
          <textarea value={text} onChange={(e) => setText(e.target.value)} required />
        </label>
        <label>
          Location
          <input value={location} onChange={(e) => setLocation(e.target.value)} required />
        </label>
        <label>
          Contact (optional)
          <input value={reporterContact} onChange={(e) => setReporterContact(e.target.value)} />
        </label>

        {/* Honest loading state, per §2.1 — AI calls take seconds, so this must
            not be a flash-of-nothing spinner. TODO(you): style/word this clearly. */}
        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting — AI triage can take a few seconds…" : "Submit Complaint"}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {result && (
        <div>
          {/* TODO(you): render category, priority, ai_summary, and triaged_by
              (the "which provider produced it" requirement) here. */}
          <p>Category: {result.category}</p>
          <p>Priority: {result.priority}</p>
          <p>Summary: {result.ai_summary}</p>
          <p>Triaged by: {result.triaged_by}</p>
        </div>
      )}
    </div>
  );
}
