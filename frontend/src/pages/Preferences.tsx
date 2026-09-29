import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, pretty } from "../api";
import { useVocab } from "../components/Layout";
import { ErrorBox, Icon, Loading, useToast } from "../components/ui";
import type { Preferences as Prefs } from "../types";

const CATS: [string, string][] = [["tops", "Tops"], ["bottoms", "Bottoms"], ["one_piece", "Dresses & sets"],
  ["outerwear", "Outerwear"], ["footwear", "Footwear"], ["accessories", "Accessories"]];
const FITS = ["slim", "regular", "relaxed", "oversized"];

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" className="chip" aria-pressed={on} onClick={onClick}>{children}</button>;
}

export default function Preferences() {
  const qc = useQueryClient();
  const toast = useToast();
  const vocab = useVocab();
  const q = useQuery({ queryKey: ["prefs"], queryFn: () => api.get<Prefs>("/preferences") });
  const [p, setP] = useState<Prefs | null>(null);
  useEffect(() => { if (q.data) setP(q.data); }, [q.data]);
  const save = useMutation({
    mutationFn: (body: Prefs) => api.put<Prefs>("/preferences", body),
    onSuccess: (d) => {
      qc.setQueryData(["prefs"], d);
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["folder"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
      toast("Preferences saved. Your matches are updated.");
    },
  });
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!p || !vocab.data) return <Loading label="Loading your preferences" />;

  const set = <K extends keyof Prefs>(k: K, v: Prefs[K]) => setP({ ...p, [k]: v });
  const toggle = (k: "preferred_materials" | "avoid_materials" | "avoid_colors" | "occasions", v: string) => {
    const cur = p[k];
    const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
    const other = k === "preferred_materials" ? "avoid_materials" : k === "avoid_materials" ? "preferred_materials" : null;
    setP({ ...p, [k]: next, ...(other ? { [other]: p[other].filter((x) => x !== v) } : {}) });
  };
  const g = p.gender_fit === "men" ? "men" : "women";
  const sizeOpts = (grp: string) => vocab.data.sizes[grp][g];

  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(p); }}>
      <div className="row-between" style={{ marginBottom: 8 }}>
        <div>
          <span className="eyebrow">Set once, edit anytime</span>
          <h1>Your preferences</h1>
        </div>
      </div>
      <p className="muted" style={{ marginTop: 4 }}>
        These are soft preferences. Matches that fit them show under <b>For you</b>; great matches that don't are still shown
        under <b>Also view</b>, with the reason.
      </p>
      <div className="prefs-grid section">
        <section className="card pad stack">
          <h3>Budget per piece</h3>
          {CATS.map(([k, lbl]) => {
            const [lo, hi] = p.budgets[k] ?? [0, 5000];
            return (
              <div className="budget-row" key={k}>
                <span className="label">{lbl}</span>
                <input className="input" type="number" min={0} step={100} value={lo} aria-label={`${lbl} minimum ₹`}
                  onChange={(e) => set("budgets", { ...p.budgets, [k]: [Number(e.target.value), hi] })} />
                <input className="input" type="number" min={0} step={100} value={hi} aria-label={`${lbl} maximum ₹`}
                  onChange={(e) => set("budgets", { ...p.budgets, [k]: [lo, Number(e.target.value)] })} />
              </div>
            );
          })}
          <span className="small muted">Minimum and maximum, in ₹.</span>
        </section>

        <section className="card pad stack">
          <h3>Size and fit</h3>
          <div className="field">
            <span className="label">I shop</span>
            <div className="chips">
              {["women", "men", "any"].map((x) => (
                <Toggle key={x} on={p.gender_fit === x} onClick={() => set("gender_fit", x)}>{x === "any" ? "Everything" : pretty(x) + "'s"}</Toggle>
              ))}
            </div>
          </div>
          {(["tops", "bottoms", "footwear"] as const).map((grp) => (
            <div className="field" key={grp}>
              <label htmlFor={`size-${grp}`}>{grp === "footwear" ? "Footwear (UK)" : grp === "bottoms" ? "Bottoms (waist)" : "Tops & dresses"}</label>
              <select id={`size-${grp}`} className="select" value={p.sizes[grp] ?? ""} onChange={(e) => set("sizes", { ...p.sizes, [grp]: e.target.value })}>
                <option value="">Not set</option>
                {sizeOpts(grp).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          ))}
          <div className="field">
            <span className="label">Fit I like</span>
            <div className="chips">{FITS.map((f) => <Toggle key={f} on={p.fit === f} onClick={() => set("fit", f)}>{pretty(f)}</Toggle>)}</div>
          </div>
        </section>

        <section className="card pad stack">
          <h3>Materials</h3>
          <div className="field">
            <span className="label">I love</span>
            <div className="chips">{vocab.data.fabrics.filter((f) => f !== "metal").map((f) => (
              <Toggle key={f} on={p.preferred_materials.includes(f)} onClick={() => toggle("preferred_materials", f)}>{pretty(f)}</Toggle>))}</div>
          </div>
          <div className="field">
            <span className="label">I avoid</span>
            <div className="chips">{vocab.data.fabrics.filter((f) => f !== "metal").map((f) => (
              <Toggle key={f} on={p.avoid_materials.includes(f)} onClick={() => toggle("avoid_materials", f)}>{pretty(f)}</Toggle>))}</div>
          </div>
        </section>

        <section className="card pad stack">
          <h3>Colours, city, occasions</h3>
          <div className="field">
            <span className="label">Colours I avoid</span>
            <div className="chips">{vocab.data.colors.map((c) => (
              <Toggle key={c.key} on={p.avoid_colors.includes(c.key)} onClick={() => toggle("avoid_colors", c.key)}>
                <span className="swatch" style={{ background: c.hex }} />{c.label}
              </Toggle>))}</div>
          </div>
          <div className="field">
            <label htmlFor="city">City (for delivery times)</label>
            <select id="city" className="select" value={p.city} onChange={(e) => set("city", e.target.value)}>
              {vocab.data.cities.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <span className="label">Occasions I shop for</span>
            <div className="chips">{vocab.data.occasions.map((o) => (
              <Toggle key={o} on={p.occasions.includes(o)} onClick={() => toggle("occasions", o)}>{pretty(o)}</Toggle>))}</div>
          </div>
        </section>
      </div>
      {save.error && <div className="section"><ErrorBox error={save.error} /></div>}
      <div className="section row">
        <button className="btn btn-primary" disabled={save.isPending}>
          {save.isPending ? <span className="spinner" /> : <Icon name="check" />} Save preferences
        </button>
      </div>
    </form>
  );
}
