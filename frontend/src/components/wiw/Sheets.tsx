import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Heart, Plus, Truck, FolderPlus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { inr } from "@/lib/api";
import { getProduct } from "@/lib/data";
import { addToCart, createFolder, setPieceFolders, toggleWish, useStore } from "@/lib/store";
import { openHang, openProduct, useUI } from "@/lib/ui";
import { cn } from "@/lib/utils";

/** "Hang it in folders": one piece, many folders. */
export function HangSheet() {
  const product = useUI((u) => u.hangProduct);
  const folders = useStore((s) => s.folders);
  const rail = useStore((s) => s.rail);
  const hangers = useStore((s) => s.hangers);
  const [picked, setPicked] = useState<number[]>([]);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!product) return;
    const onRail = rail?.items.find((i) => i.product.id === product.id);
    setPicked(onRail ? onRail.folder_ids : hangers.filter((h) => h.product.id === product.id).map((h) => h.folderId));
    // only when a new piece opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product]);

  const add = async () => {
    if (!name.trim()) return;
    const f = await createFolder(name.trim());
    if (f) setPicked((p) => [...p, f.id]);
    setName("");
  };

  return (
    <Dialog open={!!product} onOpenChange={(o) => !o && openHang(null)}>
      <DialogContent className="max-w-md rounded-[20px] border-border bg-card">
        <DialogHeader>
          <DialogTitle className="display text-2xl">Hang it in folders</DialogTitle>
          <DialogDescription>Pick every folder it belongs in. One piece, many looks.</DialogDescription>
        </DialogHeader>
        {product && (
          <div className="flex items-center gap-3 rounded-[14px] bg-muted p-2">
            <img src={product.image_url} alt="" className="size-14 rounded-[10px] object-cover" />
            <p className="text-sm font-medium">{product.name}</p>
          </div>
        )}
        <ul className="space-y-2">
          {folders.length === 0 && <li className="text-sm text-muted-foreground">No folders yet. Name your first one below.</li>}
          {folders.map((f) => {
            const on = picked.includes(f.id);
            return (
              <li key={f.id}>
                <label className="flex min-h-12 cursor-pointer items-center gap-3 rounded-[14px] border border-border px-4 hover:bg-muted">
                  <Checkbox
                    checked={on}
                    onCheckedChange={() => setPicked((p) => (on ? p.filter((x) => x !== f.id) : [...p, f.id]))}
                  />
                  <span className="flex-1 text-sm">{f.name}</span>
                  <span className="text-xs text-muted-foreground">{f.hanger_count} hangers</span>
                </label>
              </li>
            );
          })}
        </ul>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void add()}
            placeholder="New folder, e.g. Office edit"
            aria-label="New folder name"
            className="h-11 min-w-0 flex-1 rounded-full border border-border bg-background px-4 text-sm"
          />
          <Button variant="outline" onClick={() => void add()}>
            <Plus /> Add
          </Button>
        </div>
        <Button
          variant="hero"
          className="w-full"
          disabled={saving}
          onClick={async () => {
            if (!product) return;
            setSaving(true);
            const size = rail?.items.find((i) => i.product.id === product.id)?.sources.find((s) => s.size)?.size ?? null;
            const ok = await setPieceFolders(product, picked, size);
            setSaving(false);
            if (!ok) return;
            toast.success(picked.length ? `Hung in ${picked.length} folder${picked.length > 1 ? "s" : ""}` : "Taken out of all folders");
            openHang(null);
          }}
        >
          {saving ? <Loader2 className="animate-spin" /> : <FolderPlus />} Save
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/** Product sheet: photo, price, sizes, delivery, wishlist, cart, folders. */
export function ProductSheet() {
  const id = useUI((u) => u.productId);
  const wished = useStore((s) => (id ? s.wishlist.includes(id) : false));
  const { data: p, isLoading } = useQuery({
    queryKey: ["product", id],
    queryFn: () => getProduct(id!),
    enabled: !!id,
  });
  const [size, setSize] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  useEffect(() => {
    setSize(p?.suggested_size && p.sizes.find((s) => s.size === p.suggested_size && s.stock > 0) ? p.suggested_size : null);
  }, [p]);

  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && openProduct(null)}>
      <SheetContent side="right" className="w-full overflow-y-auto border-border bg-card p-0 sm:max-w-md">
        {isLoading || !p ? (
          <div className="space-y-4 p-6">
            <SheetTitle className="sr-only">Loading product</SheetTitle>
            <Skeleton className="aspect-[3/4] w-full rounded-[18px]" />
            <Skeleton className="h-6 w-2/3" />
          </div>
        ) : (
          <>
            <div className="aspect-[3/4] bg-muted">
              <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" />
            </div>
            <div className="space-y-6 p-6">
              <SheetHeader className="p-0 text-left">
                <p className="eyebrow">{p.brand} · {p.subcategory_label}</p>
                <SheetTitle className="display text-3xl">{p.name}</SheetTitle>
                <SheetDescription className="text-sm">{p.description}</SheetDescription>
              </SheetHeader>
              <div className="flex items-baseline gap-3">
                <span className="text-xl font-semibold">{inr(p.price_inr)}</span>
                {p.mrp_inr > p.price_inr && (
                  <>
                    <span className="text-sm text-muted-foreground line-through">{inr(p.mrp_inr)}</span>
                    <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-foreground">
                      {Math.round((1 - p.price_inr / p.mrp_inr) * 100)}% off
                    </span>
                  </>
                )}
              </div>
              <fieldset>
                <legend className="mb-2 text-xs font-medium text-muted-foreground">
                  Size {p.suggested_size && <>· we suggest {p.suggested_size}</>}
                </legend>
                <div className="flex flex-wrap gap-2">
                  {p.sizes.map((s) => (
                    <button
                      key={s.size}
                      disabled={s.stock === 0}
                      onClick={() => setSize(s.size)}
                      aria-pressed={size === s.size}
                      aria-label={s.stock === 0 ? `${s.size}, sold out` : s.size}
                      className={cn(
                        "min-w-11 h-11 rounded-full border px-2 text-sm transition-colors",
                        size === s.size ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted",
                        s.stock === 0 && "cursor-not-allowed text-muted-foreground line-through opacity-50",
                      )}
                    >
                      {s.size}
                    </button>
                  ))}
                </div>
              </fieldset>
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Truck className="size-4" aria-hidden /> {p.delivery}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="hero"
                  className="flex-1"
                  disabled={!size || adding || !p.in_stock}
                  onClick={async () => {
                    setAdding(true);
                    const ok = await addToCart(p, size!);
                    setAdding(false);
                    if (ok) toast.success("Added to your bag");
                  }}
                >
                  {adding && <Loader2 className="animate-spin" />}
                  {!p.in_stock ? "Sold out" : size ? "Add to cart" : "Pick a size"}
                </Button>
                <Button variant="outline" size="icon" aria-pressed={wished} aria-label={wished ? "Remove from wishlist" : "Add to wishlist"} onClick={() => void toggleWish(p.id)}>
                  <Heart className={cn(wished && "fill-current")} />
                </Button>
              </div>
              <Button variant="outline" className="w-full" onClick={() => openHang(p)}>
                <FolderPlus /> Hang it in folders
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
