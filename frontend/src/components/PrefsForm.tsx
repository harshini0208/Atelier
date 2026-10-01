import { ReactNode } from "react";
import { pretty } from "../api";
import type { Preferences, Vocab } from "../types";

export type Draft = Preferences & { name: string };

export const CATS: [string, string][] = [["tops", "Tops"], ["bottoms", "Bottoms"], ["one_piece", "Dresses & sets"],
  ["outerwear", "Outerwear"], ["footwear", "Footwear"], ["accessories", "Accessories"]];
const FITS = ["slim", "regular", "relaxed", "oversized"];

export const DEFAULT_DRAFT: Draft = {
  name: "", city: "Mumbai", gender_fit: "women", fit: "regular", sizes: {},
  budgets: { tops: [500, 2500], bottoms: [800, 3000], one_piece: [1500, 5000], outerwear: [2000, 5000],
    footwear: [1000, 4000], accessories: [300, 2500] },
  preferred_materials: [], avoid_materials: [], avoid_colors: [], occasions: [],
};

type Props = { d: Draft; set: (d: Draft) => void; vocab: Vocab };

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return <button type="button" className="chip" aria-pressed={on} onClick={onClick}>{children}</button>;
}

function toggleList(d: Draft, k: "preferred_materials" | "avoid_materials" | "avoid_colors" | "occasions", v: string): Draft {
  const cur = d[k];
  const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
  const other = k === "preferred_materials" ? "avoid_materials" : k === "avoid_materials" ? "preferred_materials" : null;
  return { ...d, [k]: next, ...(other ? { [other]: d[other].filter((x) => x !== v) } : {}) };
}

export function AboutYou({ d, set, vocab }: Props) {
  return (
    <div className="stack">
      <div className="field">
        <label htmlFor="pf-name">Your name</label>
        <input id="pf-name" className="input" value={d.name} maxLength={60} autoComplete="given-name"
          onChange={(e) => set({ ...d, name: e.target.value })} placeholder="What should we call you?" />
      </div>
      <div className="field">
        <label htmlFor="pf-city">City <span className="muted">(for delivery times)</span></label>
        <select id="pf-city" className="select" value={d.city} onChange={(e) => set({ ...d, city: e.target.value })}>
          {vocab.cities.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      <div className="field">
        <span className="label">I shop</span>
        <div className="chips">
          {["women", "men", "any"].map((x) => (
            <Toggle key={x} on={d.gender_fit === x} onClick={() => set({ ...d, gender_fit: x, sizes: {} })}>
              {x === "any" ? "Everything" : `${pretty(x)}'s`}
            </Toggle>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SizeAndFit({ d, set, vocab }: Props) {
  const g = d.gender_fit === "men" ? "men" : "women";
  return (
    <div className="stack">
      {(["tops", "bottoms", "footwear"] as const).map((grp) => (
        <div className="field" key={grp}>
          <span className="label">{grp === "footwear" ? "Footwear (UK size)" : grp === "bottoms" ? "Bottoms (waist)" : "Tops & dresses"}</span>
          <div className="chips" role="group" aria-label={`${grp} size`}>
            {vocab.sizes[grp][g].map((s) => (
              <Toggle key={s} on={d.sizes[grp] === s} onClick={() => set({ ...d, sizes: { ...d.sizes, [grp]: s } })}>{s}</Toggle>
            ))}
          </div>
        </div>
      ))}
      <div className="field">
        <span className="label">Fit I like</span>
        <div className="chips">{FITS.map((f) => <Toggle key={f} on={d.fit === f} onClick={() => set({ ...d, fit: f })}>{pretty(f)}</Toggle>)}</div>
      </div>
    </div>
  );
}

export function Budgets({ d, set }: Omit<Props, "vocab">) {
  return (
    <div className="stack">
      <span className="small muted">What you'd usually spend on one piece, in ₹. Pieces above this still show up, labelled.</span>
      {CATS.map(([k, lbl]) => {
        const [lo, hi] = d.budgets[k] ?? [0, 5000];
        return (
          <div className="budget-row" key={k}>
            <span className="label">{lbl}</span>
            <input className="input" type="number" min={0} step={100} value={lo} aria-label={`${lbl} minimum ₹`}
              onChange={(e) => set({ ...d, budgets: { ...d.budgets, [k]: [Number(e.target.value), hi] } })} />
            <input className="input" type="number" min={0} step={100} value={hi} aria-label={`${lbl} maximum ₹`}
              onChange={(e) => set({ ...d, budgets: { ...d.budgets, [k]: [lo, Number(e.target.value)] } })} />
          </div>
        );
      })}
    </div>
  );
}

export function Materials({ d, set, vocab }: Props) {
  const fabrics = vocab.fabrics.filter((f) => f !== "metal");
  return (
    <div className="stack">
      <div className="field"><span className="label">Materials I love</span>
        <div className="chips">{fabrics.map((f) => <Toggle key={f} on={d.preferred_materials.includes(f)} onClick={() => set(toggleList(d, "preferred_materials", f))}>{pretty(f)}</Toggle>)}</div>
      </div>
      <div className="field"><span className="label">Materials I avoid</span>
        <div className="chips">{fabrics.map((f) => <Toggle key={f} on={d.avoid_materials.includes(f)} onClick={() => set(toggleList(d, "avoid_materials", f))}>{pretty(f)}</Toggle>)}</div>
      </div>
    </div>
  );
}

export function ColoursAndOccasions({ d, set, vocab }: Props) {
  return (
    <div className="stack">
      <div className="field"><span className="label">Colours I avoid</span>
        <div className="chips">{vocab.colors.map((c) => (
          <Toggle key={c.key} on={d.avoid_colors.includes(c.key)} onClick={() => set(toggleList(d, "avoid_colors", c.key))}>
            <span className="swatch" style={{ background: c.hex }} />{c.label}
          </Toggle>))}</div>
      </div>
      <div className="field"><span className="label">I shop for</span>
        <div className="chips">{vocab.occasions.map((o) => <Toggle key={o} on={d.occasions.includes(o)} onClick={() => set(toggleList(d, "occasions", o))}>{pretty(o)}</Toggle>)}</div>
      </div>
    </div>
  );
}

export function prefsPayload(d: Draft) {
  const { name, ...rest } = d;
  void name;
  const sizes = Object.fromEntries(Object.entries(rest.sizes).filter(([, v]) => v));
  return { ...rest, sizes };
}
