import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MouseEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, pretty } from "../api";
import { useVocab } from "../components/Layout";
import { ErrorBox, Icon, Loading, Modal, useToast } from "../components/ui";
import type { Coverage, FolderSummary, Inspo, Piece } from "../types";

function Boxes({ inspo, selected, toggle }: { inspo: Inspo; selected: Set<number>; toggle: (id: number) => void }) {
  return (
    <>
      {inspo.pieces.filter((p) => p.box && !(p.manual && p.box[0] === 0 && p.box[2] === 1000)).map((p) => {
        const [y0, x0, y1, x1] = p.box!;
        const on = selected.has(p.id);
        return (
          <button key={p.id} className="box" aria-pressed={on} onClick={(e) => { e.stopPropagation(); toggle(p.id); }}
            aria-label={`${on ? "Unselect" : "Select"} ${p.name}`}
            style={{ top: `${y0 / 10}%`, left: `${x0 / 10}%`, height: `${(y1 - y0) / 10}%`, width: `${(x1 - x0) / 10}%` }}>
            <span className="box-label">{on ? "✓ " : ""}{p.subcategory_label}</span>
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
              <optgroup key={c.key} label={c.label}>
                {c.subcategories.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="field">
          <span className="label">Colour</span>
          <div className="chips">
            {vocab.data?.colors.map((c) => (
              <button type="button" key={c.key} className="chip" aria-pressed={color === c.key} onClick={() => setColor(c.key)}>
                <span className="swatch" style={{ background: c.hex }} />{c.label}
              </button>
            ))}
          </div>
        </div>
        {add.error && <ErrorBox error={add.error} />}
        <button className="btn btn-primary" disabled={!sub || !color || add.isPending}>Add piece</button>
      </form>
    </Modal>
  );
}

function PieceRow({ p, on, toggle, folders, folderId, setFolder }: {
  p: Piece; on: boolean; toggle: () => void; folders: FolderSummary[]; folderId: number; setFolder: (id: number) => void;
}) {
  const vocab = useVocab();
  const hex = vocab.data?.colors.find((c) => c.key === p.color)?.hex;
  return (
    <div className={`piece-row ${on ? "on" : ""}`} onClick={toggle}>
      <input type="checkbox" checked={on} onChange={toggle} onClick={(e) => e.stopPropagation()} aria-label={`Keep ${p.name}`} />
      {p.crop_url ? <img src={p.crop_url} alt={`Crop of ${p.name}`} /> : <div className="skeleton" style={{ width: 56, height: 56 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>{p.name}</div>
        <div className="chips" style={{ marginTop: 4 }}>
          {hex && <span className="chip"><span className="swatch" style={{ background: hex }} />{pretty(p.color)}</span>}
          <span className="chip">{pretty(p.fabric)}</span>
          {p.pattern !== "solid" && <span className="chip">{pretty(p.pattern)}</span>}
          {p.confidence < 0.6 && <span className="chip chip-amber">Best guess</span>}
          {p.manual && <span className="chip">Added by you</span>}
        </div>
      </div>
      {on && folders.length > 1 && (
        <select className="select" style={{ width: 150, minHeight: 36, fontSize: 13 }} value={folderId}
          onClick={(e) => e.stopPropagation()} onChange={(e) => setFolder(Number(e.target.value))} aria-label={`Folder for ${p.name}`}>
          {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
      )}
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
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [folderBy, setFolderBy] = useState<Record<number, number>>({});
  const [tapMode, setTapMode] = useState(false);
  const [tapPoint, setTapPoint] = useState<[number, number] | null | undefined>(undefined);
  const inspo = q.data;

  useEffect(() => {
    if (!inspo) return;
    // keep what was saved before, and anything the shopper added by hand; fresh detections start unselected
    setSelected((prev) => {
      const next = new Set(prev);
      inspo.pieces.forEach((p) => { if (p.selected || (p.manual && p.selected === null)) next.add(p.id); });
      return next;
    });
  }, [inspo]);

  const toggle = (pid: number) => setSelected((s) => { const n = new Set(s); n.has(pid) ? n.delete(pid) : n.add(pid); return n; });
  const allOn = useMemo(() => inspo && inspo.pieces.length > 0 && inspo.pieces.every((p) => selected.has(p.id)), [inspo, selected]);

  const commit = useMutation({
    mutationFn: () => api.post<{ created: number[]; coverage: Coverage }>(`/inspo/${inspoId}/select`, {
      piece_ids: [...selected], folder_id: inspo!.folder_id, folder_by_piece: folderBy }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["folder"] });
      qc.invalidateQueries({ queryKey: ["folders"] });
      qc.invalidateQueries({ queryKey: ["inspo", inspoId] });
      toast(r.created.length ? `${r.created.length} piece${r.created.length === 1 ? "" : "s"} on hangers` : "Hangers updated");
      nav(`/folders/${inspo!.folder_id}`);
    },
  });

  const onImageClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!tapMode) return;
    const r = e.currentTarget.getBoundingClientRect();
    setTapPoint([Math.round(((e.clientY - r.top) / r.height) * 1000), Math.round(((e.clientX - r.left) / r.width) * 1000)]);
    setTapMode(false);
  };

  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!inspo) return <Loading label="Opening your inspo" />;
  const folderName = folders.data?.find((f) => f.id === inspo.folder_id)?.name;

  return (
    <>
      <Link to={`/folders/${inspo.folder_id}`} className="btn btn-ghost btn-sm" style={{ marginLeft: -8 }}><Icon name="back" size={16} /> {folderName ?? "Folder"}</Link>
      <div className="inspo-layout" style={{ marginTop: 8 }}>
        <div className="stack">
          <div className={`inspo-frame ${tapMode ? "tap-mode" : ""}`} onClick={onImageClick}>
            <img src={inspo.image_url} alt="Your inspiration screenshot" />
            {!tapMode && <Boxes inspo={inspo} selected={selected} toggle={toggle} />}
          </div>
          <div className="row" style={{ justifyContent: "center" }}>
            <button className={`btn btn-sm ${tapMode ? "btn-primary" : ""}`} onClick={() => setTapMode((t) => !t)} aria-pressed={tapMode}>
              <Icon name="plus" size={16} /> {tapMode ? "Tap the piece on the image…" : "Tap to add a missed piece"}
            </button>
            <button className="btn btn-sm btn-ghost" onClick={() => setTapPoint(null)}>Add without tapping</button>
          </div>
        </div>

        <div className="stack">
          <div>
            <span className="eyebrow">Step 2 · Pick what you love</span>
            <h1>{inspo.pieces.length ? `We found ${inspo.pieces.length} piece${inspo.pieces.length === 1 ? "" : "s"}` : "Let's find the pieces"}</h1>
            <p className="muted" style={{ margin: "6px 0 0" }}>
              Tap the boxes or the list. The pieces you keep go on hangers; we'll match them with Urban Thread's catalog.
            </p>
          </div>
          {inspo.message && <div className={`alert ${inspo.status === "analyzed" ? "" : "alert-rose"}`}>{inspo.message}</div>}
          {inspo.pieces.length > 0 && (
            <>
              <div className="row-between">
                <button className="btn btn-sm" onClick={() => setSelected(allOn ? new Set() : new Set(inspo.pieces.map((p) => p.id)))}>
                  {allOn ? "Clear all" : "♥ Like all"}
                </button>
                <span className="small muted">{selected.size} of {inspo.pieces.length} selected</span>
              </div>
              <div className="piece-list">
                {inspo.pieces.map((p) => (
                  <PieceRow key={p.id} p={p} on={selected.has(p.id)} toggle={() => toggle(p.id)} folders={folders.data ?? []}
                    folderId={folderBy[p.id] ?? inspo.folder_id!} setFolder={(fid) => setFolderBy({ ...folderBy, [p.id]: fid })} />
                ))}
              </div>
            </>
          )}
          {commit.error && <ErrorBox error={commit.error} />}
          <button className="btn btn-primary btn-block" disabled={selected.size === 0 || commit.isPending} onClick={() => commit.mutate()}>
            {commit.isPending ? <span className="spinner" /> : <Icon name="hanger" />}
            {selected.size ? `Hang ${selected.size} piece${selected.size === 1 ? "" : "s"}` : "Select pieces to hang"}
          </button>
          {inspo.source === "fallback" && inspo.pieces.length > 0 && (
            <span className="small muted">Offline mode: pieces came from the saved demo analysis.</span>
          )}
        </div>
      </div>
      {tapPoint !== undefined && <AddPieceDialog point={tapPoint} inspoId={inspoId} onClose={() => setTapPoint(undefined)} />}
    </>
  );
}
