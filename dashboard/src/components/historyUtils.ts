import type { LedgerEvent, PromiseGroups } from "../types";

export function flattenPromiseGroups(groups: PromiseGroups): LedgerEvent[] {
  return Object.values(groups).flat();
}

export function fieldText(event: LedgerEvent, field: string, fallback = "n/a"): string {
  const value = event[field];
  if (value === undefined || value === null) {
    return fallback;
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function eventTimestamp(event: LedgerEvent): string {
  return fieldText(event, "timestamp", "no timestamp");
}

export function latestByGroup(groups: PromiseGroups): LedgerEvent[] {
  return Object.values(groups)
    .map((events) => events[events.length - 1])
    .filter((event): event is LedgerEvent => event !== undefined);
}
