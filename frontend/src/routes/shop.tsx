import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Heart, Search } from "lucide-react";
import { Chip, PageHead } from "@/components/wiw/bits";
import { inr } from "@/lib/api";
import { getShop } from "@/lib/data";
import { toggleWish, useStore } from "@/lib/store";
import { openProduct } from "@/lib/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/shop")({
  head: () => ({ meta: [{ title: "Shop Urban Thread · Atelier" }] }),
  component: Shop,
});

const NEW_DAYS = 21;

function Shop() {
  const pref = useStore((s) => s.me?.preferences?.gender_fit);
  const [gender, setGender] = useState(pref === "men" ? "men" : "women");
  const [cat, setCat] = useState<string | null>(null);
  const [sub, setSub] = useState<string | null>(null);
  const [sort, setSort] = useState("relevance");
  const [q, setQ] = useState("");
  const wishlist = useStore((s) => s.wishlist);
  const { data } = useQuery({ queryKey: ["shop", gender], queryFn: () => getShop(gender) });
  const newest = useMemo(
    () => Math.max(0, ...(data?.products ?? []).map((p) => (p.added_at ? new Date(p.added_at).getTime() : 0))),
    [data],
  );

  const inCat = useMemo(() => (data?.products ?? []).filter((p) => !cat || p.category === cat), [data, cat]);
  const subs = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    inCat.forEach((p) => m.set(p.subcategory, { label: p.subcategory_label, n: (m.get(p.subcategory)?.n ?? 0) + 1 }));
    return [...m.entries()];
  }, [inCat]);
  const products = useMemo(() => {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    let list = inCat.filter(
      (p) =>
        (!sub || p.subcategory === sub) &&
        terms.every((t) => `${p.name} ${p.subcategory_label} ${p.fabric} ${p.primary_color}`.toLowerCase().includes(t)),
    );
    if (sort === "low") list = [...list].sort((a, b) => a.price_inr - b.price_inr);
    if (sort === "high") list = [...list].sort((a, b) => b.price_inr - a.price_inr);
    if (sort === "sale") list = [...list].sort((a, b) => b.mrp_inr - b.price_inr - (a.mrp_inr - a.price_inr));
    if (sort === "new") list = [...list].sort((a, b) => (b.added_at ?? "").localeCompare(a.added_at ?? ""));
    return list;
  }, [inCat, sub, q, sort]);

  return (
    <>
      <PageHead eyebrow="Urban Thread" title="Shop" />
      <div className="mb-6 flex gap-6 border-b border-border" role="tablist">
        {([["women", "Women"], ["men", "Men"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={gender === k} onClick={() => { setGender(k); setCat(null); setSub(null); }}
            className={cn("-mb-px min-h-11 border-b-2 font-serif text-xl font-light", gender === k ? "border-foreground" : "border-transparent text-muted-foreground")}>
            {l}
          </button>
        ))}
      </div>

      <div className="grid gap-8 md:grid-cols-[180px_minmax(0,1fr)]">
        <nav aria-label="Categories" className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 md:mx-0 md:flex-col md:gap-0 md:px-0">
          {[{ key: null, label: "View all", count: data?.count ?? 0 }, ...(data?.categories ?? [])].map((c) => (
            <button key={c.key ?? "all"} onClick={() => { setCat(c.key); setSub(null); }} aria-pressed={cat === c.key}
              className={cn("flex min-h-11 shrink-0 items-center justify-between gap-3 rounded-full px-4 text-sm md:rounded-none md:px-0",
                cat === c.key ? "bg-primary text-primary-foreground md:bg-transparent md:font-semibold md:text-foreground md:underline md:underline-offset-4" : "bg-card md:bg-transparent")}>
              {c.label} <span className="text-xs opacity-60">{c.count}</span>
            </button>
          ))}
        </nav>

        <div className="min-w-0">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row">
            <label className="relative flex-1">
              <span className="sr-only">Search</span>
              <Search className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the store"
                className="h-11 w-full rounded-full border border-border bg-card pl-11 pr-4 text-sm" />
            </label>
            <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)} className="h-11 rounded-full border border-border bg-card px-4 text-sm">
              <option value="relevance">Recommended</option>
              <option value="new">Newest</option>
              <option value="low">Price: low to high</option>
              <option value="high">Price: high to low</option>
              <option value="sale">Biggest discount</option>
            </select>
          </div>
          {cat && subs.length > 1 && (
            <div className="no-scrollbar mb-6 flex gap-2 overflow-x-auto">
              <Chip active={!sub} onClick={() => setSub(null)}>All</Chip>
              {subs.map(([k, v]) => <Chip key={k} active={sub === k} onClick={() => setSub(k)}>{v.label} <span className="opacity-60">{v.n}</span></Chip>)}
            </div>
          )}

          {!data ? (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="shimmer aspect-[3/4] rounded-[18px]" />)}</div>
          ) : products.length === 0 ? (
            <p className="py-20 text-center text-sm text-muted-foreground">Nothing here yet. Try another section.</p>
          ) : (
            <ul className="grid grid-cols-2 gap-x-4 gap-y-8 lg:grid-cols-3">
              {products.map((p) => {
                const off = p.mrp_inr > p.price_inr ? Math.round((1 - p.price_inr / p.mrp_inr) * 100) : 0;
                const isNew = !!p.added_at && newest - new Date(p.added_at).getTime() < NEW_DAYS * 86_400_000;
                const wished = wishlist.includes(p.id);
                return (
                  <li key={p.id} className="shop-card">
                    <div className="relative overflow-hidden rounded-[18px] bg-muted">
                      <button onClick={() => openProduct(p.id)} className="block w-full" aria-label={p.name}>
                        <img src={p.image_url} alt={p.name} loading="lazy" className="aspect-[3/4] w-full object-cover transition-transform duration-500 hover:scale-[1.03]" />
                      </button>
                      {(off > 0 || isNew) && (
                        <span className="absolute left-2 top-2 rounded-full bg-accent px-2 py-1 text-[10px] font-bold text-accent-foreground">
                          {off > 0 ? `${off}% OFF` : "NEW"}
                        </span>
                      )}
                      <button onClick={() => void toggleWish(p.id)} aria-label={wished ? `Remove ${p.name} from wishlist` : `Add ${p.name} to wishlist`} aria-pressed={wished}
                        className="absolute right-1 top-1 grid size-11 place-items-center rounded-full">
                        <span className="grid size-8 place-items-center rounded-full bg-card"><Heart className={cn("size-4", wished && "fill-current")} /></span>
                      </button>
                    </div>
                    <button onClick={() => openProduct(p.id)} className="mt-3 block text-left">
                      <p className="line-clamp-2 text-sm leading-snug">{p.name}</p>
                      <p className="mt-1 text-sm font-semibold">
                        {inr(p.price_inr)} {off > 0 && <span className="ml-1 text-xs font-normal text-muted-foreground line-through">{inr(p.mrp_inr)}</span>}
                      </p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">{p.sizes.filter((s) => s.stock > 0).map((s) => s.size).join(" · ") || "Out of stock"}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
