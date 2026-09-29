import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../components/Layout";
import ProductModal from "../components/ProductModal";
import { ErrorBox, Price, SkeletonGrid } from "../components/ui";
import type { Product } from "../types";

type ShopResp = {
  count: number; products: (Product & { is_new: boolean; added_at: string })[];
  categories: { key: string; label: string; count: number }[];
  subcategories: { key: string; label: string; count: number }[];
};
const SORTS: [string, string][] = [["recommended", "Recommended"], ["new", "What's new"], ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"], ["discount", "Biggest discount"]];

function Badge({ p }: { p: ShopResp["products"][number] }) {
  const off = p.mrp_inr > p.price_inr ? Math.round(((p.mrp_inr - p.price_inr) / p.mrp_inr) * 100) : 0;
  const lowStock = p.in_stock && p.sizes.reduce((s, x) => s + x.stock, 0) <= 4;
  if (!p.in_stock) return <span className="shop-badge dark">Sold out</span>;
  if (p.is_new) return <span className="shop-badge">New</span>;
  if (off) return <span className="shop-badge sale">{off}% off</span>;
  if (lowStock) return <span className="shop-badge">Few left</span>;
  return null;
}

export default function Shop() {
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const pref = me?.preferences?.gender_fit;
  const gender = params.get("gender") ?? (pref === "men" ? "men" : "women");
  const category = params.get("category") ?? "";
  const subcategory = params.get("sub") ?? "";
  const sort = params.get("sort") ?? "recommended";
  const [q, setQ] = useState(params.get("q") ?? "");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { const t = window.setTimeout(() => update({ q: q || null }), 300); return () => window.clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const qs = new URLSearchParams({ gender, sort, ...(category ? { category } : {}), ...(subcategory ? { subcategory } : {}), ...(params.get("q") ? { q: params.get("q")! } : {}) });
  const shop = useQuery({ queryKey: ["shop", qs.toString()], queryFn: () => api.get<ShopResp>(`/shop?${qs}`), placeholderData: (p) => p });

  function update(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  }
  const catLabel = shop.data?.categories.find((c) => c.key === category)?.label;

  return (
    <div className="shop">
      <div className="shop-top">
        <div className="shop-gender" role="tablist" aria-label="Section">
          {[["women", "Women"], ["men", "Men"]].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={gender === k} onClick={() => update({ gender: k, category: null, sub: null })}>{l}</button>
          ))}
        </div>
        <input className="input shop-search" type="search" placeholder="Search Urban Thread" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" />
      </div>

      <div className="shop-layout">
        <nav className="shop-cats" aria-label="Categories">
          <button aria-current={!category ? "page" : undefined} onClick={() => update({ category: null, sub: null })}>
            View all <span>{shop.data?.categories.reduce((s, c) => s + c.count, 0) ?? ""}</span></button>
          {shop.data?.categories.map((c) => (
            <button key={c.key} aria-current={category === c.key ? "page" : undefined} onClick={() => update({ category: c.key, sub: null })}>
              {c.label} <span>{c.count}</span></button>
          ))}
        </nav>

        <section style={{ minWidth: 0 }}>
          <div className="row-between" style={{ marginBottom: 10 }}>
            <div>
              <span className="eyebrow">Urban Thread · {gender === "men" ? "Men" : "Women"}</span>
              <h1 style={{ fontSize: 26 }}>{catLabel ?? "New season"} <span className="small muted" style={{ fontFamily: "var(--sans)" }}>{shop.data ? `${shop.data.count} items` : ""}</span></h1>
            </div>
            <label className="row small">
              <span className="muted">Sort</span>
              <select className="select" style={{ width: "auto", minHeight: 36 }} value={sort} onChange={(e) => update({ sort: e.target.value })}>
                {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
          </div>
          {!!shop.data?.subcategories.length && (
            <div className="chips" style={{ marginBottom: 14 }}>
              <button className="chip" aria-pressed={!subcategory} onClick={() => update({ sub: null })}>All</button>
              {shop.data.subcategories.map((s) => (
                <button key={s.key} className="chip" aria-pressed={subcategory === s.key} onClick={() => update({ sub: s.key })}>{s.label} ({s.count})</button>
              ))}
            </div>
          )}
          {shop.error && <ErrorBox error={shop.error} onRetry={() => shop.refetch()} />}
          {!shop.data && <SkeletonGrid n={8} />}
          {shop.data?.count === 0 && <div className="empty"><h3>Nothing here yet</h3><p className="muted" style={{ margin: 0 }}>Try another category or search.</p></div>}
          <div className="shop-grid" style={{ opacity: shop.isFetching ? 0.6 : 1 }}>
            {shop.data?.products.map((p) => (
              <button key={p.id} className="shop-card" onClick={() => setOpen(p.id)} aria-label={`${p.name}`}>
                <div className="shop-img">
                  <img src={p.image_url} alt={p.name} loading="lazy" className={p.image_url.includes("/photos/") ? "photo" : ""} />
                  <Badge p={p} />
                </div>
                <div className="shop-meta">
                  <span className="name">{p.name}</span>
                  <Price price={p.price_inr} mrp={p.mrp_inr} />
                  <span className="small muted">{p.sizes.filter((s) => s.stock > 0).map((s) => s.size).join(" · ") || "Out of stock"}</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
      {open && <ProductModal productId={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
