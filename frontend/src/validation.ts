/**
 * Client-side validation that MIRRORS the server rules in
 * backend/app/routes/schemas.py (ComplaintCreate) — it gives instant feedback,
 * it does not replace them. The server re-validates everything and its 400
 * field errors are shown the same way as these.
 */
export const LIMITS = {
  text: { min: 10, max: 2000 },
  location: { min: 3, max: 200 },
  contact: { max: 200 },
} as const;

export interface ComplaintForm {
  text: string;
  location: string;
  reporter_contact: string;
}

export type FormErrors = Partial<Record<keyof ComplaintForm, string>>;

export function validateComplaint(form: ComplaintForm): FormErrors {
  const errors: FormErrors = {};
  const text = form.text.trim();
  const location = form.location.trim();
  const contact = form.reporter_contact.trim();

  if (text.length < LIMITS.text.min) {
    errors.text = `Please describe the problem in at least ${LIMITS.text.min} characters.`;
  } else if (text.length > LIMITS.text.max) {
    errors.text = `Please keep the description under ${LIMITS.text.max} characters.`;
  }
  if (location.length < LIMITS.location.min) {
    errors.location = `Location must be at least ${LIMITS.location.min} characters.`;
  } else if (location.length > LIMITS.location.max) {
    errors.location = `Location must be at most ${LIMITS.location.max} characters.`;
  }
  if (contact.length > LIMITS.contact.max) {
    errors.reporter_contact = `Contact must be at most ${LIMITS.contact.max} characters.`;
  }
  return errors;
}
