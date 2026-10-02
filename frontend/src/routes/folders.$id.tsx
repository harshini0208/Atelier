import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { ArrowLeft, Brush, Plus, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Chip, PageHead } from "@/components/wiw/bits";
import { inr } from "@/lib/api";
import { moveHanger, removeHanger, setPieceFolders, useStore } from "@/lib/store";
import { openProduct, setPendingInspo } from "@/lib/ui";

export const Route = createFileRoute("/folders/$id")({
  head: () => ({ meta: [{ title: "Folder · Atelier" }] }),
  component: FolderPage,
});

function FolderPage() {
  const id = Number(Route.useParams().id);
  const navigate = useNavigate();
  const folder = useStore((s) => s.folders.find((f) => f.id === id));
  const folders = useStore((s) => s.folders);
  const allHangers = useStore((s) => s.hangers);
  const inspo = useStore((s) => s.folderInspo[id] ?? []);
  const rail = useStore((s) => s.rail);
  const hangers = allHangers.filter((h) => h.folderId === id);
  const [tab, setTab] = useState<"hangers" | "inspo">("hangers");
  const [adding, setAdding] = useState(false);
  const file = useRef<HTMLInputElement>(null);

  if (!folder)
    return (
      <div className="py-20 text-center">
        <p className="display text-3xl">This folder isn't here</p>
        <Button asChild variant="outline" className="mt-6"><Link to="/">Back to wardrobe</Link></Button>
      </div>
    );

  const upload = (f?: File) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) return void toast.error("Please choose an image (PNG, JPG or WebP screenshot).");
    setPendingInspo(f, id);
    void navigate({ to: "/inspo" });
  };

  return (
    <>
      <Link to="/" className="mb-6 inline-flex min-h-11 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Wardrobe
      </Link>
      <PageHead
        eyebrow="Folder"
        title={folder.name}
        intro={folder.description}
        actions={
          <>
            <Button variant="outline" onClick={() => setAdding(true)}><Plus /> Add from your rail</Button>
            <Button asChild variant="hero"><Link to="/board" search={{ folder: id }}><Brush /> Style board</Link></Button>
          </>
        }
      />

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}
        className="mb-8 flex flex-col items-center gap-3 rounded-[20px] border border-dashed border-border bg-card px-6 py-8 text-center"
      >
        <input ref={file} type="file" accept="image/*" className="sr-only" aria-label="Choose an inspo screenshot" onChange={(e) => upload(e.target.files?.[0])} />
        <Button variant="outline" onClick={() => file.current?.click()}><Upload /> Upload inspo</Button>
        <p className="text-xs text-muted-foreground">Drop a screenshot from Instagram, Pinterest, anything.</p>
      </div>

      <div className="mb-6 flex gap-2 border-b border-border pb-3" role="tablist">
        <Chip active={tab === "hangers"} onClick={() => setTab("hangers")}>Hangers ({hangers.length})</Chip>
        <Chip active={tab === "inspo"} onClick={() => setTab("inspo")}>Inspo ({inspo.length})</Chip>
      </div>

      {tab === "hangers" ? (
        hangers.length ? (
          <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 xl:grid-cols-4">
            {hangers.map((h) => (
              <li key={h.id} className="hanger-card">
                <button onClick={() => openProduct(h.product.id)} className="block w-full overflow-hidden rounded-[18px] bg-muted">
                  <img src={h.product.image_url} alt={h.product.name} className="aspect-[3/4] w-full object-cover" />
                </button>
                <p className="eyebrow mt-3">{h.fromInspo ? "From inspo" : "From your rail"}</p>
                <p className="mt-1 text-sm font-medium leading-snug">{h.product.name}</p>
                <p className="text-xs text-muted-foreground">{inr(h.product.price_inr)}{h.size ? ` · Size ${h.size}` : ""}</p>
                <div className="mt-2 flex items-center gap-1">
                  {folders.length > 1 && (
                    <select
                      aria-label={`Move ${h.product.name} to folder`}
                      value=""
                      onChange={(e) => void moveHanger(h.id, Number(e.target.value))}
                      className="h-9 min-w-0 flex-1 rounded-full border border-border bg-card px-3 text-xs"
                    >
                      <option value="" disabled>Move to…</option>
                      {folders.filter((f) => f.id !== id).map((f) => (
                        <option key={f.id} value={f.id}>{f.name}</option>
                      ))}
                    </select>
                  )}
                  <Button variant="ghost" size="icon" aria-label={`Remove ${h.product.name}`} onClick={() => void removeHanger(h.id)}>
                    <Trash2 />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-12 text-center text-sm text-muted-foreground">No hangers yet. Add pieces from your rail or upload inspo.</p>
        )
      ) : inspo.length ? (
        <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {inspo.map((i) => (
            <li key={i.id}>
              <Link to="/inspo" search={{ id: i.id }} className="block overflow-hidden rounded-[14px] border border-border bg-card">
                <img src={i.image_url} alt="Inspo screenshot" loading="lazy" className="aspect-[9/16] w-full object-cover" />
                <span className="block px-2 py-1 text-[10px] text-muted-foreground">
                  {i.pieces.length} pieces · {i.pieces.filter((p) => p.selected).length} saved
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="py-12 text-center text-sm text-muted-foreground">Screenshots you upload into this folder show here.</p>
      )}

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto rounded-[20px] border-border bg-card">
          <DialogHeader>
            <DialogTitle className="display text-2xl">Add from your rail</DialogTitle>
            <DialogDescription>Pieces you own, bagged or wishlisted.</DialogDescription>
          </DialogHeader>
          {!rail?.items.length && <p className="text-sm text-muted-foreground">Your rail is empty. Heart pieces in the shop or link your membership.</p>}
          <ul className="space-y-2">
            {rail?.items.map((it) => {
              const on = it.folder_ids.includes(id);
              return (
                <li key={it.product.id}>
                  <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-[14px] border border-border p-2 hover:bg-muted">
                    <Checkbox
                      checked={on}
                      onCheckedChange={() =>
                        void setPieceFolders(
                          it.product,
                          on ? it.folder_ids.filter((x) => x !== id) : [...it.folder_ids, id],
                          it.sources.find((s) => s.size)?.size ?? null,
                        )
                      }
                    />
                    <img src={it.product.image_url} alt="" className="size-12 rounded-[10px] object-cover" />
                    <span className="flex-1 text-sm">{it.product.name}</span>
                    <span className="text-[11px] text-muted-foreground">{it.sources[0]?.label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
          <Button variant="hero" onClick={() => setAdding(false)}>Done</Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
