// Display formatting shared across screens.

export function fileName(path) {
  return path ? path.split(/[\\/]/).pop() : path;
}

/** Timestamps are stored UTC without a zone suffix; render them local. */
export function formatTimestamp(value) {
  if (!value) return "";
  const parsed = new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function percent(value) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(0)}%`;
}
