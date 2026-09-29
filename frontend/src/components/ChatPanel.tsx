import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, inr } from "../api";
import type { Product } from "../types";
import ProductModal from "./ProductModal";
import { ErrorBox, Icon, useToast } from "./ui";

type OutfitItem = { product: Product; piece_name: string; why: string; reasons: { label: string }[]; hanger_id: number };
type Outfit = { items: OutfitItem[]; total_inr: number; max_total_inr: number | null; within_budget: boolean; over_by_inr: number;
  occasion: string | null; gaps: string[]; dropped?: string[] };
type Msg = {
  id: number; role: "user" | "assistant"; content: string; created_at: string;
  payload: { source?: string; products?: Product[]; outfit?: Outfit | null; actions?: string[];
    pending_preferences?: { summary: string } | null };
};

const SUGGESTIONS = ["Make it work for a beach wedding under ₹5,000", "Make it more casual", "Put it on the mannequin",
  "Add the look to my cart"];

function useFolderId(): number | null {
  const { pathname } = useLocation();
  const m = pathname.match(/^\/folders\/(\d+)/);
  return m ? Number(m[1]) : null;
}

function OutfitCard({ o, folderId, onOpen }: { o: Outfit; folderId: number | null; onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const place = useMutation({
    mutationFn: () => api.post(`/folders/${folderId}/looks`, {
      name: o.occasion ? `For ${o.occasion}` : "Stylist pick",
      placements: o.items.map((i) => ({ product_id: i.product.id, slot: i.product.slot })), reason: o.occasion ?? "" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["looks", folderId] }); nav(`/folders/${folderId}/wardrobe`); },
  });
  const cart = useMutation({
    mutationFn: () => api.post<{ added: unknown[]; needs_size: unknown[] }>(`/cart/look/${folderId}`, {
      items: o.items.map((i) => ({ product_id: i.product.id })) }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["me"] }); qc.invalidateQueries({ queryKey: ["cart"] });
      toast(`Added ${r.added.length} to cart${r.needs_size.length ? `, ${r.needs_size.length} need a size` : ""}`);
    },
  });
  return (
    <div className="card" style={{ padding: 10, marginTop: 8 }}>
      <div className="row-between small" style={{ marginBottom: 6 }}>
        <b>{o.occasion ? `Look for ${o.occasion}` : "Your look"}</b>
        <span className={`chip ${o.within_budget ? "chip-sage" : "chip-amber"}`}>
          {inr(o.total_inr)}{o.max_total_inr ? (o.within_budget ? " · in budget" : ` · ${inr(o.over_by_inr)} over`) : ""}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(76px, 1fr))", gap: 6 }}>
        {o.items.map((i) => (
          <button key={i.product.id} className="product-card" onClick={() => onOpen(i.product.id)} title={i.why}>
            <div className="product-img" style={{ padding: 4 }}><img src={i.product.image_url} alt={i.product.name} /></div>
            <div style={{ padding: "4px 6px 6px", fontSize: 11, lineHeight: 1.25 }}>
              <div style={{ fontWeight: 600 }}>{i.product.name}</div>
              <div>{inr(i.product.price_inr)}</div>
              {i.reasons[0] && <div style={{ color: "var(--amber)" }}>{i.reasons[0].label}</div>}
            </div>
          </button>
        ))}
      </div>
      {(o.gaps.length > 0 || (o.dropped?.length ?? 0) > 0) && (
        <div className="small muted" style={{ marginTop: 6 }}>
          {o.dropped?.length ? `Left out to fit the budget: ${o.dropped.join(", ")}. ` : ""}
          {o.gaps.length ? `Not in store: ${o.gaps.join(", ")}.` : ""}
        </div>
      )}
      {folderId && (
        <div className="row" style={{ marginTop: 8, gap: 6 }}>
          <button className="btn btn-sm" onClick={() => place.mutate()} disabled={place.isPending}><Icon name="mannequin" size={16} /> Try on</button>
          <button className="btn btn-sm btn-primary" onClick={() => cart.mutate()} disabled={cart.isPending}><Icon name="bag" size={16} /> Add look to cart</button>
        </div>
      )}
    </div>
  );
}

function Message({ m, folderId, onOpen }: { m: Msg; folderId: number | null; onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const confirm = useMutation({
    mutationFn: (accept: boolean) => api.post<Msg>(`/chat/${m.id}/confirm`, { accept }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["chat"] }); qc.invalidateQueries({ queryKey: ["prefs"] });
      qc.invalidateQueries({ queryKey: ["matches"] }); qc.invalidateQueries({ queryKey: ["folder"] }); },
  });
  const p = m.payload ?? {};
  const mine = m.role === "user";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: mine ? "flex-end" : "flex-start" }}>
      <div style={{ maxWidth: "92%", padding: "9px 12px", borderRadius: 14, whiteSpace: "pre-wrap", fontSize: 14,
        background: mine ? "var(--ink)" : "var(--surface)", color: mine ? "#fbf8f4" : "var(--ink)",
        border: mine ? 0 : "1px solid var(--line)", borderBottomRightRadius: mine ? 4 : 14, borderBottomLeftRadius: mine ? 14 : 4 }}>
        {m.content}
      </div>
      {p.outfit && p.outfit.items.length > 0 && <div style={{ width: "100%" }}><OutfitCard o={p.outfit} folderId={folderId} onOpen={onOpen} /></div>}
      {p.products && p.products.length > 0 && (
        <div style={{ display: "flex", gap: 6, overflowX: "auto", width: "100%", marginTop: 8, paddingBottom: 4 }}>
          {p.products.map((pr) => (
            <button key={pr.id} className="product-card" style={{ flex: "0 0 96px" }} onClick={() => onOpen(pr.id)}>
              <div className="product-img" style={{ padding: 4 }}><img src={pr.image_url} alt={pr.name} /></div>
              <div style={{ padding: "4px 6px 6px", fontSize: 11, lineHeight: 1.25 }}><b>{pr.name}</b><br />{inr(pr.price_inr)}</div>
            </button>
          ))}
        </div>
      )}
      {p.pending_preferences && (
        <div className="card" style={{ padding: 10, marginTop: 8, width: "100%" }}>
          <div className="small"><b>Update your preferences?</b> {p.pending_preferences.summary}</div>
          <div className="row" style={{ marginTop: 8, gap: 6 }}>
            <button className="btn btn-sm btn-primary" onClick={() => confirm.mutate(true)} disabled={confirm.isPending}>Confirm</button>
            <button className="btn btn-sm" onClick={() => confirm.mutate(false)} disabled={confirm.isPending}>No thanks</button>
          </div>
        </div>
      )}
      {p.actions?.map((a) => <span key={a} className="chip chip-sage" style={{ marginTop: 6 }}><Icon name="check" size={12} /> {a}</span>)}
    </div>
  );
}

export default function ChatPanel() {
  const folderId = useFolderId();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [product, setProduct] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const key = ["chat", folderId];
  const q = useQuery({ queryKey: key, queryFn: () => api.get<Msg[]>(`/chat${folderId ? `?folder_id=${folderId}` : ""}`) });
  const send = useMutation({
    mutationFn: (message: string) => api.post<Msg>("/chat", { message, folder_id: folderId }),
    onMutate: (message) => {
      qc.setQueryData<Msg[]>(key, (old) => [...(old ?? []), { id: -Date.now(), role: "user", content: message, created_at: "", payload: {} }]);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: key });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["looks"] });
      qc.invalidateQueries({ queryKey: ["prefs"] });
    },
  });
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [q.data, send.isPending, open]);
  // on phones the chat is a full-screen sheet: close it when an action navigates (e.g. "Try on")
  const { pathname } = useLocation();
  useEffect(() => { setOpen(false); }, [pathname]);

  const submit = (e?: FormEvent, value?: string) => {
    e?.preventDefault();
    const msg = (value ?? text).trim();
    if (!msg || send.isPending) return;
    setText("");
    send.mutate(msg);
  };

  const body = (
    <>
      <div className="row-between" style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
        <div>
          <div className="eyebrow">Urban Thread</div>
          <h3 style={{ fontSize: 18 }}>Your stylist</h3>
        </div>
        <button className="icon-btn chat-close" onClick={() => setOpen(false)} aria-label="Close stylist"><Icon name="x" /></button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 10 }} aria-live="polite">
        {q.error && <ErrorBox error={q.error} onRetry={() => q.refetch()} />}
        {q.data?.map((m) => <Message key={m.id} m={m} folderId={folderId} onOpen={setProduct} />)}
        {send.isPending && <div className="row small muted"><span className="spinner" /> Styling…</div>}
        {send.error && <ErrorBox error={send.error} />}
        <div ref={endRef} />
      </div>
      <div style={{ padding: "8px 12px 12px", borderTop: "1px solid var(--line)" }}>
        {folderId && (
          <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8 }}>
            {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => submit(undefined, s)} disabled={send.isPending}>{s}</button>)}
          </div>
        )}
        <form onSubmit={submit} className="row" style={{ flexWrap: "nowrap", gap: 6 }}>
          <label htmlFor="chat-input" className="sr-only">Message the stylist</label>
          <input id="chat-input" className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={800}
            placeholder={folderId ? "Occasion, budget, how you'll wear it…" : "Ask me to find something…"} />
          <button className="btn btn-primary" disabled={!text.trim() || send.isPending} aria-label="Send">
            <Icon name="arrow" />
          </button>
        </form>
      </div>
      {product && <ProductModal productId={product} onClose={() => setProduct(null)} />}
    </>
  );

  return (
    <>
      <aside className={`chat-panel ${open ? "open" : ""}`} aria-label="Stylist chat">{body}</aside>
      {!open && (
        <button className="chat-fab btn btn-primary" onClick={() => setOpen(true)} aria-label="Open stylist chat">
          <Icon name="sparkle" /> Stylist
        </button>
      )}
    </>
  );
}
