import { useQuery } from "@tanstack/react-query";
import { api, pretty } from "../api";
import { useVocab } from "../components/Layout";
import { ErrorBox, Loading } from "../components/ui";

type Item = { field: string; value: string; label: string; count: number };
type TasteT = { saves: number; skips: number; core: Item[]; exploring: Item[]; sentence: string; counts: Record<string, Record<string, number>> };
const FIELD: Record<string, string> = { subcategory: "Piece", color: "Colour", fabric: "Fabric", pattern: "Pattern", style_tags: "Style", occasion_tags: "Occasion" };

export default function Taste() {
  const vocab = useVocab();
  const q = useQuery({ queryKey: ["taste"], queryFn: () => api.get<TasteT>("/taste") });
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading label="Reading your saves" />;
  const t = q.data;
  const hex = (c: string) => vocab.data?.colors.find((x) => x.key === c)?.hex;
  const chip = (i: Item, cls: string) => (
    <span key={i.field + i.value} className={`chip ${cls}`} title={`${FIELD[i.field]} · saved ${i.count}×`}>
      {i.field === "color" && <span className="swatch" style={{ background: hex(i.value) }} />}
      {i.label} <span style={{ opacity: .7 }}>×{i.count}</span>
    </span>
  );
  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <span className="eyebrow">My taste</span>
      <h1>What you keep saving</h1>
      <p style={{ fontFamily: "var(--serif)", fontSize: 20, lineHeight: 1.4 }}>{t.sentence}</p>
      <p className="small muted">Built from {t.saves} saved pieces and {t.skips} you skipped. Counts are exact; only the sentence above is written by AI.</p>
      <div className="two-col section">
        <section className="card pad stack">
          <h3>Core taste</h3>
          <span className="small muted">Attributes that keep recurring across your saves</span>
          <div className="chips">{t.core.length ? t.core.map((i) => chip(i, "chip-sage")) : <span className="muted small">Save a few more pieces.</span>}</div>
        </section>
        <section className="card pad stack">
          <h3>Exploring</h3>
          <span className="small muted">New to you in the last two weeks</span>
          <div className="chips">{t.exploring.length ? t.exploring.map((i) => chip(i, "")) : <span className="muted small">Nothing new lately.</span>}</div>
        </section>
      </div>
      <section className="card pad section">
        <h3 style={{ marginBottom: 12 }}>By attribute</h3>
        <div className="two-col">
          {Object.entries(t.counts).filter(([, v]) => Object.keys(v).length).map(([f, v]) => (
            <div key={f}>
              <div className="label" style={{ marginBottom: 6 }}>{FIELD[f]}</div>
              <div className="chips">{Object.entries(v).map(([k, n]) => (
                <span key={k} className="chip">{f === "color" && <span className="swatch" style={{ background: hex(k) }} />}{pretty(k)} ×{n}</span>))}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
