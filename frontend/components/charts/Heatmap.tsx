// Correlation matrix as an accessible table with a diverging color scale.
// null cells (undefined correlation, e.g. a constant series) are shown as "—".

function cellColor(value: number | null): string {
  if (value === null) return 'transparent';
  const v = Math.max(-1, Math.min(1, value));
  const token = v >= 0 ? '--info' : '--down';
  return `rgb(var(${token}) / ${(Math.abs(v) * 0.75).toFixed(3)})`;
}

export default function Heatmap({ labels, matrix }: { labels: string[]; matrix: (number | null)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="num border-separate border-spacing-0.5 text-2xs" aria-label="Correlation of daily returns">
        <thead>
          <tr>
            <th className="sticky left-0 bg-panel" />
            {labels.map((label) => (
              <th key={label} scope="col" className="px-1.5 py-1 font-semibold text-ink-muted">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <th scope="row" className="sticky left-0 bg-panel pr-2 text-left font-semibold text-ink-muted">
                {labels[i]}
              </th>
              {row.map((value, j) => (
                <td
                  key={`${i}-${j}`}
                  className="min-w-[3.25rem] rounded-sm px-1.5 py-1.5 text-center text-ink"
                  style={{ background: cellColor(value) }}
                  title={`${labels[i]} vs ${labels[j]}: ${value === null ? 'undefined' : value.toFixed(3)}`}
                >
                  {value === null ? '—' : value.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 flex items-center gap-2 text-2xs text-ink-faint">
        <span className="inline-block h-2 w-6 rounded-sm" style={{ background: 'linear-gradient(90deg, rgb(var(--down) / .75), transparent, rgb(var(--info) / .75))' }} />
        −1 to +1, Pearson correlation of daily returns
      </p>
    </div>
  );
}
