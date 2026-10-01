import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, inr } from "../api";
import { openStylist } from "../components/ChatPanel";
import { useMe } from "../components/Layout";
import ProductModal from "../components/ProductModal";
import { FolderPicker, Rail, RailItem, useRail, WishButton } from "../components/Rail";
import { ErrorBox, Icon, Modal, useToast } from "../components/ui";
import UploadZone from "../components/UploadZone";
import type { FolderSummary, Inspo } from "../types";

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

const FILTERS: { key: string; label: string; match: (i: RailItem) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "online", label: "Bought online", match: (i) => i.sources.some((s) => s.kind === "online") },
  { key: "in_store", label: "Bought in store", match: (i) => i.sources.some((s) => s.kind === "in_store") },
  { key: "cart", label: "In your bag", match: (i) => i.sources.some((s) => s.kind === "cart") },
  { key: "wishlist", label: "Wishlist", match: (i) => i.sources.some((s) => s.kind === "wishlist") },
];

function RailCard({ item, folders, onOpen, onHang }: {
  item: RailItem; folders: FolderSummary[]; onOpen: () => void; onHang: () => void;
}) {
  const p = item.product;
  const src = item.sources[0];
  const inFolders = folders.filter((f) => item.folder_ids.includes(f.id));
  return (
    <article className="rail-card" aria-label={p.name}>
      <span className="rail-hook" aria-hidden />
      <div className="rail-img">
        <button className="rail-open" onClick={onOpen} aria-label={`Open ${p.name}`}>
          <img src={p.image_url} alt="" loading="lazy" className={p.image_url.includes("/photos/") ? "photo" : ""} />
        </button>
        {!item.owned && <WishButton product={p} />}
        <span className={`rail-src ${src.kind}`}>
          <Icon name={src.kind === "in_store" ? "store" : src.kind === "online" ? "check" : src.kind === "cart" ? "bag" : "heart"} size={12} />
          {src.label}
        </span>
      </div>
      <div className="rail-meta">
        <b className="small">{p.name}</b>
        <span className="small muted">{src.detail || inr(p.price_inr)}{src.size && src.size !== "Free" ? ` · Size ${src.size}` : ""}</span>
        <button className="btn btn-sm rail-folders" onClick={onHang}>
          <Icon name="folder" size={14} />
          {inFolders.length ? (inFolders.length === 1 ? inFolders[0].name : `In ${inFolders.length} folders`) : "Add to folders"}
        </button>
      </div>
    </article>
  );
}

function LinkMembership({ compact = false }: { compact?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const link = useMutation({
    mutationFn: () => api.post<{ added: number; rail: Rail }>("/membership/link", {}),
    onSuccess: (r) => { qc.setQueryData(["rail"], r.rail); toast(`${r.added} pieces from your online and in-store purchases are on your rail`); },
  });
  return (
    <div className={compact ? "member-banner" : "stack"} style={compact ? undefined : { gap: 8 }}>
      <div style={{ flex: 1 }}>
        <b>{compact ? "Shop at Urban Thread stores too?" : "Bring in what you've already bought"}</b>
        <div className="small muted">Link your Urban Thread membership to see online orders and in-store receipts here.
          <span className="demo-note"> Demo: a sample purchase history is added.</span></div>
      </div>
      {link.error && <ErrorBox error={link.error} />}
      <button className={`btn ${compact ? "btn-sm" : "btn-primary"}`} onClick={() => link.mutate()} disabled={link.isPending}>
        {link.isPending ? <span className="spinner" /> : <Icon name="store" size={16} />} Link membership
      </button>
    </div>
  );
}

export default function Home() {
  const { data: me } = useMe();
  const nav = useNavigate();
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState<string | null>(null);
  const [hang, setHang] = useState<RailItem | null>(null);
  const rail = useRail();
  const folders = useQuery({ queryKey: ["folders"], queryFn: () => api.get<FolderSummary[]>("/folders") });
  const unfiled = useQuery({ queryKey: ["unfiled"], queryFn: () => api.get<Inspo[]>("/inspo") });
  const items = rail.data?.items ?? [];
  const f = FILTERS.find((x) => x.key === filter) ?? FILTERS[0];
  const shown = items.filter(f.match);
  const first = me?.name.split(" ")[0];

  return (
    <>
      <section className="home-head">
        <div>
          <span className="eyebrow">Urban Thread · Walk-In Wardrobe</span>
          <h1>{first ? `Hi ${first}.` : "Your wardrobe"}</h1>
          <p className="muted" style={{ margin: 0 }}>
            Everything you've bought online or in store, have in your bag, or love, on one rail. Hang pieces in folders,
            style them on a canvas, or ask the stylist.
          </p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={() => nav("/board")} disabled={!items.length}><Icon name="sparkle" size={16} /> Style on canvas</button>
          <button className="btn btn-primary" onClick={() => openStylist()}><Icon name="chat" size={16} /> Ask the stylist</button>
        </div>
      </section>

      <section className="section rail-section" aria-labelledby="rail-h">
        <div className="section-head">
          <h2 id="rail-h">Your rail</h2>
          <span className="small muted">{items.length} piece{items.length === 1 ? "" : "s"}</span>
        </div>
        {rail.error && <ErrorBox error={rail.error} onRetry={() => rail.refetch()} />}
        {rail.isLoading && <div className="rail-scroller">{Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton rail-card" style={{ height: 300 }} />)}</div>}
        {rail.data && items.length === 0 && (
          <div className="rail-empty">
            <div className="card pad"><LinkMembership /></div>
            <div className="card pad stack" style={{ gap: 8 }}>
              <b>Heart pieces in the Shop</b>
              <span className="small muted">Your wishlist and bag show up here, ready to hang in folders and style.</span>
              <Link to="/shop" className="btn"><Icon name="tag" size={16} /> Browse the Shop</Link>
            </div>
          </div>
        )}
        {items.length > 0 && (
          <>
            <div className="chips" role="tablist" aria-label="Filter your rail">
              {FILTERS.map((x) => {
                const n = items.filter(x.match).length;
                if (x.key !== "all" && !n) return null;
                return (
                  <button key={x.key} role="tab" aria-selected={filter === x.key} className={`chip ${filter === x.key ? "chip-dark" : ""}`}
                    onClick={() => setFilter(x.key)}>{x.label} <span className="muted">{n}</span></button>
                );
              })}
            </div>
            <div className="rail-scroller">
              <div className="rail-bar" aria-hidden />
              {shown.map((i) => (
                <RailCard key={i.product.id} item={i} folders={folders.data ?? []} onOpen={() => setOpen(i.product.id)} onHang={() => setHang(i)} />
              ))}
            </div>
            {!rail.data?.member_linked && <LinkMembership compact />}
          </>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Your folders</h2>
          <span className="small muted">{folders.data?.length ?? 0} folders</span>
        </div>
        {folders.error && <ErrorBox error={folders.error} onRetry={() => folders.refetch()} />}
        <div className="folder-grid">
          {folders.isLoading && Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ aspectRatio: "4/5.6" }} />)}
          {folders.data?.map((fo) => <FolderCard key={fo.id} f={fo} />)}
          {folders.data && (
            <button className="card add-card" onClick={() => setAdding(true)}>
              <span className="stack" style={{ alignItems: "center", gap: 6 }}>
                <Icon name="plus" size={28} />
                <b>Add folder</b>
                <span className="small muted">Office edit, “Goa trip”, sangeet…</span>
              </span>
            </button>
          )}
        </div>
      </section>

      <section className="section inspo-section">
        <div className="section-head">
          <h2>Shop a look you saw</h2>
          <span className="small muted">Optional</span>
        </div>
        <div className="inspo-row">
          <div className="stack" style={{ gap: 6 }}>
            <p className="muted small" style={{ margin: 0 }}>
              Saw an outfit on Instagram or Pinterest? Upload a screenshot. We find each piece in Urban Thread, in your
              size and budget, and you hang the ones you like.
            </p>
            <UploadZone compact />
          </div>
          {!!unfiled.data?.length && (
            <div className="stack" style={{ gap: 6, minWidth: 0 }}>
              <span className="small muted">Not in a folder yet</span>
              <div className="row" style={{ gap: 10, overflowX: "auto", flexWrap: "nowrap", paddingBottom: 4 }}>
                {unfiled.data.map((i) => (
                  <Link key={i.id} to={`/inspo/${i.id}`} className="card" style={{ flex: "0 0 96px", overflow: "hidden", textDecoration: "none" }}>
                    <img src={i.image_url} alt="Unsorted inspo" style={{ width: "100%", aspectRatio: "9/16", objectFit: "cover" }} />
                    <div className="small muted" style={{ padding: "4px 6px" }}>{i.pieces.length} pieces</div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {adding && <AddFolderDialog onClose={() => setAdding(false)} onCreated={(fo) => nav(`/folders/${fo.id}`)} />}
      {open && <ProductModal productId={open} onClose={() => setOpen(null)} />}
      {hang && <FolderPicker product={hang.product} initial={hang.folder_ids}
        size={hang.sources.find((s) => s.size)?.size} onClose={() => setHang(null)} />}
    </>
  );
}
