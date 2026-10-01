import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, inr } from "../api";
import { ErrorBox, Icon, Loading, useToast } from "../components/ui";
import type { Product } from "../types";

type State = { watched: { product: Product; hanger: string; watchers: number }[]; new_arrivals: { index: number; name: string; price_inr: number }[] };

export default function Demo() {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["demo"], queryFn: () => api.get<State>("/demo/state") });
  const [log, setLog] = useState<string[]>([]);
  const done = (msg: string) => { setLog((l) => [msg, ...l]); toast(msg); qc.invalidateQueries(); };
  const price = useMutation({
    mutationFn: (p: Product) => api.post<{ product: string; new_price: number; notified: string[] }>("/demo/price",
      { product_id: p.id, new_price_inr: Math.max(99, Math.round((p.price_inr * 0.78) / 100) * 100 - 1) }),
    onSuccess: (r) => done(`${r.product} now ${inr(r.new_price)}. Notified: ${r.notified.join(", ") || "nobody"}`),
  });
  const restock = useMutation({
    mutationFn: (x: { p: Product; size: string }) => api.post<{ product: string; size: string; notified: string[] }>("/demo/restock",
      { product_id: x.p.id, size: x.size, qty: 5 }),
    onSuccess: (r) => done(`${r.product} size ${r.size} restocked. Notified: ${r.notified.join(", ") || "nobody"}`),
  });
  const arrival = useMutation({
    mutationFn: (i: number) => api.post<{ product: Product; notified: string[]; scores: Record<string, number>; threshold: number }>(`/demo/new-arrival/${i}`),
    onSuccess: (r) => done(`Launched ${r.product.name}. Taste scores ${Object.entries(r.scores).map(([u, s]) => `${u} ${s}`).join(", ")} (threshold ${r.threshold}). Notified: ${r.notified.join(", ") || "nobody"}`),
  });
  const reset = useMutation({ mutationFn: () => api.post("/demo/reset"), onSuccess: () => done("Demo data reset") });
  const err = price.error || restock.error || arrival.error || reset.error;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <p className="muted">Simulate store events. Each one runs the matching watchers and notifies shoppers whose hangers it matches.</p>
      {err && <ErrorBox error={err} />}
      {log.length > 0 && <div className="alert alert-sage stack" style={{ gap: 4 }}>{log.slice(0, 4).map((l, i) => <span key={i}>{l}</span>)}</div>}
      {!q.data && <Loading />}
      {q.data && (
        <>
          <section className="section">
            <div className="section-head"><h2>Pieces shoppers are watching</h2></div>
            {q.data.watched.length === 0 && <div className="empty"><p className="muted" style={{ margin: 0 }}>No shopper has hung a piece yet.</p></div>}
            <div className="stack">
              {q.data.watched.map((w) => {
                const sold = w.product.sizes.filter((s) => s.stock <= 0).map((s) => s.size);
                return (
                  <div key={w.product.id} className="card pad row" style={{ flexWrap: "wrap", gap: 12 }}>
                    <img src={w.product.image_url} alt="" style={{ width: 56, height: 56, objectFit: "contain", background: "#f4efe8", borderRadius: 8 }} />
                    <div style={{ flex: 1, minWidth: 180 }}>
                      <b>{w.product.name}</b> <span className="small">{inr(w.product.price_inr)}</span>
                      <div className="small muted">{w.watchers} shopper{w.watchers === 1 ? "" : "s"} watching · e.g. for “{w.hanger}”</div>
                    </div>
                    <button className="btn btn-sm" onClick={() => price.mutate(w.product)} disabled={price.isPending}><Icon name="tag" size={16} /> Drop price ~22%</button>
                    {sold.map((s) => (
                      <button key={s} className="btn btn-sm" onClick={() => restock.mutate({ p: w.product, size: s })} disabled={restock.isPending}>
                        <Icon name="bolt" size={16} /> Restock {s}</button>
                    ))}
                  </div>
                );
              })}
            </div>
          </section>
          <section className="section">
            <div className="section-head"><h2>New arrivals</h2><span className="small muted">Notifies only shoppers whose taste score clears the threshold</span></div>
            <div className="row">
              {q.data.new_arrivals.length === 0 && <span className="muted">All launched.</span>}
              {q.data.new_arrivals.map((a) => (
                <button key={a.index} className="btn" onClick={() => arrival.mutate(a.index)} disabled={arrival.isPending}>
                  <Icon name="sparkle" size={16} /> Launch {a.name} ({inr(a.price_inr)})</button>
              ))}
            </div>
          </section>
          <section className="section">
            <button className="btn btn-ghost" onClick={() => confirm("Delete ALL shopper data (profiles, folders, carts, orders, events) and start fresh? The catalog stays.") && reset.mutate()} disabled={reset.isPending}>
              {reset.isPending ? <span className="spinner" /> : <Icon name="undo" size={16} />} Delete all shopper data</button>
          </section>
        </>
      )}
    </div>
  );
}
