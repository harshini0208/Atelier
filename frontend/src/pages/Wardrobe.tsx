import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, KeyboardSensor, PointerSensor, TouchSensor, useDraggable, useSensor, useSensors } from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, inr, pretty } from "../api";
import AvatarSetup from "../components/AvatarSetup";
import MannequinStage, { Avatar, useMannequin } from "../components/Mannequin";
import ProductModal from "../components/ProductModal";
import { ErrorBox, Icon, Loading, Modal, Price, useToast } from "../components/ui";
import type { FolderDetail, Product } from "../types";

type TrayItem = { hanger_id: number; hanger_index: number; piece: { name: string; crop_url: string | null; subcategory: string };
  product: Product | null; source: "chosen" | "top_match" | "not_in_store"; slot: string };
type Look = { id: number; name: string; reason: string; items: { product: Product; slot: string }[]; total_inr: number };
type StyleOption = { items: { product: Product; why: string; reasons: { label: string }[] }[]; total_inr: number; reason: string; gaps: string[] };
type StyleResp = { options: StyleOption[]; complete_the_look: { product: Product; score: number; pairs_with_past: string | null; reasons: { label: string }[] }[]; message?: string };

function TrayCard({ item, onPut }: { item: TrayItem; onPut: (p: Product) => void }) {
  const p = item.product;
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `tray-${item.hanger_id}`, disabled: !p, data: { product: p } });
  return (
    <div ref={setNodeRef} className="card tray-card" style={{ padding: 8, display: "flex", gap: 8, alignItems: "center", opacity: isDragging ? 0.4 : 1,
      touchAction: "none" }}>
      <div {...listeners} {...attributes} aria-label={p ? `Drag ${p.name} onto the mannequin` : `${item.piece.name}: not in store`}
        style={{ cursor: p ? "grab" : "not-allowed", display: "flex", gap: 8, alignItems: "center", flex: 1, minWidth: 0 }}>
        <div style={{ width: 58, height: 58, borderRadius: 10, background: "#f4efe8", flex: "none", display: "grid", placeItems: "center" }}>
          {p ? <img src={p.image_url} alt="" style={{ width: 52, height: 52, objectFit: "contain" }} />
            : item.piece.crop_url && <img src={item.piece.crop_url} alt="" style={{ width: 52, height: 52, objectFit: "contain", opacity: .5 }} />}
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="small" style={{ fontWeight: 600, lineHeight: 1.25 }}>{p?.name ?? item.piece.name}</div>
          <div className="small muted">{p ? inr(p.price_inr) : "Not in store"}{p && item.source === "top_match" ? " · top match" : ""}</div>
        </div>
      </div>
      {p && <button className="btn btn-sm" onClick={() => onPut(p)} aria-label={`Put ${p.name} on the mannequin`}>Put on</button>}
    </div>
  );
}

function SizePrompt({ items, onDone, onClose }: { items: { product: Product; reason: string }[]; onDone: (sizes: Record<string, string>) => void; onClose: () => void }) {
  const [sizes, setSizes] = useState<Record<string, string>>({});
  return (
    <Modal title="Pick sizes" onClose={onClose}>
      <div className="stack">
        {items.map(({ product: p, reason }) => (
          <div key={p.id} className="stack" style={{ gap: 6 }}>
            <b>{p.name}</b><span className="small muted">{reason}</span>
            <div className="size-picker">
              {p.sizes.map((s) => (
                <button key={s.size} disabled={s.stock <= 0} aria-pressed={sizes[p.id] === s.size} onClick={() => setSizes({ ...sizes, [p.id]: s.size })}>{s.size}</button>
              ))}
            </div>
          </div>
        ))}
        <button className="btn btn-primary" disabled={items.some((i) => !sizes[i.product.id])} onClick={() => onDone(sizes)}>Add to cart</button>
      </div>
    </Modal>
  );
}

export default function Wardrobe() {
  const { id } = useParams();
  const folderId = Number(id);
  const qc = useQueryClient();
  const toast = useToast();
  const folder = useQuery({ queryKey: ["folder", folderId], queryFn: () => api.get<FolderDetail>(`/folders/${folderId}`) });
  const tray = useQuery({ queryKey: ["tray", folderId], queryFn: () => api.get<{ items: TrayItem[] }>(`/folders/${folderId}/tray`) });
  const looks = useQuery({ queryKey: ["looks", folderId], queryFn: () => api.get<Look[]>(`/folders/${folderId}/looks`) });
  const avatar = useQuery({ queryKey: ["avatar"], queryFn: () => api.get<Avatar>("/avatar") });
  const geo = useMannequin(avatar.data);
  const [placed, setPlaced] = useState<Record<string, Product>>({});
  const [history, setHistory] = useState<Record<string, Product>[]>([]);
  const [dragging, setDragging] = useState(false);
  const [active, setActive] = useState<Product | null>(null);
  const [editAvatar, setEditAvatar] = useState(false);
  const [product, setProduct] = useState<string | null>(null);
  const [needSizes, setNeedSizes] = useState<{ product: Product; reason: string }[] | null>(null);
  const [loadedLook, setLoadedLook] = useState<number | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 8 } }), useSensor(KeyboardSensor));

  // start from the most recent saved look (e.g. one the stylist just made)
  useEffect(() => {
    const latest = looks.data?.[0];
    if (latest && latest.id !== loadedLook) {
      setPlaced(Object.fromEntries(latest.items.map((i) => [i.slot, i.product])));
      setLoadedLook(latest.id);
    }
  }, [looks.data, loadedLook]);

  const commit = (next: Record<string, Product>) => { setHistory((h) => [...h.slice(-20), placed]); setPlaced(next); };
  const putOn = (p: Product) => {
    const next = { ...placed };
    if (p.slot === "full") { delete next.torso; delete next.legs; }
    if (p.slot === "torso" || p.slot === "legs") delete next.full;
    next[p.slot] = p;
    commit(next);
  };
  const takeOff = (p: Product) => { const next = { ...placed }; delete next[p.slot]; commit(next); };
  const onDragStart = (e: DragStartEvent) => { setDragging(true); setActive((e.active.data.current?.product as Product) ?? null); };
  const onDragEnd = (e: DragEndEvent) => {
    setDragging(false);
    setActive(null);
    const p = e.active.data.current?.product as Product | undefined;
    if (!p || !e.over) return;
    putOn(p);
    const zone = String(e.over.id).replace("zone-", "");
    if (zone !== "stage" && zone !== p.slot) toast(`Snapped to ${pretty(p.slot)}`);
  };

  const pieces = useMemo(() => Object.values(placed), [placed]);
  const total = pieces.reduce((s, p) => s + p.price_inr, 0);

  const style = useMutation({ mutationFn: (body: { formality?: string; occasion?: string }) => api.post<StyleResp>(`/folders/${folderId}/style`, body) });
  const save = useMutation({
    mutationFn: () => api.post<Look>(`/folders/${folderId}/looks`, { name: `Look ${(looks.data?.length ?? 0) + 1}`,
      placements: pieces.map((p) => ({ product_id: p.id })), reason: "" }),
    onSuccess: (l) => { setLoadedLook(l.id); qc.invalidateQueries({ queryKey: ["looks", folderId] }); toast("Look saved"); },
  });
  const addToCart = useMutation({
    // first pass: the whole look (sizes auto-picked); second pass: only the pieces that needed a size
    mutationFn: (items: { product_id: string; size?: string }[]) => api.post<{ added: unknown[]; needs_size: { product: Product; reason: string }[]; failed: { product: Product; reason: string }[] }>(
      `/cart/look/${folderId}`, { items }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["me"] }); qc.invalidateQueries({ queryKey: ["cart"] });
      if (r.needs_size.length) setNeedSizes(r.needs_size); else setNeedSizes(null);
      toast(`${r.added.length} piece${r.added.length === 1 ? "" : "s"} added to cart${r.failed.length ? ` (${r.failed.length} unavailable)` : ""}`);
    },
  });

  if (folder.error) return <ErrorBox error={folder.error} onRetry={() => folder.refetch()} />;
  if (!folder.data || !avatar.data) return <Loading label="Opening your walk-in wardrobe" />;

  return (
    <>
      <Link to={`/folders/${folderId}`} className="btn btn-ghost btn-sm" style={{ marginLeft: -8 }}><Icon name="back" size={16} /> {folder.data.name}</Link>
      <div className="row-between" style={{ marginTop: 4 }}>
        <div><span className="eyebrow">Walk-in wardrobe</span><h1>{folder.data.name}</h1></div>
        <button className="btn btn-sm" onClick={() => setEditAvatar(true)}><Icon name="user" size={16} /> Edit mannequin</button>
      </div>
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragCancel={() => { setDragging(false); setActive(null); }} onDragEnd={onDragEnd}>
        <div className="wardrobe-layout section" style={{ marginTop: 16 }}>
          <section className="stack wardrobe-tray" style={{ gap: 8 }}>
            <div className="row-between"><h3>Your hangers</h3><span className="small muted">Drag onto the mannequin, or tap “Put on”</span></div>
            {tray.isLoading && <Loading />}
            {tray.data?.items.length === 0 && <div className="empty"><p className="muted" style={{ margin: 0 }}>No hangers yet. Save pieces from an inspo first.</p></div>}
            <div className="tray-grid">{tray.data?.items.map((it) => <TrayCard key={it.hanger_id} item={it} onPut={putOn} />)}</div>
          </section>
          <div className="stack wardrobe-stage">
            <MannequinStage geo={geo.data} placed={pieces} dragging={dragging} onRemove={takeOff} />
            <div className="row" style={{ justifyContent: "center", gap: 6 }}>
              <button className="btn btn-sm" disabled={!history.length} onClick={() => { setPlaced(history[history.length - 1]); setHistory((h) => h.slice(0, -1)); }}>
                <Icon name="undo" size={16} /> Undo</button>
              <button className="btn btn-sm" disabled={!pieces.length} onClick={() => commit({})}><Icon name="trash" size={16} /> Clear</button>
              <button className="btn btn-sm" disabled={!pieces.length || save.isPending} onClick={() => save.mutate()}><Icon name="check" size={16} /> Save look</button>
            </div>
            {pieces.length > 0 && (
              <div className="card pad stack" style={{ gap: 8 }}>
                <div className="row-between"><b>On the mannequin</b><span className="price">{inr(total)}</span></div>
                <div className="chips">{pieces.map((p) => <button key={p.id} className="chip" onClick={() => setProduct(p.id)}>{p.name}</button>)}</div>
                <button className="btn btn-primary" onClick={() => addToCart.mutate(pieces.map((p) => ({ product_id: p.id })))} disabled={addToCart.isPending}>
                  {addToCart.isPending ? <span className="spinner" /> : <Icon name="bag" />} Add full look to cart
                </button>
                {addToCart.error && <ErrorBox error={addToCart.error} />}
              </div>
            )}
          </div>

          <div className="stack wardrobe-side">

            <section className="card pad stack">
              <div className="row-between">
                <h3>Style it for me</h3>
                <button className="btn btn-primary btn-sm" onClick={() => style.mutate({})} disabled={style.isPending || !tray.data?.items.length}>
                  {style.isPending ? <span className="spinner" /> : <Icon name="sparkle" size={16} />} Style it
                </button>
              </div>
              <div className="chips">
                {[["more_casual", "More casual"], ["more_formal", "More formal"], ["more_festive", "More festive"]].map(([k, l]) => (
                  <button key={k} className="chip" onClick={() => style.mutate({ formality: k })} disabled={style.isPending}>{l}</button>
                ))}
              </div>
              {style.error && <ErrorBox error={style.error} />}
              {style.data?.message && <div className="alert">{style.data.message}</div>}
              {style.data?.options.map((o, k) => (
                <button key={k} className="card" style={{ padding: 10, textAlign: "left", cursor: "pointer" }}
                  onClick={() => commit(Object.fromEntries(o.items.map((i) => [i.product.slot, i.product])))}>
                  <div className="row-between"><b>Look {k + 1}</b><Price price={o.total_inr} /></div>
                  <div className="row" style={{ gap: 4, margin: "6px 0" }}>
                    {o.items.map((i) => <img key={i.product.id} src={i.product.image_url} alt={i.product.name} title={i.why}
                      style={{ width: 44, height: 44, objectFit: "contain", background: "#f4efe8", borderRadius: 8 }} />)}
                  </div>
                  <div className="small">{o.reason}</div>
                  <div className="small muted" style={{ marginTop: 4 }}>Tap to dress the mannequin</div>
                </button>
              ))}
              {!!style.data?.complete_the_look.length && (
                <div className="stack" style={{ gap: 6 }}>
                  <b className="small">Complete the look</b>
                  <div className="tray-grid">
                    {style.data.complete_the_look.map((c) => (
                      <div key={c.product.id} className="card" style={{ padding: 8, display: "flex", gap: 8, alignItems: "center" }}>
                        <img src={c.product.image_url} alt="" style={{ width: 48, height: 48, objectFit: "contain", background: "#f4efe8", borderRadius: 8 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="small" style={{ fontWeight: 600 }}>{c.product.name}</div>
                          <div className="small muted">{inr(c.product.price_inr)}{c.pairs_with_past ? ` · goes with your ${c.pairs_with_past}` : ""}</div>
                        </div>
                        <button className="btn btn-sm" onClick={() => putOn(c.product)}>Put on</button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            {!!looks.data?.length && (
              <section className="stack" style={{ gap: 8 }}>
                <h3>Saved looks</h3>
                {looks.data.map((l) => (
                  <button key={l.id} className="card" style={{ padding: 10, textAlign: "left", cursor: "pointer" }}
                    onClick={() => commit(Object.fromEntries(l.items.map((i) => [i.slot, i.product])))}>
                    <div className="row-between"><b className="small">{l.name}</b><span className="small">{inr(l.total_inr)}</span></div>
                    <div className="row" style={{ gap: 4, marginTop: 6 }}>
                      {l.items.map((i) => <img key={i.product.id} src={i.product.image_url} alt={i.product.name}
                        style={{ width: 36, height: 36, objectFit: "contain", background: "#f4efe8", borderRadius: 6 }} />)}
                    </div>
                  </button>
                ))}
              </section>
            )}
          </div>
        </div>
        <DragOverlay dropAnimation={null}>
          {active && (
            <div className="card" style={{ padding: 6, width: 96, boxShadow: "0 14px 34px rgba(0,0,0,.25)", cursor: "grabbing" }}>
              <img src={active.image_url} alt="" style={{ width: 84, height: 84, objectFit: "contain" }} />
            </div>
          )}
        </DragOverlay>
      </DndContext>
      {editAvatar && <AvatarSetup initial={avatar.data} onClose={() => setEditAvatar(false)} />}
      {product && <ProductModal productId={product} onClose={() => setProduct(null)} />}
      {needSizes && <SizePrompt items={needSizes} onClose={() => setNeedSizes(null)}
        onDone={(sizes) => addToCart.mutate(Object.entries(sizes).map(([product_id, size]) => ({ product_id, size })))} />}
    </>
  );
}
