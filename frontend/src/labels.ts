/**
 * Presentation vocabulary: display labels and option lists.
 *
 * These are NOT business rules. Which transitions are valid, and what category
 * or priority a complaint gets, is decided by the server. The `satisfies`
 * clauses tie every list to the generated schema types, so if the backend adds
 * or renames an enum value, `tsc` fails until this file is updated.
 */
import type { Category, Priority, Status, TriagedBy } from "./api/client";

export const CATEGORIES = [
  "water",
  "electricity",
  "sanitation",
  "roads",
  "streetlights",
  "other",
] as const satisfies readonly Category[];

export const PRIORITIES = ["high", "normal", "low"] as const satisfies readonly Priority[];

export const STATUSES = [
  "open",
  "in_progress",
  "resolved",
  "rejected",
] as const satisfies readonly Status[];

export const CATEGORY_LABEL: Record<Category, string> = {
  water: "Water",
  electricity: "Electricity",
  sanitation: "Sanitation",
  roads: "Roads",
  streetlights: "Streetlights",
  other: "Other",
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  high: "High",
  normal: "Normal",
  low: "Low",
};

export const STATUS_LABEL: Record<Status, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  rejected: "Rejected",
};

/** Verb shown on a button that moves a complaint *to* this status. */
export const STATUS_ACTION: Record<Status, string> = {
  open: "Reopen",
  in_progress: "Start work",
  resolved: "Mark resolved",
  rejected: "Reject",
};

export const PROVIDER_LABEL: Record<TriagedBy, string> = {
  "llm:gemini": "Gemini (hosted LLM)",
  "llm:groq": "Groq (hosted LLM)",
  "llm:ollama": "Ollama (local LLM)",
  rules: "Keyword rules",
  "rules:fallback": "Keyword rules (fallback)",
  simulated: "Simulated (CI)",
};

export function providerLabel(value: string): string {
  return (PROVIDER_LABEL as Record<string, string>)[value] ?? value;
}
