import { useQuery } from "@tanstack/react-query";
import { api, pretty } from "../api";
import Bars from "../components/Bars";
import { ErrorBox, Icon, Loading } from "../components/ui";

type R = {
  funnel: { step: string; shoppers: number; events: number }[];
  gaps: { label: string; saves: number; saves_with_match: number; unmatched: number; variants: { color: string; fabric: string; saves: number }[] }[];
  top_attributes: Record<string, { label: string; saves: number }[]>;
  coverage: { looks: number; pieces_covered: number; pieces_covered_in_prefs: number; pieces: number; fully_covered_looks: number };
  memo: { headline: string; bullets: string[]; action: string }; memo_source: string; source: string; synthetic_note: string;
};

export default function Retailer() {
  const q = useQuery({ queryKey: ["retailer"], queryFn: () => api.get<R>("/retailer") });
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading label="Crunching the numbers" />;
  const r = q.data;
  const c = r.coverage;
  const f = Object.fromEntries(r.funnel.map((s) => [s.step, s.shoppers]));
  return (
    <>
      <span className="eyebrow">Retailer view · Urban Thread</span>
      <h1>What shoppers want, and what we're missing</h1>
      <p className="small muted">{r.source}. {r.synthetic_note}</p>

      <section className="card pad section stack" style={{ borderColor: "var(--sage)" }}>
        <div className="row" style={{ gap: 8 }}><Icon name="sparkle" /><span className="eyebrow">Merchandiser memo</span>
          <span className="chip">{r.memo_source === "fallback" ? "template" : "Gemini"}, from the numbers below</span></div>
        <h2>{r.memo.headline}</h2>
        <ul style={{ margin: 0, paddingLeft: 20 }}>{r.memo.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        <div className="alert alert-sage"><b>Suggested action:</b> {r.memo.action}</div>
      </section>

      <div className="stat-grid section">
        <div className="card stat"><span className="small muted">Shoppers who uploaded inspo</span><b>{(f["Inspo uploaded"] ?? 0).toLocaleString("en-IN")}</b></div>
        <div className="card stat"><span className="small muted">Saved pieces with an in-stock match</span><b>{c.pieces_covered.toLocaleString("en-IN")} <span className="small muted">of {c.pieces.toLocaleString("en-IN")}</span></b></div>
        <div className="card stat"><span className="small muted">Looks fully covered</span><b>{c.fully_covered_looks} <span className="small muted">of {c.looks}</span></b></div>
        <div className="card stat"><span className="small muted">Shoppers who bought</span><b>{f["Purchased"] ?? 0}</b></div>
      </div>

      <div className="two-col section">
        <section className="card pad stack">
          <h3>Inspo to cart</h3>
          <span className="small muted">Distinct shoppers reaching each step</span>
          <Bars data={r.funnel.map((s) => ({ label: s.step, value: s.shoppers, note: `${s.events} events` }))} unit="shoppers" caption="Funnel from inspo to purchase" />
        </section>
        <section className="card pad stack">
          <h3>Unmet demand</h3>
          <span className="small muted">Pieces shoppers saved that we couldn't match in stock</span>
          <Bars data={r.gaps.map((g) => ({ label: g.label, value: g.unmatched, note: g.variants.map((v) => `${pretty(v.color)} ${v.fabric} ${v.saves}`).join(", ") }))}
            unit="saves without a match" caption="Unmet demand by piece" />
          <div className="stack" style={{ gap: 6 }}>
            {r.gaps.slice(0, 3).map((g) => (
              <div key={g.label} className="small"><b>{g.label}</b>: saved {g.saves} times, {g.saves_with_match} matches in stock.
                <span className="muted"> Most wanted: {g.variants.map((v) => `${pretty(v.color).toLowerCase()} ${v.fabric} (${v.saves})`).join(", ")}</span></div>
            ))}
          </div>
        </section>
      </div>

      <section className="card pad section stack">
        <h3>Most-saved attributes</h3>
        <div className="two-col">
          {Object.entries(r.top_attributes).map(([k, v]) => (
            <div key={k} className="stack" style={{ gap: 6 }}>
              <span className="label">{pretty(k)}</span>
              <Bars data={v.map((x) => ({ label: x.label, value: x.saves }))} unit="saves" caption={`Most saved ${k}`} />
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
