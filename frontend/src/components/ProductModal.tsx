import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, inr, pretty } from "../api";
import type { Hanger, ProductDetail } from "../types";
import { ErrorBox, Icon, Loading, Modal, Price, useToast } from "./ui";

export default function ProductModal({ productId, hangerId, onClose, onAddedToLook }: {
  productId: string; hangerId?: number; onClose: () => void; onAddedToLook?: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["product", productId], queryFn: () => api.get<ProductDetail>(`/products/${productId}`) });
  const [size, setSize] = useState<string | null>(null);
  useEffect(() => { if (q.data) setSize(q.data.suggested_size); }, [q.data]);
  const p = q.data;

  const toLook = useMutation({
    mutationFn: () => api.post<Hanger>(`/hangers/${hangerId}/choose`, { product_id: productId, size }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["folder"] });
      qc.invalidateQueries({ queryKey: ["matches", hangerId] });
      toast("Added to your look");
      onAddedToLook?.();
      onClose();
    },
  });
  const toCart = useMutation({
    mutationFn: () => api.post("/cart", { product_id: productId, size, qty: 1 }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); qc.invalidateQueries({ queryKey: ["cart"] }); toast("Added to cart"); onClose(); },
  });

  return (
    <Modal title={p?.name ?? "Product"} onClose={onClose}>
      {q.error && <ErrorBox error={q.error} onRetry={() => q.refetch()} />}
      {!p && !q.error && <Loading />}
      {p && (
        <div className="stack">
          <div style={{ background: "#f4efe8", borderRadius: 14, padding: 16 }}>
            <img src={p.image_url} alt={`${p.name} flat-lay`} style={{ maxHeight: 280, margin: "0 auto" }} />
          </div>
          <div className="row-between">
            <div>
              <div className="eyebrow">{p.brand} · {p.subcategory_label}</div>
              <Price price={p.price_inr} mrp={p.mrp_inr} />
              {p.price_history.length > 1 && p.price_history[p.price_history.length - 1].price_inr < p.price_history[0].price_inr && (
                <span className="chip chip-sage" style={{ marginLeft: 8 }}>Price dropped from {inr(p.price_history[0].price_inr)}</span>
              )}
            </div>
            {!p.in_stock && <span className="chip chip-rose">Sold out</span>}
          </div>
          <p className="muted" style={{ margin: 0 }}>{p.description}</p>
          <div className="chips">
            <span className="chip">{pretty(p.fabric)}</span>
            {p.silhouette !== "none" && <span className="chip">{pretty(p.silhouette)} fit</span>}
            {p.pattern !== "solid" && <span className="chip">{pretty(p.pattern)}</span>}
            {p.style_tags.map((s) => <span key={s} className="chip">{pretty(s)}</span>)}
          </div>
          <div className="field">
            <span className="label">Size {p.suggested_size ? <span className="muted">(your size is pre-selected)</span> : null}</span>
            <div className="size-picker" role="group" aria-label="Choose a size">
              {p.sizes.map((s) => (
                <button key={s.size} type="button" disabled={s.stock <= 0} aria-pressed={size === s.size} onClick={() => setSize(s.size)}
                  aria-label={`${s.size}${s.stock <= 0 ? ", sold out" : s.stock <= 2 ? `, only ${s.stock} left` : ""}`}>
                  {s.size}
                </button>
              ))}
            </div>
            {size && (p.sizes.find((s) => s.size === size)?.stock ?? 0) <= 2 && <span className="small" style={{ color: "var(--amber)" }}>Only a few left in {size}</span>}
          </div>
          <div className="small muted row"><Icon name="bolt" size={16} /> {p.delivery}</div>
          {(toLook.error || toCart.error) && <ErrorBox error={toLook.error || toCart.error} />}
          <div className="row">
            {hangerId && (
              <button className="btn btn-primary" style={{ flex: 1 }} disabled={toLook.isPending} onClick={() => toLook.mutate()}>
                <Icon name="hanger" /> Add to look
              </button>
            )}
            <button className={`btn ${hangerId ? "" : "btn-primary"}`} style={{ flex: 1 }} disabled={!size || toCart.isPending || !p.in_stock}
              onClick={() => toCart.mutate()}>
              <Icon name="bag" /> {size ? "Add to cart" : "Pick a size"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
