import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MouseEvent, useEffect, useState } from "react";
import { api } from "../api";
import type { FolderSummary, Product } from "../types";
import { ErrorBox, Icon, Modal, useToast } from "./ui";

export type RailSource = { kind: "online" | "in_store" | "cart" | "wishlist"; label: string; detail: string; size: string | null; at: string };
export type RailItem = { product: Product; sources: RailSource[]; owned: boolean; folder_ids: number[] };
export type Rail = { items: RailItem[]; counts: Record<string, number>; member_linked: boolean };

export const useRail = () => useQuery({ queryKey: ["rail"], queryFn: () => api.get<Rail>("/rail") });

export function useWishlist() {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["wishlist"], queryFn: () => api.get<string[]>("/wishlist") });
  const ids = new Set(q.data ?? []);
  const toggle = useMutation({
    mutationFn: (p: Product) => (ids.has(p.id) ? api.del(`/wishlist/${p.id}`) : api.post("/wishlist", { product_id: p.id })),
    onMutate: (p) => {
      const was = ids.has(p.id);
      qc.setQueryData<string[]>(["wishlist"], (old = []) => (was ? old.filter((i) => i !== p.id) : [p.id, ...old]));
      toast(was ? `Removed ${p.name} from your wishlist` : `${p.name} is on your rail`);
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: ["wishlist"] }); qc.invalidateQueries({ queryKey: ["rail"] }); },
  });
  return { ids, toggle: (p: Product) => toggle.mutate(p) };
}

/** Heart toggle. Sits on top of a card, so it stops the click reaching the card. */
export function WishButton({ product, className = "" }: { product: Product; className?: string }) {
  const { ids, toggle } = useWishlist();
  const on = ids.has(product.id);
  return (
    <button type="button" className={`wish-btn ${on ? "on" : ""} ${className}`} aria-pressed={on}
      aria-label={on ? `Remove ${product.name} from wishlist` : `Add ${product.name} to wishlist`}
      onClick={(e: MouseEvent) => { e.stopPropagation(); toggle(product); }}>
      <Icon name="heart" size={18} />
    </button>
  );
}

/** Hang one piece in any number of folders at once (and take it out of the ones you untick). */
export function FolderPicker({ product, initial, size, onClose }: {
  product: Product; initial?: number[]; size?: string | null; onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const folders = useQuery({ queryKey: ["folders"], queryFn: () => api.get<FolderSummary[]>("/folders") });
  const rail = useQuery({ queryKey: ["rail"], queryFn: () => api.get<Rail>("/rail"), enabled: initial === undefined });
  const [picked, setPicked] = useState<Set<number> | null>(initial ? new Set(initial) : null);
  const [name, setName] = useState("");
  useEffect(() => {
    if (picked === null && rail.data) setPicked(new Set(rail.data.items.find((i) => i.product.id === product.id)?.folder_ids ?? []));
  }, [rail.data, picked, product.id]);
  const sel = picked ?? new Set<number>();
  const flip = (id: number) => { const n = new Set(sel); if (n.has(id)) n.delete(id); else n.add(id); setPicked(n); };

  const create = useMutation({
    mutationFn: () => api.post<FolderSummary>("/folders", { name: name.trim(), description: "" }),
    onSuccess: (f) => { qc.invalidateQueries({ queryKey: ["folders"] }); setPicked(new Set([...sel, f.id])); setName(""); },
  });
  const save = useMutation({
    mutationFn: () => api.put<{ folder_ids: number[] }>(`/rail/${product.id}/folders`, { folder_ids: [...sel], size: size ?? null }),
    onSuccess: (r) => {
      ["rail", "folders", "folder", "tray"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast(r.folder_ids.length ? `${product.name} is hanging in ${r.folder_ids.length} folder${r.folder_ids.length === 1 ? "" : "s"}`
        : `${product.name} is off your folders`);
      onClose();
    },
  });

  return (
    <Modal title="Hang it in folders" onClose={onClose}>
      <div className="stack">
        <div className="row" style={{ gap: 12, flexWrap: "nowrap" }}>
          <img src={product.image_url} alt="" style={{ width: 64, height: 64, objectFit: "contain", background: "#f4efe8", borderRadius: 10 }} />
          <div><b>{product.name}</b><div className="small muted">Pick every folder it belongs in. One piece, many looks.</div></div>
        </div>
        {folders.error && <ErrorBox error={folders.error} />}
        <div className="stack" style={{ gap: 6 }} role="group" aria-label="Folders">
          {folders.data?.length === 0 && <span className="small muted">No folders yet. Name your first one below.</span>}
          {folders.data?.map((f) => (
            <label key={f.id} className="folder-check">
              <input type="checkbox" checked={sel.has(f.id)} onChange={() => flip(f.id)} />
              <span style={{ flex: 1 }}>{f.name}</span>
              <span className="small muted">{f.hanger_count} hanger{f.hanger_count === 1 ? "" : "s"}</span>
            </label>
          ))}
        </div>
        <form className="row" style={{ flexWrap: "nowrap", gap: 6 }} onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
          <label htmlFor="new-folder" className="sr-only">New folder name</label>
          <input id="new-folder" className="input" placeholder="New folder, e.g. Office edit" maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn" disabled={!name.trim() || create.isPending}><Icon name="plus" size={16} /> Add</button>
        </form>
        {(create.error || save.error) && <ErrorBox error={create.error || save.error} />}
        <button className="btn btn-primary" disabled={picked === null || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? <span className="spinner" /> : <Icon name="hanger" />} Save
        </button>
      </div>
    </Modal>
  );
}

/** From a folder: tick rail pieces to hang them here (untick to take them off). */
export function AddFromRail({ folderId, onClose }: { folderId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const rail = useRail();
  const toggle = useMutation({
    mutationFn: (i: RailItem) => {
      const has = i.folder_ids.includes(folderId);
      const ids = has ? i.folder_ids.filter((f) => f !== folderId) : [...i.folder_ids, folderId];
      return api.put<{ folder_ids: number[] }>(`/rail/${i.product.id}/folders`,
        { folder_ids: ids, size: i.sources.find((s) => s.size)?.size ?? null }).then(() => ({ i, has }));
    },
    onSuccess: ({ i, has }) => {
      ["rail", "folders", "folder", "tray"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast(has ? `Took ${i.product.name} off this folder` : `${i.product.name} is hanging here`);
    },
  });
  const items = rail.data?.items ?? [];
  return (
    <Modal title="Add from your rail" onClose={onClose}>
      <div className="stack">
        <span className="small muted">Pieces you've bought online or in store, have in your bag, or wishlisted. Tap to hang one here.</span>
        {rail.error && <ErrorBox error={rail.error} />}
        {rail.data && !items.length && <span className="small muted">Your rail is empty. Heart pieces in the Shop or link your membership on the home page.</span>}
        <div className="rail-pick-grid">
          {items.map((i) => {
            const on = i.folder_ids.includes(folderId);
            return (
              <button key={i.product.id} className={`rail-pick ${on ? "on" : ""}`} aria-pressed={on} disabled={toggle.isPending}
                onClick={() => toggle.mutate(i)}>
                <img src={i.product.image_url} alt="" />
                <span className="small" style={{ fontWeight: 600 }}>{i.product.name}</span>
                <span className="small muted">{i.sources[0].label}</span>
                {on && <span className="rail-pick-check"><Icon name="check" size={14} /></span>}
              </button>
            );
          })}
        </div>
        <button className="btn btn-primary" onClick={onClose}>Done</button>
      </div>
    </Modal>
  );
}
