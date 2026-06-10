interface JsonBlockProps {
  value: unknown;
}

export function JsonBlock({ value }: JsonBlockProps) {
  if (value === undefined || value === null) {
    return <span className="muted">No data</span>;
  }

  if (typeof value !== "object") {
    return <span>{String(value)}</span>;
  }

  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}
