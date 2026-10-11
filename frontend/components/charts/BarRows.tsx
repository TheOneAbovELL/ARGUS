// Horizontal comparison bars (allocation, risk contribution). Values are
// fractions; bars scale to the largest absolute value in the set.

export interface BarRow {
  label: string;
  values: { key: string; value: number | null; color: string }[];
}

export default function BarRows({
  rows,
  legend,
  format = (v) => `${(v * 100).toFixed(1)}%`,
}: {
  rows: BarRow[];
  legend: { key: string; label: string; color: string }[];
  format?: (value: number) => string;
}) {
  const max = Math.max(1e-9, ...rows.flatMap((r) => r.values.map((v) => Math.abs(v.value ?? 0))));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3 text-2xs text-ink-muted">
        {legend.map((item) => (
          <span key={item.key} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm" style={{ background: `rgb(var(--${item.color}))` }} aria-hidden />
            {item.label}
          </span>
        ))}
      </div>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.label} className="grid grid-cols-[7rem_1fr] items-center gap-2">
            <span className="num truncate text-xs font-semibold text-ink">{row.label}</span>
            <div className="space-y-0.5">
              {row.values.map((v) => (
                <div key={v.key} className="flex items-center gap-2">
                  <div className="h-2 flex-1 rounded-sm bg-raised">
                    {v.value !== null && (
                      <div
                        className="h-2 rounded-sm"
                        style={{ width: `${(Math.abs(v.value) / max) * 100}%`, background: `rgb(var(--${v.color}))`, opacity: v.value < 0 ? 0.5 : 1 }}
                      />
                    )}
                  </div>
                  <span className="num w-14 text-right text-2xs text-ink-muted">{v.value === null ? '—' : format(v.value)}</span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
