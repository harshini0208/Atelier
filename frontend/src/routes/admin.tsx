import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ArrowLeft, Loader2, RotateCcw, Sparkles, Tag, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Chip, PageHead, SectionHead } from "@/components/wiw/bits";
import { adminToken, api, errorText, inr, pretty, setAdminToken } from "@/lib/api";
import type { Product } from "@/lib/types";

export const Route = createFileRoute("/admin")({
  head: () => ({ meta: [{ title: "Brand admin · Urban Thread" }] }),
  component: Admin,
});

/** Brand-side tools (not linked from the shopper app): insights and simulated store events. */
function Admin() {
  const qc = useQueryClient();
  const [token, setToken] = useState(adminToken() ?? "");
  const [tab, setTab] = useState<"insights" | "events">("insights");
  const save = (e: FormEvent) => {
    e.preventDefault();
    setAdminToken(token.trim() || null);
    void qc.invalidateQueries();
  };
  return (
    <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <Link to="/" className="mb-6 inline-flex min-h-11 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Shopper app
      </Link>
      <PageHead eyebrow="Urban Thread · brand admin" title="Store insights & events" intro="For the brand team only. Shoppers never see this page." />
      <form className="mb-6 flex flex-wrap items-center gap-2" onSubmit={save}>
        <label htmlFor="adm" className="text-xs text-muted-foreground">Admin token</label>
        <input id="adm" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Not needed locally"
          className="h-11 w-64 rounded-full border border-border bg-card px-4 text-sm" />
        <Button size="sm" variant="outline">Use token</Button>
      </form>
      <div className="mb-8 flex gap-2" role="tablist">
        <Chip active={tab === "insights"} onClick={() => setTab("insights")}>Insights</Chip>
        <Chip active={tab === "events"} onClick={() => setTab("events")}>Store events</Chip>
      </div>
      {tab === "insights" ? <Insights /> : <Events />}
    </main>
  );
}

function Bars({ rows, unit }: { rows: { label: string; value: number; note?: string }[]; unit: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label} className="text-sm">
          <div className="mb-1 flex justify-between gap-3"><span>{r.label}</span><span className="text-xs text-muted-foreground">{r.value} {unit}</span></div>
          <span className="block h-1.5 overflow-hidden rounded-full bg-muted">
            <span className="block h-full rounded-full bg-primary" style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          {r.note && <p className="mt-1 text-[11px] text-muted-foreground">{r.note}</p>}
        </li>
      ))}
    </ul>
  );
}

type R = {
  funnel: { step: string; shoppers: number; events: number }[];
  gaps: { label: string; saves: number; saves_with_match: number; unmatched: number; variants: { color: string; fabric: string; saves: number }[] }[];
  top_attributes: Record<string, { label: string; saves: number }[]>;
  coverage: { looks: number; pieces_covered: number; pieces_covered_in_prefs: number; pieces: number; fully_covered_looks: number };
  memo: { headline: string; bullets: string[]; action: string };
  memo_source: string;
  source: string;
  synthetic_note: string;
};

function Insights() {
  const q = useQuery({ queryKey: ["retailer"], queryFn: () => api.get<R>("/retailer") });
  if (q.error) return <p className="text-sm text-danger">{errorText(q.error)}</p>;
  if (!q.data) return <div className="shimmer h-72 rounded-[20px]" />;
  const r = q.data;
  const c = r.coverage;
  const f = Object.fromEntries(r.funnel.map((s) => [s.step, s.shoppers]));
  const stats: [string, string][] = [
    ["Shoppers who uploaded inspo", (f["Inspo uploaded"] ?? 0).toLocaleString("en-IN")],
    ["Saved pieces with an in-stock match", `${c.pieces_covered} of ${c.pieces}`],
    ["Looks fully covered", `${c.fully_covered_looks} of ${c.looks}`],
    ["Shoppers who bought", String(f["Purchased"] ?? 0)],
  ];
  return (
    <div className="space-y-10">
      <p className="text-xs text-muted-foreground">{r.source}. {r.synthetic_note}</p>
      <section className="rounded-[20px] bg-hero p-6 sm:p-8">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest opacity-80">
          Merchandiser memo · {r.memo_source === "fallback" ? "template" : "Gemini"}, from the numbers below
        </p>
        <h2 className="display text-3xl">{r.memo.headline}</h2>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm opacity-90">{r.memo.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        <p className="mt-4 text-sm"><b>Suggested action:</b> {r.memo.action}</p>
      </section>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([l, v]) => (
          <div key={l} className="rounded-[18px] border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">{l}</p>
            <p className="display mt-2 text-3xl">{v}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-10 md:grid-cols-2">
        <section>
          <SectionHead title="Inspo to cart" meta="distinct shoppers per step" />
          <Bars rows={r.funnel.map((s) => ({ label: s.step, value: s.shoppers, note: `${s.events} events` }))} unit="shoppers" />
        </section>
        <section>
          <SectionHead title="Unmet demand" meta="saved, no in-stock match" />
          <Bars rows={r.gaps.map((g) => ({ label: g.label, value: g.unmatched, note: g.variants.map((v) => `${pretty(v.color)} ${v.fabric} ${v.saves}`).join(", ") }))} unit="unmatched saves" />
        </section>
      </div>
      <section>
        <SectionHead title="Most-saved attributes" />
        <div className="grid gap-8 md:grid-cols-2">
          {Object.entries(r.top_attributes).map(([k, v]) => (
            <div key={k}>
              <p className="eyebrow mb-3">{pretty(k)}</p>
              <Bars rows={v.map((x) => ({ label: x.label, value: x.saves }))} unit="saves" />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

type State = { watched: { product: Product; hanger: string; watchers: number }[]; new_arrivals: { index: number; name: string; price_inr: number }[] };

function Events() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["demo"], queryFn: () => api.get<State>("/demo/state") });
  const [log, setLog] = useState<string[]>([]);
  const done = (msg: string) => {
    setLog((l) => [msg, ...l]);
    toast.success(msg);
    void qc.invalidateQueries();
  };
  const fail = (e: unknown) => toast.error(errorText(e));
  const price = useMutation({
    mutationFn: (p: Product) =>
      api.post<{ product: string; new_price: number; notified: string[] }>("/demo/price", {
        product_id: p.id,
        new_price_inr: Math.max(99, Math.round((p.price_inr * 0.78) / 100) * 100 - 1),
      }),
    onSuccess: (r) => done(`${r.product} now ${inr(r.new_price)}. Notified: ${r.notified.join(", ") || "nobody"}`),
    onError: fail,
  });
  const restock = useMutation({
    mutationFn: (x: { p: Product; size: string }) =>
      api.post<{ product: string; size: string; notified: string[] }>("/demo/restock", { product_id: x.p.id, size: x.size, qty: 5 }),
    onSuccess: (r) => done(`${r.product} size ${r.size} restocked. Notified: ${r.notified.join(", ") || "nobody"}`),
    onError: fail,
  });
  const arrival = useMutation({
    mutationFn: (i: number) =>
      api.post<{ product: Product; notified: string[]; scores: Record<string, number>; threshold: number }>(`/demo/new-arrival/${i}`),
    onSuccess: (r) =>
      done(`Launched ${r.product.name}. Taste scores ${Object.entries(r.scores).map(([u, s]) => `${u} ${s}`).join(", ")} (threshold ${r.threshold}). Notified: ${r.notified.join(", ") || "nobody"}`),
    onError: fail,
  });
  const reset = useMutation({ mutationFn: () => api.post("/demo/reset"), onSuccess: () => done("Demo data reset"), onError: fail });

  if (q.error) return <p className="text-sm text-danger">{errorText(q.error)}</p>;
  if (!q.data) return <div className="shimmer h-72 rounded-[20px]" />;
  return (
    <div className="space-y-10">
      <p className="text-sm text-muted-foreground">Simulate store events. Each one runs the matching watchers and notifies shoppers whose hangers it matches.</p>
      {log.length > 0 && (
        <div className="space-y-1 rounded-[16px] bg-muted p-4 text-sm">{log.slice(0, 4).map((l, i) => <p key={i}>{l}</p>)}</div>
      )}
      <section>
        <SectionHead title="Pieces shoppers are watching" />
        {q.data.watched.length === 0 && <p className="text-sm text-muted-foreground">No shopper has hung a piece yet.</p>}
        <ul className="space-y-3">
          {q.data.watched.map((w) => {
            const sold = w.product.sizes.filter((s) => s.stock <= 0).map((s) => s.size);
            return (
              <li key={w.product.id} className="flex flex-wrap items-center gap-3 rounded-[16px] border border-border bg-card p-3">
                <img src={w.product.image_url} alt="" className="size-14 rounded-[10px] object-cover" />
                <div className="min-w-[180px] flex-1">
                  <p className="text-sm font-medium">{w.product.name} <span className="text-muted-foreground">{inr(w.product.price_inr)}</span></p>
                  <p className="text-xs text-muted-foreground">{w.watchers} shopper{w.watchers === 1 ? "" : "s"} watching · e.g. for “{w.hanger}”</p>
                </div>
                <Button size="sm" variant="outline" disabled={price.isPending} onClick={() => price.mutate(w.product)}><Tag /> Drop price ~22%</Button>
                {sold.map((s) => (
                  <Button key={s} size="sm" variant="outline" disabled={restock.isPending} onClick={() => restock.mutate({ p: w.product, size: s })}>
                    <Zap /> Restock {s}
                  </Button>
                ))}
              </li>
            );
          })}
        </ul>
      </section>
      <section>
        <SectionHead title="New arrivals" meta="notifies shoppers whose taste clears the threshold" />
        <div className="flex flex-wrap gap-2">
          {q.data.new_arrivals.length === 0 && <span className="text-sm text-muted-foreground">All launched.</span>}
          {q.data.new_arrivals.map((a) => (
            <Button key={a.index} variant="outline" disabled={arrival.isPending} onClick={() => arrival.mutate(a.index)}>
              <Sparkles /> Launch {a.name} ({inr(a.price_inr)})
            </Button>
          ))}
        </div>
      </section>
      <section>
        <Button
          variant="ghost"
          disabled={reset.isPending}
          onClick={() => confirm("Delete ALL shopper data (profiles, folders, carts, orders, events) and start fresh? The catalog stays.") && reset.mutate()}
        >
          {reset.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Delete all shopper data
        </Button>
      </section>
    </div>
  );
}
