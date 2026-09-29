import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../components/Layout";
import { ErrorBox, Icon, Modal, useToast } from "../components/ui";
import type { FolderSummary } from "../types";

export function AddFolderDialog({ onClose, onCreated }: { onClose: () => void; onCreated?: (f: FolderSummary) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useMutation({
    mutationFn: () => api.post<FolderSummary>("/folders", { name, description }),
    onSuccess: (f) => {
      qc.invalidateQueries({ queryKey: ["folders"] });
      toast(`“${f.name}” is ready`);
      onCreated?.(f);
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) create.mutate();
  };
  const ideas = ["Old-money summer", "Goa trip", "Office edit", "Sangeet night", "Streetwear"];
  return (
    <Modal title="New wardrobe folder" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <div className="field">
          <label htmlFor="fname">Name</label>
          <input id="fname" className="input" autoFocus maxLength={60} value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Anything you like" required />
        </div>
        <div className="chips" aria-label="Ideas">
          {ideas.map((i) => <button type="button" key={i} className="chip" onClick={() => setName(i)}>{i}</button>)}
        </div>
        <div className="field">
          <label htmlFor="fdesc">Description <span className="muted">(optional)</span></label>
          <textarea id="fdesc" className="textarea" maxLength={300} value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="What's this wardrobe for? The stylist reads this too." />
        </div>
        {create.error && <ErrorBox error={create.error} />}
        <button className="btn btn-primary" disabled={!name.trim() || create.isPending}>
          {create.isPending ? <span className="spinner" /> : <Icon name="plus" />} Create folder
        </button>
      </form>
    </Modal>
  );
}

function FolderCard({ f }: { f: FolderSummary }) {
  const imgs = f.cover_images.length ? f.cover_images : f.inspo_images;
  return (
    <Link to={`/folders/${f.id}`} className="card folder-card">
      <div className={`folder-cover ${imgs.length < 4 ? "single" : ""}`}>
        {imgs.length === 0 && <div className="placeholder" aria-hidden>{f.name[0]}</div>}
        {(imgs.length < 4 ? imgs.slice(0, 1) : imgs.slice(0, 4)).map((src) => (
          <img key={src} src={src} alt="" loading="lazy" style={{ objectFit: imgs === f.inspo_images ? "cover" : "contain" }} />
        ))}
      </div>
      <div className="folder-meta">
        <h3>{f.name}</h3>
        <div className="small muted">{f.hanger_count} hanger{f.hanger_count === 1 ? "" : "s"} · {f.inspo_count} inspo</div>
      </div>
    </Link>
  );
}

export default function Home() {
  const { data: me } = useMe();
  const nav = useNavigate();
  const [adding, setAdding] = useState(false);
  const folders = useQuery({ queryKey: ["folders"], queryFn: () => api.get<FolderSummary[]>("/folders") });

  return (
    <>
      <section className="hero">
        <div className="stack">
          <span className="eyebrow">Urban Thread · Walk-In Wardrobe</span>
          <h1>{me ? `Hi ${me.name.split(" ")[0]}. ` : ""}Save inspiration from anywhere.</h1>
          <p className="muted" style={{ margin: 0 }}>
            Upload a screenshot of a reel, post or pin. We find the pieces in this store, in your size and budget, ready to buy.
          </p>
          <div className="row">
            <button className="btn btn-primary" onClick={() => setAdding(true)}><Icon name="plus" /> Add folder</button>
          </div>
        </div>
        <div className="hero-steps" aria-label="How it works">
          <div><b>1</b>Upload a screenshot</div>
          <div><b>2</b>Pick the pieces you love</div>
          <div><b>3</b>Shop them in your size</div>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Your wardrobes</h2>
          <span className="small muted">{folders.data?.length ?? 0} folders</span>
        </div>
        {folders.error && <ErrorBox error={folders.error} onRetry={() => folders.refetch()} />}
        <div className="folder-grid">
          {folders.isLoading && Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ aspectRatio: "4/5.6" }} />)}
          {folders.data?.map((f) => <FolderCard key={f.id} f={f} />)}
          {folders.data && (
            <button className="card add-card" onClick={() => setAdding(true)}>
              <span className="stack" style={{ alignItems: "center", gap: 6 }}>
                <Icon name="plus" size={28} />
                <b>Add folder</b>
                <span className="small muted">Formal, ethnic, “Goa trip”…</span>
              </span>
            </button>
          )}
        </div>
      </section>
      {adding && <AddFolderDialog onClose={() => setAdding(false)} onCreated={(f) => nav(`/folders/${f.id}`)} />}
    </>
  );
}
