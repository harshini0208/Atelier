import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MouseEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useVocab } from "../components/Layout";
import ProductModal from "../components/ProductModal";
import { ErrorBox, Icon, Loading, Modal, Price, SkeletonGrid, useToast } from "../components/ui";
import type { FolderSummary, Inspo, MatchItem, Piece, Product } from "../types";

type PieceMatches = {
  for_you: MatchItem[]; also_view: MatchItem[]; closest: MatchItem[]; covered: boolean;
  piece: { id: number; name: string; crop_url: string | null; subcategory_label: string };
  hanger: { id: number; chosen_product_id: string | null } | null; gap_message?: string;
};

function Boxes({ inspo, active, hung, pick }: { inspo: Inspo; active: number | null; hung: Set<number>; pick: (id: number) => void }) {
  return (
    <>
      {inspo.pieces.filter((p) => p.box && !(p.manual && p.box[0] === 0 && p.box[2] === 1000)).map((p) => {
        const [y0, x0, y1, x1] = p.box!;
        return (
          <button key={p.id} className="box" aria-pressed={active === p.id || hung.has(p.id)} onClick={(e) => { e.stopPropagation(); pick(p.id); }}
            aria-label={`See store matches for ${p.name}`}
            style={{ top: `${y0 / 10}%`, left: `${x0 / 10}%`, height: `${(y1 - y0) / 10}%`, width: `${(x1 - x0) / 10}%`,
              outline: active === p.id ? "3px solid var(--ink)" : undefined }}>
            <span className="box-label">{hung.has(p.id) ? "✓ " : ""}{p.subcategory_label}</span>
          </button>
        );
      })}
    </>
  );
}

function AddPieceDialog({ point, inspoId, onClose }: { point: [number, number] | null; inspoId: number; onClose: () => void }) {
  const vocab = useVocab();
  const qc = useQueryClient();
  const [sub, setSub] = useState("");
  const [color, setColor] = useState("");
  const add = useMutation({
    mutationFn: () => api.post<Inspo>(`/inspo/${inspoId}/pieces`, { subcategory: sub, color, point }),
    onSuccess: (d) => { qc.setQueryData(["inspo", inspoId], d); onClose(); },
  });
  return (
    <Modal title="Add a piece" onClose={onClose}>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
        <p className="muted small" style={{ margin: 0 }}>Tell us what the piece is and we'll find it in the store.</p>
        <div className="field">
          <label htmlFor="sub">What is it?</label>
          <select id="sub" className="select" value={sub} onChange={(e) => setSub(e.target.value)} required>
            <option value="">Choose a piece</option>
            {vocab.data?.categories.map((c) => (
              <optgroup key={c.key} label={c.label}>{c.subcategories.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</optgroup>
            ))}
          </select>
        </div>
        <div className="field">
          <span className="label">Colour</span>
          <div className="chips">{vocab.data?.colors.map((c) => (
            <button type="button" key={c.key} className="chip" aria-pressed={color === c.key} onClick={() => setColor(c.key)}>
              <span className="swatch" style={{ background: c.hex }} />{c.label}
            </button>))}</div>
        </div>
        {add.error && <ErrorBox error={add.error} />}
        <button className="btn btn-primary" disabled={!sub || !color || add.isPending}>Add piece</button>
      </form>
    </Modal>
  );
}

function MatchCard({ item, chosen, onHang, onDetails, busy }: {
  item: MatchItem; chosen: boolean; onHang: () => void; onDetails: () => void; busy: boolean;
}) {
  const p = item.product;
  return (
    <div className="product-card" style={{ cursor: "default", borderColor: chosen ? "var(--sage)" : undefined, boxShadow: chosen ? "0 0 0 1px var(--sage)" : undefined }}>
      <button className="product-img" onClick={onDetails} aria-label={`Details for ${p.name}`} style={{ border: 0, cursor: "pointer" }}>
        <img src={p.image_url} alt={p.name} loading="lazy" />
      </button>
      <div className="product-body">
        <span className="name">{p.name}</span>
        <Price price={p.price_inr} mrp={p.mrp_inr} />
        {item.reasons.length > 0
          ? <div className="chips">{item.reasons.map((r) => <span key={r.label} className="chip chip-amber">{r.label}</span>)}</div>
          : <div className="chips">{item.why.slice(0, 2).map((w) => <span key={w} className="chip chip-sage">{w}</span>)}</div>}
        <button className={`btn btn-sm ${chosen ? "" : "btn-primary"}`} onClick={onHang} disabled={busy || chosen} style={{ marginTop: "auto" }}>
          {chosen ? <><Icon name="check" size={14} /> On your hanger</> : <><Icon name="hanger" size={14} /> Hang this</>}
        </button>
      </div>
    </div>
  );
}

function PieceMatchesPanel({ inspo, pieceId, folderId, onHung }: { inspo: Inspo; pieceId: number; folderId: number; onHung: (name: string) => void }) {
  const qc = useQueryClient();
  const [details, setDetails] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["piece-matches", pieceId], queryFn: () => api.get<PieceMatches>(`/inspo/${inspo.id}/pieces/${pieceId}/matches`) });
  const hang = useMutation({
    mutationFn: (p: Product | null) => api.post(`/inspo/${inspo.id}/pieces/${pieceId}/hang`, { product_id: p?.id ?? null, folder_id: folderId }),
    onSuccess: (_d, p) => {
      qc.invalidateQueries({ queryKey: ["piece-matches", pieceId] });
      qc.invalidateQueries({ queryKey: ["inspo", inspo.id] });
      qc.invalidateQueries({ queryKey: ["folder"] });
      qc.invalidateQueries({ queryKey: ["folders"] });
      onHung(p ? p.name : "wish");
    },
  });
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <SkeletonGrid n={3} />;
  const m = q.data;
  const chosen = m.hanger?.chosen_product_id ?? null;
  const tier = (title: string, hint: string, items: MatchItem[]) => items.length > 0 && (
    <section className="stack" style={{ gap: 8 }}>
      <div className="row-between"><h3>{title}</h3><span className="small muted">{hint}</span></div>
      <div className="product-grid">
        {items.map((i) => <MatchCard key={i.product.id} item={i} chosen={chosen === i.product.id} busy={hang.isPending}
          onHang={() => hang.mutate(i.product)} onDetails={() => setDetails(i.product.id)} />)}
      </div>
    </section>
  );
  return (
    <div className="stack" style={{ gap: 18 }}>
      {m.gap_message && <div className="alert">{m.gap_message}</div>}
      {tier("For you", "Fits the look and your preferences", m.for_you)}
      {tier("Also view", "Great match, outside a preference", m.also_view)}
      {tier("Closest from this store", "Not a close match", m.closest)}
      {!m.covered && (
        <button className="btn" onClick={() => hang.mutate(null)} disabled={hang.isPending || (m.hanger !== null && !chosen)}>
          <Icon name="sparkle" size={16} /> {m.hanger && !chosen ? "Saved as a wish" : "Save as a wish (we'll tell you if it arrives)"}
        </button>
      )}
      {hang.error && <ErrorBox error={hang.error} />}
      {details && <ProductModal productId={details} onClose={() => setDetails(null)} />}
    </div>
  );
}

export default function InspoReview() {
  const { id } = useParams();
  const inspoId = Number(id);
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const q = useQuery({ queryKey: ["inspo", inspoId], queryFn: () => api.get<Inspo>(`/inspo/${inspoId}`) });
  const folders = useQuery({ queryKey: ["folders"], queryFn: () => api.get<FolderSummary[]>("/folders") });
  const [active, setActive] = useState<number | null>(null);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [tapMode, setTapMode] = useState(false);
  const [tapPoint, setTapPoint] = useState<[number, number] | null | undefined>(undefined);
  const matchesRef = useRef<HTMLDivElement>(null);
  const inspo = q.data;
  useEffect(() => { if (inspo && folderId === null) setFolderId(inspo.folder_id); }, [inspo, folderId]);

  const hung = new Set((inspo?.pieces ?? []).filter((p) => p.selected).map((p) => p.id));
  const pick = (pid: number) => {
    setActive(pid);
    window.setTimeout(() => matchesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };
  const done = useMutation({
    mutationFn: () => api.post(`/inspo/${inspoId}/select`, { piece_ids: [...hung], folder_id: folderId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["folder"] }); nav(`/folders/${folderId ?? inspo!.folder_id}`); },
  });

  const onImageClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!tapMode) return;
    const r = e.currentTarget.getBoundingClientRect();
    setTapPoint([Math.round(((e.clientY - r.top) / r.height) * 1000), Math.round(((e.clientX - r.left) / r.width) * 1000)]);
    setTapMode(false);
  };

  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!inspo) return <Loading label="Opening your inspo" />;
  const activePiece: Piece | undefined = inspo.pieces.find((p) => p.id === active);

  return (
    <>
      <Link to={`/folders/${inspo.folder_id}`} className="btn btn-ghost btn-sm" style={{ marginLeft: -8 }}><Icon name="back" size={16} /> Back to folder</Link>
      <div className="inspo-layout" style={{ marginTop: 8 }}>
        <div className="stack inspo-image-col">
          <div className={`inspo-frame ${tapMode ? "tap-mode" : ""}`} onClick={onImageClick}>
            <img src={inspo.image_url} alt="Your inspiration screenshot" />
            {!tapMode && <Boxes inspo={inspo} active={active} hung={hung} pick={pick} />}
          </div>
          <div className="row" style={{ justifyContent: "center" }}>
            <button className={`btn btn-sm ${tapMode ? "btn-primary" : ""}`} onClick={() => setTapMode((t) => !t)} aria-pressed={tapMode}>
              <Icon name="plus" size={16} /> {tapMode ? "Tap the piece on the image…" : "Tap to add a missed piece"}
            </button>
          </div>
        </div>

        <div className="stack">
          <div>
            <span className="eyebrow">Tap a piece you love</span>
            <h1>{inspo.pieces.length ? `${inspo.pieces.length} piece${inspo.pieces.length === 1 ? "" : "s"} in this look` : "Let's find the pieces"}</h1>
            <p className="muted" style={{ margin: "6px 0 0" }}>
              Tap a piece to see what Urban Thread has for it, then hang the one you want. Your hangers hold real store pieces.
            </p>
          </div>
          {inspo.message && <div className={`alert ${inspo.status === "analyzed" ? "" : "alert-rose"}`}>{inspo.message}</div>}
          {inspo.pieces.length > 0 && (
            <div className="chips" role="tablist" aria-label="Pieces in this look">
              {inspo.pieces.map((p) => (
                <button key={p.id} role="tab" aria-selected={active === p.id} className={`chip ${hung.has(p.id) ? "chip-sage" : ""}`}
                  aria-pressed={active === p.id} onClick={() => pick(p.id)} style={{ padding: "4px 10px 4px 4px" }}>
                  {p.crop_url && <img src={p.crop_url} alt="" style={{ width: 28, height: 28, objectFit: "contain", borderRadius: 6, background: "#fff" }} />}
                  {hung.has(p.id) ? "✓ " : ""}{p.name}
                </button>
              ))}
            </div>
          )}
          {folders.data && folders.data.length > 1 && (
            <div className="row small">
              <label htmlFor="to-folder" className="muted">Hang in</label>
              <select id="to-folder" className="select" style={{ width: "auto", minHeight: 36 }} value={folderId ?? ""}
                onChange={(e) => setFolderId(Number(e.target.value))}>
                {folders.data.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
          )}
          <div ref={matchesRef} style={{ scrollMarginTop: 80 }}>
            {activePiece ? (
              <div className="card pad stack">
                <div className="row" style={{ flexWrap: "nowrap" }}>
                  {activePiece.crop_url && <img src={activePiece.crop_url} alt="" style={{ width: 52, height: 52, objectFit: "contain", background: "#efe8de", borderRadius: 8 }} />}
                  <div><div className="eyebrow">In store for</div><h2 style={{ fontSize: 20 }}>{activePiece.name}</h2></div>
                </div>
                <PieceMatchesPanel inspo={inspo} pieceId={activePiece.id} folderId={folderId ?? inspo.folder_id!}
                  onHung={(n) => toast(n === "wish" ? "Saved as a wish" : `${n} is on your hanger`)} />
              </div>
            ) : inspo.pieces.length > 0 && (
              <div className="empty"><p className="muted" style={{ margin: 0 }}>Tap a box on the image or a piece above to see what's in store.</p></div>
            )}
          </div>
          <button className="btn btn-primary btn-block" onClick={() => done.mutate()} disabled={done.isPending}>
            {done.isPending ? <span className="spinner" /> : <Icon name="check" />}
            {hung.size ? `Done: ${hung.size} piece${hung.size === 1 ? "" : "s"} on hangers` : "Done"}
          </button>
          {done.error && <ErrorBox error={done.error} />}
          {hung.size > 0 && <span className="small muted" style={{ textAlign: "center" }}>
            Hung so far: {inspo.pieces.filter((p) => p.selected).map((p) => p.name).join(", ")}
          </span>}
        </div>
      </div>
      {tapPoint !== undefined && <AddPieceDialog point={tapPoint} inspoId={inspoId} onClose={() => setTapPoint(undefined)} />}
    </>
  );
}
