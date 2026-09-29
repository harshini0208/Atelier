import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, inr } from "../api";
import HangerDrawer from "../components/HangerDrawer";
import UploadZone from "../components/UploadZone";
import { CoverageLine, ErrorBox, Icon, Loading, useToast } from "../components/ui";
import type { FolderDetail, FolderSummary, Hanger } from "../types";

function HangerHook() {
  return (
    <svg className="hanger-hook" viewBox="0 0 44 22" aria-hidden>
      <path d="M22 1.5a3 3 0 0 1 3 3c0 2.2-3 2.4-3 4.8V10M22 10 4 20.5h36z" fill="none" stroke="#8d7f6c" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HangerCard({ h, onOpen }: { h: Hanger; onOpen: () => void }) {
  // the hanger holds the real store piece; the inspo crop is only a small reminder of where it came from
  const product = h.chosen_product;
  return (
    <button className="hanger" onClick={onOpen} aria-label={`${product?.name ?? h.piece.name}: see other options`}>
      <HangerHook />
      <div className="hanger-card">
        <div className="hanger-img">
          {product ? <img src={product.image_url} alt={product.name} style={{ padding: 8 }} />
            : h.piece.crop_url ? <img src={h.piece.crop_url} alt="" style={{ opacity: .55 }} /> : null}
          {product && h.piece.crop_url && <img className="pick" src={h.piece.crop_url} alt="" title={`From your inspo: ${h.piece.name}`} />}
        </div>
        <div className="hanger-body">
          <div className="name">{product?.name ?? h.piece.name}</div>
          <div className="row" style={{ marginTop: 6, gap: 4 }}>
            {product ? <span className="price" style={{ fontSize: 13 }}>{inr(product.price_inr)}</span>
              : <span className="chip chip-rose">{h.covered ? "Pick a store piece" : "Wish · not in store"}</span>}
            {product && h.chosen_size && <span className="chip">Size {h.chosen_size}</span>}
          </div>
        </div>
      </div>
    </button>
  );
}

function MoveMenu({ h, folders, current }: { h: Hanger; folders: FolderSummary[]; current: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const move = useMutation({
    mutationFn: (fid: number) => api.patch(`/hangers/${h.id}`, { folder_id: fid }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["folder"] }); qc.invalidateQueries({ queryKey: ["folders"] }); toast("Hanger moved"); },
  });
  const remove = useMutation({
    mutationFn: () => api.del(`/hangers/${h.id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["folder"] }); toast("Hanger removed"); },
  });
  return (
    <div className="row" style={{ gap: 4, marginTop: 6 }}>
      <select className="select" style={{ minHeight: 30, fontSize: 12, padding: "4px 6px", width: 108 }} value={current}
        onChange={(e) => move.mutate(Number(e.target.value))} aria-label={`Move ${h.piece.name} to folder`}>
        {folders.map((f) => <option key={f.id} value={f.id}>{f.id === current ? "Move to…" : f.name}</option>)}
      </select>
      <button className="icon-btn" style={{ width: 30, height: 30 }} onClick={() => remove.mutate()} aria-label={`Remove ${h.piece.name}`}>
        <Icon name="trash" size={16} />
      </button>
    </div>
  );
}

export default function FolderPage() {
  const { id } = useParams();
  const folderId = Number(id);
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const hangerParam = params.get("hanger");
  const [tab, setTab] = useState<"looks" | "inspo">("looks");
  const q = useQuery({ queryKey: ["folder", folderId], queryFn: () => api.get<FolderDetail>(`/folders/${folderId}`) });
  const folders = useQuery({ queryKey: ["folders"], queryFn: () => api.get<FolderSummary[]>("/folders") });

  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading label="Opening your wardrobe" />;
  const f = q.data;
  const byInspo = new Map<number, Hanger[]>();
  f.hangers.forEach((h) => byInspo.set(h.piece.inspo_id, [...(byInspo.get(h.piece.inspo_id) ?? []), h]));
  const openHanger = (hid: number) => setParams({ hanger: String(hid) });

  return (
    <>
      <Link to="/" className="btn btn-ghost btn-sm" style={{ marginLeft: -8 }}><Icon name="back" size={16} /> Wardrobes</Link>
      <div className="row-between" style={{ marginTop: 4 }}>
        <div style={{ minWidth: 0 }}>
          <span className="eyebrow">Folder</span>
          <h1>{f.name}</h1>
          {f.description && <p className="muted" style={{ margin: "4px 0 0" }}>{f.description}</p>}
        </div>
        {f.hangers.length > 0 && (
          <button className="btn btn-primary" onClick={() => nav(`/folders/${folderId}/board`)}><Icon name="sparkle" /> Style board</button>
        )}
      </div>

      <div className="section" style={{ marginTop: 18 }}>
        <UploadZone folderId={folderId} compact={f.inspo.length > 0} />
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "looks"} onClick={() => setTab("looks")}>Hangers ({f.hangers.length})</button>
        <button role="tab" aria-selected={tab === "inspo"} onClick={() => setTab("inspo")}>Inspo ({f.inspo.length})</button>
      </div>

      {tab === "looks" && (
        <>
          {f.hangers.length === 0 && (
            <div className="empty">
              <h3>No hangers yet</h3>
              <p className="muted" style={{ margin: 0 }}>Upload an inspo screenshot, pick the pieces you love, and they'll hang here.</p>
            </div>
          )}
          {f.looks.map((look) => {
            const hs = byInspo.get(look.inspo_id) ?? [];
            return (
              <section key={look.inspo_id} className="card pad" style={{ marginBottom: 16 }}>
                <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                  {look.image_url && (
                    <Link to={`/inspo/${look.inspo_id}`} aria-label="Open this inspo">
                      <img src={look.image_url} alt="Inspo for this look" style={{ width: 56, height: 96, objectFit: "cover", borderRadius: 8 }} />
                    </Link>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <CoverageLine coverage={look.coverage} />
                  </div>
                </div>
                <div className="rail">
                  {hs.map((h) => (
                    <div key={h.id} style={{ flex: "0 0 150px" }}>
                      <HangerCard h={h} onOpen={() => openHanger(h.id)} />
                      <MoveMenu h={h} folders={folders.data ?? []} current={folderId} />
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}

      {tab === "inspo" && (
        <div className="folder-grid">
          {f.inspo.length === 0 && <div className="muted">No inspo yet.</div>}
          {f.inspo.map((i) => (
            <Link key={i.id} to={`/inspo/${i.id}`} className="card folder-card">
              <img src={i.image_url} alt="Inspo screenshot" style={{ aspectRatio: "9/16", objectFit: "cover" }} loading="lazy" />
              <div className="folder-meta small muted">{i.pieces.length} pieces · {i.pieces.filter((p) => p.selected).length} saved</div>
            </Link>
          ))}
        </div>
      )}

      {hangerParam && <HangerDrawer hangerId={Number(hangerParam)} onClose={() => setParams({})} />}
    </>
  );
}
