import { cn } from "@/lib/utils";
import { mannequinUrl } from "@/lib/data";
import type { Vocab } from "@/lib/types";
import { Chip } from "./bits";

export type PrefDraft = {
  name: string;
  city: string;
  gender_fit: string;
  sizes: Record<string, string>;
  fit: string;
  body: string;
  tone: string;
  budgets: Record<string, [number, number]>;
  preferred_materials: string[];
  avoid_materials: string[];
  avoid_colors: string[];
  occasions: string[];
  bring_purchases: boolean;
};

export const BODY_LABEL: Record<string, string> = { slim: "Slim", curvy: "Curvy", plus: "Plus size", athletic: "Athletic" };
export const BUDGET_CATS: [string, string][] = [
  ["tops", "Tops"],
  ["bottoms", "Bottoms"],
  ["one_piece", "Dresses & sets"],
  ["outerwear", "Outerwear"],
  ["footwear", "Footwear"],
  ["accessories", "Accessories"],
];

/** The preferences part of a draft, in the shape the API takes. */
export function prefsPayload(d: PrefDraft) {
  const budgets = Object.fromEntries(
    Object.entries(d.budgets).filter(([, [lo, hi]]) => hi > 0 && hi >= lo),
  );
  return {
    city: d.city,
    gender_fit: d.gender_fit,
    sizes: d.sizes,
    fit: d.fit,
    budgets,
    preferred_materials: d.preferred_materials,
    avoid_materials: d.avoid_materials,
    avoid_colors: d.avoid_colors,
    occasions: d.occasions,
  };
}

const field = "h-11 w-full rounded-[14px] border border-border bg-background px-4 text-sm";
const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

type P = { d: PrefDraft; set: (p: Partial<PrefDraft>) => void; vocab: Vocab };

export function AboutFields({ d, set, vocab }: P) {
  return (
    <div className="space-y-5">
      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Your name</span>
        <input className={field} value={d.name} onChange={(e) => set({ name: e.target.value })} autoComplete="given-name" />
      </label>
      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-muted-foreground">City (for delivery times)</span>
        <select className={field} value={d.city} onChange={(e) => set({ city: e.target.value })}>
          {vocab.cities.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </label>
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">I shop</span>
        <div className="flex gap-2">
          {([["women", "Women's"], ["men", "Men's"], ["any", "Everything"]] as const).map(([k, l]) => (
            <Chip key={k} active={d.gender_fit === k} onClick={() => set({ gender_fit: k })}>{l}</Chip>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SizeFields({ d, set, vocab }: P) {
  const g = d.gender_fit === "men" ? "men" : "women";
  const labels: Record<string, string> = { tops: "Tops & dresses", bottoms: "Bottoms (waist)", footwear: "Footwear (UK size)" };
  return (
    <div className="space-y-5">
      {Object.entries(vocab.sizes).map(([cat, byG]) => (
        <div key={cat} role="group" aria-label={`${cat} size`}>
          <span className="mb-2 block text-xs font-medium text-muted-foreground">{labels[cat] ?? cat}</span>
          <div className="flex flex-wrap gap-2">
            {(byG[g] ?? []).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={d.sizes[cat] === s}
                onClick={() => set({ sizes: { ...d.sizes, [cat]: s } })}
                className={cn(
                  "size-11 rounded-full border text-sm",
                  d.sizes[cat] === s ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">Fit I like</span>
        <div className="flex flex-wrap gap-2">
          {["slim", "regular", "relaxed", "oversized"].map((f) => (
            <Chip key={f} active={d.fit === f} onClick={() => set({ fit: f })}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}

export function MannequinFields({ d, set }: Omit<P, "vocab">) {
  const bodies = ["slim", "curvy", "plus", "athletic"];
  const tones = ["light", "tan", "brown", "deep"];
  return (
    <div className="grid gap-6 sm:grid-cols-[180px_1fr]">
      <div className="aspect-[3/4] overflow-hidden rounded-[18px] bg-muted">
        <img src={mannequinUrl(d.body, d.tone)} alt={`${BODY_LABEL[d.body]} mannequin, ${d.tone} finish`} className="h-full w-full object-contain" />
      </div>
      <div className="space-y-5">
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-muted-foreground">Body type</legend>
          <div className="grid grid-cols-4 gap-2">
            {bodies.map((b) => (
              <button
                key={b}
                type="button"
                aria-pressed={d.body === b}
                onClick={() => set({ body: b })}
                className={cn(
                  "overflow-hidden rounded-[14px] border-2 bg-muted text-[11px] font-medium",
                  d.body === b ? "border-primary" : "border-transparent hover:border-border",
                )}
              >
                <img src={mannequinUrl(b, d.tone)} alt="" className="aspect-[3/4] w-full object-contain" loading="lazy" />
                <span className="block py-1.5">{BODY_LABEL[b]}</span>
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-muted-foreground">Finish</legend>
          <div className="grid grid-cols-4 gap-2">
            {tones.map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={d.tone === t}
                aria-label={`${t} finish`}
                onClick={() => set({ tone: t })}
                className={cn(
                  "overflow-hidden rounded-[14px] border-2 bg-muted",
                  d.tone === t ? "border-primary" : "border-transparent hover:border-border",
                )}
              >
                <img src={mannequinUrl(d.body, t)} alt="" className="aspect-square w-full object-cover object-top" loading="lazy" />
                <span className="block py-1 text-[11px] capitalize">{t}</span>
              </button>
            ))}
          </div>
        </fieldset>
        <p className="text-xs text-muted-foreground">
          Only used to show how pieces drape and fit. The mannequin is faceless; no photos of you.
        </p>
      </div>
    </div>
  );
}

export function BudgetFields({ d, set }: Omit<P, "vocab">) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">What you'd usually spend on one piece, in ₹. Pieces above this still show up, labelled.</p>
      {BUDGET_CATS.map(([k, l]) => {
        const [lo, hi] = d.budgets[k] ?? [0, 0];
        return (
          <div key={k} className="grid grid-cols-[1fr_96px_96px] items-center gap-2">
            <span className="text-sm">{l}</span>
            <input aria-label={`${l} from`} type="number" inputMode="numeric" className={field} value={lo || ""} placeholder="From"
              onChange={(e) => set({ budgets: { ...d.budgets, [k]: [Number(e.target.value), hi] } })} />
            <input aria-label={`${l} up to`} type="number" inputMode="numeric" className={field} value={hi || ""} placeholder="Up to"
              onChange={(e) => set({ budgets: { ...d.budgets, [k]: [lo, Number(e.target.value)] } })} />
          </div>
        );
      })}
    </div>
  );
}

export function FabricFields({ d, set, vocab }: P) {
  return (
    <div className="space-y-5">
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">Fabrics I love</span>
        <div className="flex flex-wrap gap-2">
          {vocab.fabrics.map((f) => (
            <Chip key={f} active={d.preferred_materials.includes(f)} onClick={() => set({ preferred_materials: toggle(d.preferred_materials, f), avoid_materials: d.avoid_materials.filter((x) => x !== f) })}>{f}</Chip>
          ))}
        </div>
      </div>
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">Fabrics I avoid</span>
        <div className="flex flex-wrap gap-2">
          {vocab.fabrics.map((f) => (
            <Chip key={f} active={d.avoid_materials.includes(f)} onClick={() => set({ avoid_materials: toggle(d.avoid_materials, f), preferred_materials: d.preferred_materials.filter((x) => x !== f) })}>{f}</Chip>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ColourFields({ d, set, vocab }: P) {
  return (
    <div className="space-y-5">
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">Colours I avoid</span>
        <div className="flex flex-wrap gap-2">
          {vocab.colors.map((c) => (
            <Chip key={c.key} active={d.avoid_colors.includes(c.key)} onClick={() => set({ avoid_colors: toggle(d.avoid_colors, c.key) })}>
              {/* product colour sample: data, not theme styling */}
              <span className="size-3 rounded-full border border-border" style={{ background: c.hex }} aria-hidden />
              {c.label}
            </Chip>
          ))}
        </div>
      </div>
      <div>
        <span className="mb-2 block text-xs font-medium text-muted-foreground">I dress for</span>
        <div className="flex flex-wrap gap-2">
          {vocab.occasions.map((o) => (
            <Chip key={o} active={d.occasions.includes(o)} onClick={() => set({ occasions: toggle(d.occasions, o) })}>{o}</Chip>
          ))}
        </div>
      </div>
    </div>
  );
}
