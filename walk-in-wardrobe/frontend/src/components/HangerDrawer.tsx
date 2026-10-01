import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, pretty } from "../api";
import type { Matches, MatchItem, Product } from "../types";
import { useVocab } from "./Layout";
import ProductModal from "./ProductModal";
import { CoverageLine, ErrorBox, ProductCard, Sheet, SkeletonGrid } from "./ui";

function Tier({ title, hint, items, onOpen, chosen }: {
  title: string; hint: string; items: MatchItem[]; onOpen: (p: Product) => void; chosen?: string | null;
}) {
  if (!items.length) return null;
  return (
    <section className="section" style={{ marginTop: 20 }}>
      <div className="section-head">
        <h3>{title}</h3>
        <span className="small muted">{hint}</span>
      </div>
      <div className="product-grid">
        {items.map((i) => (
          <ProductCard key={i.product.id} item={i} onOpen={onOpen}
            badge={chosen === i.product.id ? <span className="chip chip-dark">In your look</span> : undefined} />
        ))}
      </div>
    </section>
  );
}

export default function HangerDrawer({ hangerId, onClose }: { hangerId: number; onClose: () => void }) {
  const vocab = useVocab();
  const [product, setProduct] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["matches", hangerId], queryFn: () => api.get<Matches>(`/hangers/${hangerId}/matches`) });
  const m = q.data;
  const piece = m?.hanger.piece;
  const hex = piece && vocab.data?.colors.find((c) => c.key === piece.color)?.hex;

  const head = (
    <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
      {piece?.crop_url && <img src={piece.crop_url} alt={`Your saved ${piece.name}`} style={{ width: 64, height: 64, objectFit: "contain", background: "#efe8de", borderRadius: 10 }} />}
      <div style={{ minWidth: 0 }}>
        <div className="eyebrow">Matches from Urban Thread</div>
        <h2 style={{ fontSize: 20 }}>{piece?.name ?? "Loading…"}</h2>
        {piece && (
          <div className="chips" style={{ marginTop: 4 }}>
            {hex && <span className="chip"><span className="swatch" style={{ background: hex }} />{pretty(piece.color)}</span>}
            <span className="chip">{pretty(piece.fabric)}</span>
            {piece.silhouette !== "none" && <span className="chip">{pretty(piece.silhouette)}</span>}
            {piece.style_tags.slice(0, 2).map((s) => <span key={s} className="chip">{pretty(s)}</span>)}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <Sheet title={piece?.name ?? "Matches"} onClose={onClose} head={head}>
      {q.error && <ErrorBox error={q.error} onRetry={() => q.refetch()} />}
      {!m && !q.error && <SkeletonGrid />}
      {m && (
        <>
          <CoverageLine coverage={m.coverage} />
          {m.gap_message && <div className="alert" style={{ marginTop: 12 }}>{m.gap_message}</div>}
          <Tier title="For you" hint="Matches the style and your preferences" items={m.for_you} onOpen={(p) => setProduct(p.id)}
            chosen={m.hanger.chosen_product_id} />
          {m.for_you.length === 0 && m.also_view.length > 0 && (
            <div className="alert" style={{ marginTop: 16 }}>
              Nothing matches all your preferences yet. These are close matches, and the chips show what's different.
            </div>
          )}
          <Tier title="Also view" hint="Great style match, outside a preference" items={m.also_view} onOpen={(p) => setProduct(p.id)}
            chosen={m.hanger.chosen_product_id} />
          <Tier title="Closest from this store" hint="Not a close match, the nearest we have" items={m.closest} onOpen={(p) => setProduct(p.id)} />
        </>
      )}
      {product && <ProductModal productId={product} hangerId={hangerId} onClose={() => setProduct(null)} />}
    </Sheet>
  );
}
