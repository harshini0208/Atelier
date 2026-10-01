/** Single-series horizontal bars (magnitude). One sequential hue, values in ink, native tooltip per bar,
 *  and a visually-hidden table so the numbers are readable without the chart. */
export type Bar = { label: string; value: number; note?: string };

export default function Bars({ data, unit, caption }: { data: Bar[]; unit: string; caption: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure style={{ margin: 0 }}>
      <div className="bars" aria-hidden>
        {data.map((d) => (
          <div key={d.label} className="bar-row" title={`${d.label}: ${d.value.toLocaleString("en-IN")} ${unit}${d.note ? ` (${d.note})` : ""}`}>
            <span className="bar-label">{d.label}</span>
            <span className="bar-track"><span className="bar-fill" style={{ width: `${(d.value / max) * 100}%` }} /></span>
            <span className="bar-value">{d.value.toLocaleString("en-IN")}</span>
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead><tr><th>Item</th><th>{unit}</th></tr></thead>
        <tbody>{data.map((d) => <tr key={d.label}><td>{d.label}</td><td>{d.value}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
