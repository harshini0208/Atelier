import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, KeyboardSensor, PointerSensor, TouchSensor, useDraggable, useDroppable, useSensor, useSensors } from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyboardEvent, PointerEvent as RPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, inr } from "../api";
import { mannequinUrl, useMannequin } from "../components/Mannequin";
import ProductModal from "../components/ProductModal";
import { ErrorBox, Icon, Loading, Modal, Price, useToast } from "../components/ui";
import type { FolderDetail, Product } from "../types";

type Item = { product: Product; x: number; y: number; w: number; z: number };   // x, y, w in % of the board
type FolderTrayItem = { hanger_id: number; piece: { name: string; crop_url: string | null }; product: Product | null; source: string };
type RailTrayItem = { key: string; product: Product; owned: boolean; sources: string[] };
/** One draggable piece: from a folder hanger (may be "not in store") or from the rail. */
type TrayItem = { key: string; name: string; crop_url: string | null; product: Product | null; note: string; owned: boolean };
type Look = { id: number; name: string; items: { product: Product; x: number; y: number; w: number; z: number }[]; total_inr: number };
type Layout = { product_id: string; x: number; y: number; w: number; z: number };
type StyleOption = { items: { product: Product; why: string; owned?: boolean }[]; total_inr: number; reason: string; layout: Layout[]; owned_count?: number };
type StyleResp = { options: StyleOption[]; message?: string;
  complete_the_look: { product: Product; pairs_with_past: string | null }[] };
type LayerAsk = { moved: string; other: string };

const SMALL = new Set(["footwear", "accessories"]);
const defaultWidth = (p: Product) => (SMALL.has(p.category) ? 22 : 36);
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function TrayCard({ item, onAdd }: { item: TrayItem; onAdd: (p: Product) => void }) {
  const p = item.product;
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `tray-${item.key}`, disabled: !p, data: { product: p } });
  return (
    <div ref={setNodeRef} className="card tray-card" style={{ padding: 8, display: "flex", gap: 8, alignItems: "center", opacity: isDragging ? 0.4 : 1, touchAction: "none" }}>
      <div {...listeners} {...attributes} aria-label={p ? `Drag ${p.name} onto the board` : `${item.name}: not in store`}
        style={{ cursor: p ? "grab" : "not-allowed", display: "flex", gap: 8, alignItems: "center", flex: 1, minWidth: 0 }}>
        <div style={{ width: 56, height: 56, borderRadius: 10, background: "#f4efe8", flex: "none", display: "grid", placeItems: "center" }}>
          {p ? <img src={p.image_url} alt="" style={{ width: 50, height: 50, objectFit: "contain" }} />
            : item.crop_url && <img src={item.crop_url} alt="" style={{ width: 50, height: 50, objectFit: "contain", opacity: .5 }} />}
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="small" style={{ fontWeight: 600, lineHeight: 1.25 }}>{p?.name ?? item.name}</div>
          <div className="small muted">{item.note}</div>
        </div>
      </div>
      {p && <button className="btn btn-sm" onClick={() => onAdd(p)} aria-label={`Add ${p.name} to the board`}>Add</button>}
    </div>
  );
}

function Board({ items, selected, setSelected, onStart, onMove, onMoveEnd, onResize, boardRef, onKey }: {
  items: Item[]; selected: string | null; setSelected: (id: string | null) => void; onStart: () => void;
  onMove: (id: string, x: number, y: number) => void; onMoveEnd: (id: string) => void; onResize: (id: string, w: number) => void;
  boardRef: React.MutableRefObject<HTMLDivElement | null>; onKey: (e: KeyboardEvent<HTMLDivElement>, id: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: "board" });
  const drag = useRef<{ id: string; mode: "move" | "resize"; sx: number; sy: number; ox: number; oy: number; ow: number } | null>(null);
  const setRefs = (el: HTMLDivElement | null) => { setNodeRef(el); boardRef.current = el; };

  const down = (e: RPointerEvent, it: Item, mode: "move" | "resize") => {
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setSelected(it.product.id);
    onStart();
    drag.current = { id: it.product.id, mode, sx: e.clientX, sy: e.clientY, ox: it.x, oy: it.y, ow: it.w };
  };
  const move = (e: RPointerEvent) => {
    const d = drag.current;
    const r = boardRef.current?.getBoundingClientRect();
    if (!d || !r) return;
    const dx = ((e.clientX - d.sx) / r.width) * 100;
    const dy = ((e.clientY - d.sy) / r.height) * 100;
    if (d.mode === "move") onMove(d.id, clamp(d.ox + dx, -10, 95), clamp(d.oy + dy, -10, 95));
    else onResize(d.id, clamp(d.ow + dx, 8, 90));
  };
  const up = () => {
    const d = drag.current;
    drag.current = null;
    if (d && d.mode === "move") onMoveEnd(d.id);
  };

  const sorted = [...items].sort((a, b) => a.z - b.z);
  return (
    <div ref={setRefs} className="board" onPointerDown={() => setSelected(null)}
      style={{ outline: isOver ? "2px dashed var(--sage)" : undefined }} role="region"
      aria-label={items.length ? `Style board with ${items.map((i) => i.product.name).join(", ")}` : "Empty style board"}>
      {items.length === 0 && (
        <div className="board-empty">
          <Icon name="sparkle" size={28} />
          <b>Your style board</b>
          <span className="small muted">Drag pieces here, or press “Style it for me”.</span>
        </div>
      )}
      {sorted.map((it) => {
        const sel = selected === it.product.id;
        return (
          <div key={it.product.id} data-pid={it.product.id} className={`board-item ${sel ? "selected" : ""}`} tabIndex={0}
            role="button" aria-label={`${it.product.name}. Arrow keys move, plus and minus resize, Delete removes.`}
            style={{ left: `${it.x}%`, top: `${it.y}%`, width: `${it.w}%`, zIndex: it.z }}
            onPointerDown={(e) => down(e, it, "move")} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
            onFocus={() => setSelected(it.product.id)} onKeyDown={(e) => onKey(e, it.product.id)}>
            <img src={it.product.image_url} alt="" draggable={false} />
            {sel && <span className="resize-handle" aria-hidden onPointerDown={(e) => down(e, it, "resize")} onPointerMove={move} onPointerUp={up} />}
          </div>
        );
      })}
    </div>
  );
}

type TryOn = { image_url: string | null; cached: boolean };

function MannequinDrop({ children }: { children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: "mannequin" });
  return <div ref={setNodeRef} className="mq-stage" style={{ outline: isOver ? "2px dashed var(--sage)" : undefined }}>{children}</div>;
}

function SizePrompt({ items, onDone, onClose }: { items: { product: Product; reason: string }[]; onDone: (s: Record<string, string>) => void; onClose: () => void }) {
  const [sizes, setSizes] = useState<Record<string, string>>({});
  return (
    <Modal title="Pick sizes" onClose={onClose}>
      <div className="stack">
        {items.map(({ product: p, reason }) => (
          <div key={p.id} className="stack" style={{ gap: 6 }}>
            <b>{p.name}</b><span className="small muted">{reason}</span>
            <div className="size-picker">{p.sizes.map((s) => (
              <button key={s.size} disabled={s.stock <= 0} aria-pressed={sizes[p.id] === s.size} onClick={() => setSizes({ ...sizes, [p.id]: s.size })}>{s.size}</button>))}</div>
          </div>
        ))}
        <button className="btn btn-primary" disabled={items.some((i) => !sizes[i.product.id])} onClick={() => onDone(sizes)}>Add to cart</button>
      </div>
    </Modal>
  );
}

export default function StyleBoard() {
  const { id } = useParams();
  const folderId = id ? Number(id) : null;          // no folder: the rail's board (/board)
  const base = folderId ? `/folders/${folderId}` : "/rail";
  const qc = useQueryClient();
  const toast = useToast();
  const folder = useQuery({ queryKey: ["folder", folderId], queryFn: () => api.get<FolderDetail>(`/folders/${folderId}`), enabled: !!folderId });
  const tray = useQuery({
    queryKey: ["tray", folderId ?? "rail"],
    queryFn: async (): Promise<{ items: TrayItem[] }> => {
      if (folderId) {
        const r = await api.get<{ items: FolderTrayItem[] }>(`/folders/${folderId}/tray`);
        return { items: r.items.map((t) => ({ key: `h${t.hanger_id}`, name: t.piece.name, crop_url: t.piece.crop_url, product: t.product,
          owned: false, note: t.product ? inr(t.product.price_inr) : "Wish · not in store" })) };
      }
      const r = await api.get<{ items: RailTrayItem[] }>("/rail/tray");
      return { items: r.items.map((t) => ({ key: t.key, name: t.product.name, crop_url: null, product: t.product, owned: t.owned,
        note: t.owned ? "Yours" : `${inr(t.product.price_inr)} · ${t.sources[0]}` })) };
    },
  });
  const looks = useQuery({ queryKey: ["looks", folderId ?? "rail"], queryFn: () => api.get<Look[]>(`${base}/looks`) });
  const owned = useMemo(() => new Set((tray.data?.items ?? []).filter((t) => t.owned && t.product).map((t) => t.product!.id)), [tray.data]);
  const [items, setItems] = useState<Item[]>([]);
  const [history, setHistory] = useState<Item[][]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [active, setActive] = useState<Product | null>(null);
  const [ask, setAsk] = useState<LayerAsk | null>(null);
  const [product, setProduct] = useState<string | null>(null);
  const [needSizes, setNeedSizes] = useState<{ product: Product; reason: string }[] | null>(null);
  const [loadedLook, setLoadedLook] = useState<number | null>(null);
  const [view, setView] = useState<"mannequin" | "canvas">("mannequin");
  const [autoDress, setAutoDress] = useState(false);
  const [lastImg, setLastImg] = useState<string | null>(null);
  const mq = useMannequin();
  const boardRef = useRef<HTMLDivElement | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 8 } }), useSensor(KeyboardSensor));

  useEffect(() => {  // open the most recent saved look (e.g. one the stylist just laid out)
    const latest = looks.data?.[0];
    if (latest && latest.id !== loadedLook) {
      setItems(latest.items.map((i) => ({ product: i.product, x: i.x, y: i.y, w: i.w, z: i.z })));
      setLoadedLook(latest.id);
      setAutoDress(true);
    }
  }, [looks.data, loadedLook]);

  const commit = (next: Item[]) => { setHistory((h) => [...h.slice(-30), items]); setItems(next); };
  const topZ = () => items.reduce((z, i) => Math.max(z, i.z), 0);

  /** Pieces whose on-screen boxes overlap by a meaningful amount (so a layering decision is needed). */
  const overlapping = (pid: string, list: Item[] = items): Item | null => {
    const board = boardRef.current;
    const el = board?.querySelector<HTMLElement>(`[data-pid="${pid}"]`);
    if (!board || !el) return null;
    const a = el.getBoundingClientRect();
    let best: { it: Item; area: number } | null = null;
    for (const it of list) {
      if (it.product.id === pid) continue;
      const o = board.querySelector<HTMLElement>(`[data-pid="${it.product.id}"]`)?.getBoundingClientRect();
      if (!o) continue;
      const w = Math.min(a.right, o.right) - Math.max(a.left, o.left);
      const h = Math.min(a.bottom, o.bottom) - Math.max(a.top, o.top);
      if (w <= 0 || h <= 0) continue;
      const area = (w * h) / Math.min(a.width * a.height, o.width * o.height);
      if (area > 0.15 && (!best || area > best.area)) best = { it, area };
    }
    return best?.it ?? null;
  };
  const maybeAskLayer = (pid: string) => {
    window.requestAnimationFrame(() => {
      const other = overlapping(pid);
      if (other) setAsk({ moved: pid, other: other.product.id });
    });
  };
  const applyLayer = (where: "inside" | "outside") => {
    if (!ask) return;
    const other = items.find((i) => i.product.id === ask.other)!;
    // renumber so the moved piece sits just under (inside) or just over (outside) the other piece
    const order = [...items].sort((a, b) => a.z - b.z).filter((i) => i.product.id !== ask.moved);
    const idx = order.findIndex((i) => i.product.id === other.product.id);
    const moved = items.find((i) => i.product.id === ask.moved)!;
    order.splice(where === "inside" ? idx : idx + 1, 0, moved);
    commit(order.map((i, k) => ({ ...i, z: (k + 1) * 10 })));
    toast(`${moved.product.name} is ${where === "inside" ? "inside, under" : "outside, over"} the ${other.product.name}`);
    setAsk(null);
  };

  const addAt = (p: Product, x?: number, y?: number) => {
    if (items.some((i) => i.product.id === p.id)) { toast(`${p.name} is already on the board`); return; }
    const w = defaultWidth(p);
    const n = items.length;
    // a new piece goes on top, except that a coat or jacket already on the board stays the outer layer
    const outer = items.filter((i) => i.product.category === "outerwear").map((i) => i.z);
    const z = p.category !== "outerwear" && outer.length ? Math.min(...outer) - 1 : topZ() + 10;
    const it: Item = { product: p, w, x: x ?? clamp(8 + (n % 3) * 30, 0, 100 - w), y: y ?? clamp(6 + Math.floor(n / 3) * 30, 0, 80), z };
    commit([...items, it]);
    setSelected(p.id);
    maybeAskLayer(p.id);
  };
  const onDragStart = (e: DragStartEvent) => setActive((e.active.data.current?.product as Product) ?? null);
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    const p = e.active.data.current?.product as Product | undefined;
    const r = boardRef.current?.getBoundingClientRect();
    const t = e.active.rect.current.translated;
    if (p && e.over?.id === "mannequin") { addAt(p); return; }
    if (!p || !r || !t || e.over?.id !== "board") return;
    const w = defaultWidth(p);
    addAt(p, clamp(((t.left - r.left) / r.width) * 100, -5, 100 - w / 2), clamp(((t.top - r.top) / r.height) * 100, -5, 92));
  };
  const onMove = (pid: string, x: number, y: number) => setItems((cur) => cur.map((i) => (i.product.id === pid ? { ...i, x, y } : i)));
  const onResize = (pid: string, w: number) => setItems((cur) => cur.map((i) => (i.product.id === pid ? { ...i, w } : i)));
  const onStart = () => setHistory((h) => [...h.slice(-30), items]);  // snapshot before a move/resize, for undo
  const onMoveEnd = (pid: string) => maybeAskLayer(pid);
  const remove = (pid: string) => { commit(items.filter((i) => i.product.id !== pid)); setSelected(null); };
  const nudge = (pid: string, f: (i: Item) => Item) => commit(items.map((i) => (i.product.id === pid ? f(i) : i)));
  const restack = (pid: string, dir: 1 | -1) => {
    const order = [...items].sort((a, b) => a.z - b.z);
    const k = order.findIndex((i) => i.product.id === pid);
    const j = k + dir;
    if (j < 0 || j >= order.length) return;
    [order[k], order[j]] = [order[j], order[k]];
    commit(order.map((i, n) => ({ ...i, z: (n + 1) * 10 })));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>, pid: string) => {
    const step = e.shiftKey ? 5 : 1;
    const map: Record<string, (i: Item) => Item> = {
      ArrowLeft: (i) => ({ ...i, x: i.x - step }), ArrowRight: (i) => ({ ...i, x: i.x + step }),
      ArrowUp: (i) => ({ ...i, y: i.y - step }), ArrowDown: (i) => ({ ...i, y: i.y + step }),
      "+": (i) => ({ ...i, w: clamp(i.w + 2, 8, 90) }), "=": (i) => ({ ...i, w: clamp(i.w + 2, 8, 90) }), "-": (i) => ({ ...i, w: clamp(i.w - 2, 8, 90) }),
    };
    if (map[e.key]) { e.preventDefault(); nudge(pid, map[e.key]); }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(pid); }
  };

  const toBuy = items.filter((i) => !owned.has(i.product.id));
  const total = toBuy.reduce((s, i) => s + i.product.price_inr, 0);
  const sel = items.find((i) => i.product.id === selected);

  const style = useMutation({ mutationFn: (body: { formality?: string }) => api.post<StyleResp>(`${base}/style`, body) });
  const save = useMutation({
    mutationFn: () => api.post<Look>(`${base}/looks`, { name: `Look ${(looks.data?.length ?? 0) + 1}`,
      placements: items.map((i) => ({ product_id: i.product.id, x: i.x, y: i.y, w: i.w, z: i.z })) }),
    onSuccess: (l) => { setLoadedLook(l.id); qc.invalidateQueries({ queryKey: ["looks", folderId ?? "rail"] }); toast("Look saved"); },
  });
  const addToCart = useMutation({
    mutationFn: (list: { product_id: string; size?: string }[]) => api.post<{ added: unknown[]; needs_size: { product: Product; reason: string }[]; failed: unknown[] }>(
      folderId ? `/cart/look/${folderId}` : "/rail/cart", { items: list }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["me"] }); qc.invalidateQueries({ queryKey: ["cart"] });
      setNeedSizes(r.needs_size.length ? r.needs_size : null);
      toast(`${r.added.length} piece${r.added.length === 1 ? "" : "s"} added to cart${r.failed.length ? ` (${r.failed.length} unavailable)` : ""}`);
    },
  });
  const applyOption = (o: StyleOption) => {
    const byId = Object.fromEntries(o.items.map((i) => [i.product.id, i.product]));
    commit(o.layout.map((l) => ({ product: byId[l.product_id], x: l.x, y: l.y, w: l.w, z: l.z })));
    setAutoDress(true);
  };

  // ---- the mannequin: dressed in the board's pieces, inside -> outside (the board's layer order)
  const layered = [...items].sort((a, b) => a.z - b.z);
  const order = layered.map((i) => i.product.id);
  const lookKey = order.join(",");
  const mqKey = mq.data ? `${mq.data.body_type}-${mq.data.skin_tone}` : "";
  const cachedTry = useQuery({ queryKey: ["tryon", mqKey, lookKey], enabled: !!order.length && !!mq.data, staleTime: Infinity,
    queryFn: () => api.post<TryOn>("/tryon", { product_ids: order, cached_only: true }) });
  const dress = useMutation({
    mutationFn: (ids: string[]) => api.post<TryOn>("/tryon", { product_ids: ids }),
    onSuccess: (r, ids) => { qc.setQueryData(["tryon", mqKey, ids.join(",")], r); setLastImg(r.image_url); },
  });
  const dressed = order.length ? cachedTry.data?.image_url ?? null : null;
  useEffect(() => { if (dressed) setLastImg(dressed); else if (!order.length) setLastImg(null); }, [dressed, order.length]);
  useEffect(() => {
    if (!autoDress || !order.length || !cachedTry.isFetched) return;
    setAutoDress(false);
    if (!dressed && !dress.isPending && view === "mannequin") dress.mutate(order);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoDress, cachedTry.isFetched, dressed, lookKey]);

  if (folder.error) return <ErrorBox error={folder.error} onRetry={() => folder.refetch()} />;
  if (folderId && !folder.data) return <Loading label="Opening your style board" />;
  const title = folder.data?.name ?? "Your rail";
  const askMoved = ask && items.find((i) => i.product.id === ask.moved);
  const askOther = ask && items.find((i) => i.product.id === ask.other);

  return (
    <>
      <Link to={folderId ? `/folders/${folderId}` : "/"} className="btn btn-ghost btn-sm" style={{ marginLeft: -8 }}><Icon name="back" size={16} /> {folderId ? title : "Wardrobe"}</Link>
      <span className="eyebrow" style={{ display: "block", marginTop: 4 }}>Style board</span>
      <h1>{title}</h1>
      {!folderId && <p className="muted" style={{ margin: "4px 0 0" }}>Everything you've bought, bagged or wishlisted. Mix what you own with what you're eyeing.</p>}
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragCancel={() => setActive(null)} onDragEnd={onDragEnd}>
        <div className="wardrobe-layout section" style={{ marginTop: 16 }}>
          <section className="stack wardrobe-tray" style={{ gap: 8 }}>
            <div className="row-between"><h3>{folderId ? "Your hangers" : "Your rail"}</h3><span className="small muted">Drag onto the board, or tap “Add”</span></div>
            {tray.isLoading && <Loading />}
            {tray.data?.items.length === 0 && <div className="empty"><p className="muted" style={{ margin: 0 }}>{folderId ? "No hangers yet. Hang pieces from your rail or an inspo first." : "Your rail is empty. Heart pieces in the Shop or link your membership."}</p></div>}
            <div className="tray-grid">{tray.data?.items.map((it) => <TrayCard key={it.key} item={it} onAdd={(p) => addAt(p)} />)}</div>
          </section>

          <div className="stack wardrobe-stage">
            <div className="seg" role="tablist" aria-label="Board view">
              <button role="tab" aria-selected={view === "mannequin"} onClick={() => setView("mannequin")}>Mannequin</button>
              <button role="tab" aria-selected={view === "canvas"} onClick={() => setView("canvas")}>Flat lay</button>
            </div>
            {view === "mannequin" && mq.data && (
              <>
                <MannequinDrop>
                  <img src={dressed ?? lastImg ?? mannequinUrl(mq.data)} alt={items.length ? `Your mannequin wearing ${layered.map((i) => i.product.name).join(", ")}` : "Your mannequin"}
                    className={`mq-render ${!dressed && lastImg && items.length ? "stale" : ""} ${dressed || lastImg ? "" : "bare"}`} />
                  {dress.isPending && (
                    <div className="mq-overlay" role="status"><span className="spinner" /> Dressing your mannequin… about 10 seconds</div>
                  )}
                  {!items.length && <div className="mq-hint small">Add pieces from {folderId ? "your hangers" : "your rail"} and we'll dress your mannequin in them.</div>}
                  {!!items.length && !dressed && !dress.isPending && (
                    <button className="btn btn-primary mq-dress" onClick={() => dress.mutate(order)}>
                      <Icon name="sparkle" size={16} /> {lastImg ? "Update the mannequin" : "Dress the mannequin"}</button>
                  )}
                </MannequinDrop>
                {dress.error && <ErrorBox error={dress.error} />}
                {!!items.length && (
                  <div className="card pad stack" style={{ gap: 6 }}>
                    <div className="row-between"><b className="small">Layers</b><span className="small muted">inside first, outside last</span></div>
                    {layered.map((i, k) => (
                      <div key={i.product.id} className="mq-layer">
                        <span className="small muted" style={{ width: 16 }}>{k + 1}</span>
                        <img src={i.product.image_url} alt="" />
                        <button className="mq-layer-name small" onClick={() => setProduct(i.product.id)}>{i.product.name}</button>
                        <button className="icon-btn" disabled={k === 0} aria-label={`Wear ${i.product.name} further inside`} title="Further inside" onClick={() => restack(i.product.id, -1)}>↑</button>
                        <button className="icon-btn" disabled={k === layered.length - 1} aria-label={`Wear ${i.product.name} further outside`} title="Further outside" onClick={() => restack(i.product.id, 1)}>↓</button>
                        <button className="icon-btn" aria-label={`Remove ${i.product.name}`} onClick={() => remove(i.product.id)}><Icon name="trash" size={16} /></button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
            {view === "canvas" && <Board items={items} selected={selected} setSelected={setSelected} onStart={onStart} onMove={onMove} onMoveEnd={onMoveEnd}
              onResize={onResize} boardRef={boardRef} onKey={onKey} />}
            {view === "canvas" && sel && (
              <div className="row board-toolbar" role="toolbar" aria-label={`${sel.product.name} controls`}>
                <b className="small" style={{ flex: 1, minWidth: 120 }}>{sel.product.name}</b>
                <button className="btn btn-sm" onClick={() => restack(sel.product.id, 1)} title="Bring forward (wear outside)">Outside ↑</button>
                <button className="btn btn-sm" onClick={() => restack(sel.product.id, -1)} title="Send back (wear inside)">Inside ↓</button>
                <button className="btn btn-sm" aria-label="Smaller" onClick={() => nudge(sel.product.id, (i) => ({ ...i, w: clamp(i.w - 4, 8, 90) }))}>−</button>
                <button className="btn btn-sm" aria-label="Bigger" onClick={() => nudge(sel.product.id, (i) => ({ ...i, w: clamp(i.w + 4, 8, 90) }))}>+</button>
                <button className="btn btn-sm" onClick={() => setProduct(sel.product.id)}>Details</button>
                <button className="icon-btn" aria-label={`Remove ${sel.product.name}`} onClick={() => remove(sel.product.id)}><Icon name="trash" size={16} /></button>
              </div>
            )}
            {(
              <div className="row" style={{ justifyContent: "center", gap: 6 }}>
                <button className="btn btn-sm" disabled={!history.length} onClick={() => { setItems(history[history.length - 1]); setHistory((h) => h.slice(0, -1)); }}>
                  <Icon name="undo" size={16} /> Undo</button>
                <button className="btn btn-sm" disabled={!items.length} onClick={() => commit([])}><Icon name="trash" size={16} /> Clear</button>
                <button className="btn btn-sm" disabled={!items.length || save.isPending} onClick={() => save.mutate()}><Icon name="check" size={16} /> Save look</button>
              </div>
            )}
            {items.length > 0 && (
              <div className="card pad stack" style={{ gap: 8 }}>
                <div className="row-between"><b>{toBuy.length === 0 ? "All from your wardrobe. Nothing to buy." : toBuy.length < items.length ? `To complete the look (${items.length - toBuy.length} already yours)` : "On the board"}</b>
                  {toBuy.length > 0 && <span className="price">{inr(total)}</span>}</div>
                {toBuy.length > 0 && (
                <button className="btn btn-primary" onClick={() => addToCart.mutate(toBuy.map((i) => ({ product_id: i.product.id })))} disabled={addToCart.isPending}>
                  {addToCart.isPending ? <span className="spinner" /> : <Icon name="bag" />} {toBuy.length < items.length ? `Add ${toBuy.length} piece${toBuy.length === 1 ? "" : "s"} to cart` : "Add full look to cart"}
                </button>)}
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
                  <button key={k} className="chip" onClick={() => style.mutate({ formality: k })} disabled={style.isPending}>{l}</button>))}
              </div>
              {style.error && <ErrorBox error={style.error} />}
              {style.data?.message && <div className="alert">{style.data.message}</div>}
              {style.data?.options.map((o, k) => (
                <button key={k} className="card" style={{ padding: 10, textAlign: "left", cursor: "pointer" }} onClick={() => applyOption(o)}>
                  <div className="row-between"><b>Look {k + 1}</b>
                    {o.owned_count === o.items.length ? <span className="chip chip-sage">All yours</span>
                      : <span className="small"><Price price={o.total_inr} />{o.owned_count ? " to buy" : ""}</span>}</div>
                  <div className="row" style={{ gap: 4, margin: "6px 0" }}>
                    {o.items.map((i) => <img key={i.product.id} src={i.product.image_url} alt={i.product.name} title={i.why}
                      style={{ width: 44, height: 44, objectFit: "contain", background: "#f4efe8", borderRadius: 8 }} />)}
                  </div>
                  <div className="small">{o.reason}</div>
                  <div className="small muted" style={{ marginTop: 4 }}>Tap to lay it out on the board</div>
                </button>
              ))}
              {!!style.data?.complete_the_look.length && (
                <div className="stack" style={{ gap: 6 }}>
                  <b className="small">Complete the look</b>
                  {style.data.complete_the_look.map((c) => (
                    <div key={c.product.id} className="card" style={{ padding: 8, display: "flex", gap: 8, alignItems: "center" }}>
                      <img src={c.product.image_url} alt="" style={{ width: 48, height: 48, objectFit: "contain", background: "#f4efe8", borderRadius: 8 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="small" style={{ fontWeight: 600 }}>{c.product.name}</div>
                        <div className="small muted">{inr(c.product.price_inr)}{c.pairs_with_past ? ` · goes with your ${c.pairs_with_past}` : ""}</div>
                      </div>
                      <button className="btn btn-sm" onClick={() => addAt(c.product)}>Add</button>
                    </div>
                  ))}
                </div>
              )}
            </section>
            {!!looks.data?.length && (
              <section className="stack" style={{ gap: 8 }}>
                <h3>Saved looks</h3>
                {looks.data.map((l) => (
                  <button key={l.id} className="card" style={{ padding: 10, textAlign: "left", cursor: "pointer" }}
                    onClick={() => { commit(l.items.map((i) => ({ ...i }))); setAutoDress(true); }}>
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

      {ask && askMoved && askOther && (
        <Modal title="How should these layer?" onClose={() => setAsk(null)}>
          <div className="stack">
            <div className="row" style={{ justifyContent: "center", gap: 16 }}>
              {[askMoved, askOther].map((i) => (
                <div key={i.product.id} style={{ textAlign: "center", width: 120 }}>
                  <img src={i.product.image_url} alt="" style={{ width: 96, height: 96, objectFit: "contain", margin: "0 auto", background: "#f4efe8", borderRadius: 10 }} />
                  <div className="small" style={{ marginTop: 4 }}>{i.product.name}</div>
                </div>
              ))}
            </div>
            <p style={{ margin: 0 }}>You placed the <b>{askMoved.product.name}</b> on the <b>{askOther.product.name}</b>. Should it be worn inside or outside?</p>
            <div className="row">
              <button className="btn" style={{ flex: 1 }} onClick={() => applyLayer("inside")}>Inside (under the {askOther.product.subcategory_label.toLowerCase()})</button>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => applyLayer("outside")}>Outside (over the {askOther.product.subcategory_label.toLowerCase()})</button>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => setAsk(null)}>Keep as is</button>
          </div>
        </Modal>
      )}
      {product && <ProductModal productId={product} onClose={() => setProduct(null)} />}
      {needSizes && <SizePrompt items={needSizes} onClose={() => setNeedSizes(null)}
        onDone={(sizes) => addToCart.mutate(Object.entries(sizes).map(([product_id, size]) => ({ product_id, size })))} />}
    </>
  );
}
