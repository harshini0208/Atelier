import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, inr } from "../api";
import { ErrorBox, Icon, Loading, Price } from "../components/ui";
import type { Product } from "../types";

type CartLine = { id: number; product: Product; size: string; qty: number; line_total_inr: number; in_stock: boolean; stock: number };
type CartT = {
  groups: { brand: string; items: CartLine[]; subtotal_inr: number; delivery_days: number }[];
  count: number; subtotal_inr: number; savings_inr: number; shipping_inr: number; total_inr: number; city: string; delivery_days: number;
};
type Order = { id: number; total_inr: number; delivery_days: number; city: string; items: { product_id: string; qty: number }[] };

export default function Cart() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cart"], queryFn: () => api.get<CartT>("/cart") });
  const [placed, setPlaced] = useState<Order | null>(null);
  const refresh = (d: CartT) => { qc.setQueryData(["cart"], d); qc.invalidateQueries({ queryKey: ["me"] }); };
  const qty = useMutation({ mutationFn: ({ id, n }: { id: number; n: number }) => api.patch<CartT>(`/cart/${id}`, { qty: n }), onSuccess: refresh });
  const order = useMutation({
    mutationFn: () => api.post<Order>("/checkout"),
    onSuccess: (o) => { setPlaced(o); qc.invalidateQueries(); },
  });

  if (placed) {
    return (
      <div className="card pad stack" style={{ maxWidth: 560, margin: "0 auto", textAlign: "center", alignItems: "center" }}>
        <span style={{ width: 56, height: 56, borderRadius: 99, background: "var(--sage-bg)", color: "var(--sage)", display: "grid", placeItems: "center" }}><Icon name="check" size={28} /></span>
        <h1>Order #{placed.id} placed</h1>
        <p className="muted" style={{ margin: 0 }}>
          {placed.items.length} item{placed.items.length === 1 ? "" : "s"} · {inr(placed.total_inr)} · arriving in {placed.city} in about {placed.delivery_days} days.
        </p>
        <div className="alert small">This is a demo checkout. No payment was taken and nothing will ship.</div>
        <Link to="/" className="btn btn-primary">Back to your wardrobes</Link>
      </div>
    );
  }
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading label="Opening your cart" />;
  const c = q.data;
  if (!c.count) {
    return (
      <div className="empty">
        <h3>Your cart is empty</h3>
        <p className="muted">Open a wardrobe, style a look, and add the whole thing to your cart in one tap.</p>
        <Link to="/" className="btn btn-primary">Go to your wardrobes</Link>
      </div>
    );
  }
  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <span className="eyebrow">Cart</span>
      <h1>{c.count} item{c.count === 1 ? "" : "s"}</h1>
      {c.groups.map((g) => (
        <section key={g.brand} className="card pad section">
          <div className="row-between"><h3>{g.brand}</h3><span className="small muted">Ships in {g.delivery_days} days to {c.city}</span></div>
          <div className="stack" style={{ marginTop: 12 }}>
            {g.items.map((it) => (
              <div key={it.id} className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
                <img src={it.product.image_url} alt="" style={{ width: 72, height: 72, objectFit: "contain", background: "#f4efe8", borderRadius: 10, flex: "none" }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{it.product.name}</div>
                  <div className="small muted">Size {it.size}</div>
                  {!it.in_stock && <span className="chip chip-rose">Only {it.stock} left</span>}
                  <div className="row" style={{ gap: 6, marginTop: 6 }}>
                    <button className="btn btn-sm" aria-label="Decrease quantity" onClick={() => qty.mutate({ id: it.id, n: it.qty - 1 })}>−</button>
                    <span aria-live="polite">{it.qty}</span>
                    <button className="btn btn-sm" aria-label="Increase quantity" disabled={it.qty >= it.stock} onClick={() => qty.mutate({ id: it.id, n: it.qty + 1 })}>+</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => qty.mutate({ id: it.id, n: 0 })}>Remove</button>
                  </div>
                </div>
                <Price price={it.line_total_inr} />
              </div>
            ))}
          </div>
        </section>
      ))}
      <section className="card pad section stack">
        <div className="row-between"><span>Subtotal</span><b>{inr(c.subtotal_inr)}</b></div>
        {c.savings_inr > 0 && <div className="row-between" style={{ color: "var(--sage)" }}><span>You save (vs MRP)</span><b>{inr(c.savings_inr)}</b></div>}
        <div className="row-between"><span>Delivery</span><b>{c.shipping_inr ? inr(c.shipping_inr) : "Free"}</b></div>
        <div className="row-between" style={{ fontSize: 18 }}><span>Total</span><b>{inr(c.total_inr)}</b></div>
        {(qty.error || order.error) && <ErrorBox error={qty.error || order.error} />}
        <button className="btn btn-primary btn-block" disabled={order.isPending} onClick={() => order.mutate()}>
          {order.isPending ? <span className="spinner" /> : <Icon name="check" />} Place order (demo)
        </button>
        <span className="small muted" style={{ textAlign: "center" }}>Mock checkout: no payment is taken.</span>
      </section>
    </div>
  );
}
