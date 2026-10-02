import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";
import { ArrowDown, ArrowLeft, ArrowUp, Loader2, Sparkles, X, ShoppingBag, Bookmark, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Chip, PageHead, SectionHead } from "@/components/wiw/bits";
import { errorText, inr } from "@/lib/api";
import {
  deleteLookApi,
  getLooks,
  getTray,
  lookToCart,
  mannequinUrl,
  saveLookApi,
  styleBoard,
  tryOn,
  type Outfit,
  type TrayPiece,
} from "@/lib/data";
import { refreshCart, refreshRail, useStore } from "@/lib/store";
import { openProduct } from "@/lib/ui";
import type { Look, Product } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/board")({
  validateSearch: z.object({ folder: z.number().optional() }),
  head: () => ({ meta: [{ title: "Style board · Atelier" }] }),
  component: Board,
});

type Layer = { product: Product; owned: boolean };
/** Default layering when a piece is added: inner pieces first, coats and jackets on the outside. */
const SLOT_ORDER = ["torso", "legs", "full", "outer", "feet", "hand", "waist", "neck", "ears", "wrist", "head"];
const FORMALITY: [string, string][] = [["more_casual", "More casual"], ["more_formal", "More formal"], ["more_festive", "More festive"]];

function Board() {
  const { folder } = Route.useSearch();
  const folderId = folder ?? null;
  const qc = useQueryClient();
  const folderObj = useStore((s) => s.folders.find((f) => f.id === folder));
  const rail = useStore((s) => s.rail);
  const mannequin = useStore((s) => s.mannequin);
  const owned = useMemo(() => new Set(rail?.items.filter((i) => i.owned).map((i) => i.product.id)), [rail]);

  const { data: tray = [], isLoading: trayLoading } = useQuery({
    queryKey: ["tray", folderId, owned.size],
    queryFn: () => getTray(folderId, owned),
  });
  const { data: looks = [] } = useQuery({ queryKey: ["looks", folderId], queryFn: () => getLooks(folderId) });

  const [view, setView] = useState<"mannequin" | "flat">("mannequin");
  const [layers, setLayers] = useState<Layer[]>([]);
  const [pos, setPos] = useState<Record<string, { x: number; y: number }>>({});
  const [loadedLook, setLoadedLook] = useState<number | null>(null);
  const [autoDress, setAutoDress] = useState(false);
  const [lastImg, setLastImg] = useState<string | null>(null);
  const [style, setStyle] = useState<{ options: Outfit[]; message?: string; extras: { product: Product; pairs_with_past: string | null }[] } | null>(null);

  const ids = layers.map((l) => l.product.id);
  const key = ids.join(",");
  const mqKey = `${mannequin.body}-${mannequin.tone}`;
  const cached = useQuery({
    queryKey: ["tryon", mqKey, key],
    queryFn: () => tryOn(ids, true),
    enabled: ids.length > 0,
    staleTime: Infinity,
  });
  const dressed = ids.length ? cached.data?.image_url ?? null : null;
  const dress = useMutation({
    mutationFn: (list: string[]) => tryOn(list),
    onSuccess: (r, list) => {
      qc.setQueryData(["tryon", mqKey, list.join(",")], r);
      setLastImg(r.image_url);
    },
    onError: (e) => toast.error(errorText(e)),
  });
  useEffect(() => {
    if (dressed) setLastImg(dressed);
    else if (!ids.length) setLastImg(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dressed, ids.length]);
  useEffect(() => {
    if (!autoDress || !ids.length || !cached.isFetched) return;
    setAutoDress(false);
    if (!dressed && !dress.isPending && view === "mannequin") dress.mutate(ids);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoDress, cached.isFetched, dressed, key]);

  const fromLook = (lk: Look) => {
    const sorted = [...lk.items].sort((a, b) => a.z - b.z);
    setLayers(sorted.map((i) => ({ product: i.product, owned: owned.has(i.product.id) })));
    setLoadedLook(lk.id);
    setAutoDress(true);
  };
  useEffect(() => {
    // open the most recent saved look (e.g. one the stylist just laid out)
    const latest = looks[0];
    if (latest && latest.id !== loadedLook) fromLook(latest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [looks]);

  const has = (id: string) => layers.some((l) => l.product.id === id);
  const add = (p: Layer) => {
    if (has(p.product.id)) return;
    setLayers((l) =>
      [...l, p].sort((a, b) => (SLOT_ORDER.indexOf(a.product.slot) + 99) % 99 - (SLOT_ORDER.indexOf(b.product.slot) + 99) % 99),
    );
    setPos((s) => ({ ...s, [p.product.id]: { x: 10 + ((layers.length * 23) % 60), y: 8 + ((layers.length * 17) % 55) } }));
  };
  const remove = (id: string) => setLayers((l) => l.filter((x) => x.product.id !== id));
  const move = (i: number, d: -1 | 1) =>
    setLayers((l) => {
      const n = [...l];
      const j = i + d;
      if (j < 0 || j >= n.length) return l;
      const t = n[i]!;
      n[i] = n[j]!;
      n[j] = t;
      return n;
    });

  const runStyle = useMutation({
    mutationFn: (body: { formality?: string }) => styleBoard(folderId, body),
    onSuccess: (r) => setStyle({ options: r.options, ...(r.message ? { message: r.message } : {}), extras: r.complete_the_look }),
    onError: (e) => toast.error(errorText(e)),
  });
  const save = useMutation({
    mutationFn: () => saveLookApi(folderId, `Look ${looks.length + 1}`, ids),
    onSuccess: (lk) => {
      setLoadedLook(lk.id);
      void qc.invalidateQueries({ queryKey: ["looks", folderId] });
      toast.success("Look saved");
    },
    onError: (e) => toast.error(errorText(e)),
  });
  const removeLook = useMutation({
    mutationFn: (id: number) => deleteLookApi(id, folderId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["looks", folderId] }),
    onError: (e) => toast.error(errorText(e)),
  });
  const toBuy = layers.filter((l) => !l.owned);
  const cart = useMutation({
    mutationFn: () => lookToCart(folderId, toBuy.map((l) => l.product.id)),
    onSuccess: async (r) => {
      await Promise.all([refreshCart(), refreshRail()]);
      toast.success(
        `${r.added.length} piece${r.added.length === 1 ? "" : "s"} added. Pieces you own were skipped.` +
          (r.needs_size.length ? ` Pick a size for ${r.needs_size.map((n) => n.product.name).join(", ")}.` : ""),
      );
    },
    onError: (e) => toast.error(errorText(e)),
  });
  const total = toBuy.reduce((a, l) => a + l.product.price_inr, 0);
  const img = dressed ?? lastImg;

  return (
    <>
      <Link
        to={folder ? "/folders/$id" : "/"}
        params={{ id: String(folder ?? "") }}
        className="mb-6 inline-flex min-h-11 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {folderObj?.name ?? "Wardrobe"}
      </Link>
      <PageHead
        eyebrow="Style board"
        title={folderObj?.name ?? "Your rail"}
        intro="Mix what you own with what you're eyeing. Layer from inside to outside, then dress your mannequin."
      />

      <div className="mb-6 flex gap-2" role="tablist" aria-label="Board view">
        <Chip active={view === "mannequin"} onClick={() => setView("mannequin")}>Mannequin</Chip>
        <Chip active={view === "flat"} onClick={() => setView("flat")}>Flat lay</Chip>
      </div>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          {view === "mannequin" ? (
            <div className="relative aspect-[3/4] overflow-hidden rounded-[20px] bg-muted">
              <img
                src={img ?? mannequinUrl(mannequin.body, mannequin.tone)}
                alt={img && layers.length ? `Your mannequin wearing ${layers.map((l) => l.product.name).join(", ")}` : "Your mannequin"}
                className={cn("h-full w-full object-contain transition-opacity", (dress.isPending || (!dressed && img && layers.length)) && "opacity-40")}
              />
              {dress.isPending && (
                <div className="absolute inset-0 grid place-items-center" role="status">
                  <div className="rounded-[16px] bg-card px-5 py-4 text-center">
                    <Loader2 className="mx-auto mb-2 size-5 animate-spin" aria-hidden />
                    <p className="text-sm font-medium">Dressing your mannequin…</p>
                    <p className="text-xs text-muted-foreground">about 10 seconds</p>
                  </div>
                </div>
              )}
              {!dress.isPending && layers.length > 0 && !dressed && (
                <Button variant="hero" className="absolute bottom-4 left-1/2 -translate-x-1/2" onClick={() => dress.mutate(ids)}>
                  <Sparkles /> {lastImg ? "Update the mannequin" : "Dress mannequin"}
                </Button>
              )}
              {!layers.length && (
                <p className="absolute inset-x-4 bottom-4 rounded-[12px] bg-card/90 px-3 py-2 text-center text-xs text-muted-foreground">
                  Add pieces and we'll dress your mannequin in them.
                </p>
              )}
            </div>
          ) : (
            <FlatLay layers={layers} pos={pos} setPos={setPos} />
          )}

          <div className="mt-6">
            <SectionHead title="Layers" meta="inside → outside" />
            {layers.length ? (
              <ol className="space-y-2">
                {layers.map((l, i) => (
                  <li key={l.product.id} className="flex items-center gap-3 rounded-[14px] border border-border bg-card p-2">
                    <span className="w-5 text-center text-xs text-muted-foreground">{i + 1}</span>
                    <img src={l.product.image_url} alt="" className="size-12 rounded-[10px] object-cover" />
                    <button className="min-w-0 flex-1 text-left" onClick={() => openProduct(l.product.id)}>
                      <p className="truncate text-sm">{l.product.name}</p>
                      <p className="text-xs text-muted-foreground">{l.owned ? "Yours" : inr(l.product.price_inr)}</p>
                    </button>
                    <Button variant="ghost" size="icon" aria-label={`Wear ${l.product.name} further inside`} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp /></Button>
                    <Button variant="ghost" size="icon" aria-label={`Wear ${l.product.name} further outside`} disabled={i === layers.length - 1} onClick={() => move(i, 1)}><ArrowDown /></Button>
                    <Button variant="ghost" size="icon" aria-label={`Remove ${l.product.name}`} onClick={() => remove(l.product.id)}><X /></Button>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted-foreground">Add pieces from the tray to start a look.</p>
            )}
            {layers.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
                  <Bookmark /> Save look
                </Button>
                <Button variant="hero" disabled={!toBuy.length || cart.isPending} onClick={() => cart.mutate()}>
                  {cart.isPending ? <Loader2 className="animate-spin" /> : <ShoppingBag />}
                  {toBuy.length ? `Add ${toBuy.length} piece${toBuy.length === 1 ? "" : "s"} to cart · ${inr(total)}` : "All yours"}
                </Button>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-10">
          <section>
            <SectionHead title={folder ? "Your hangers" : "Your rail"} meta="Tap Add" />
            {trayLoading && <div className="shimmer h-24 rounded-[14px]" />}
            {!trayLoading && tray.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {folder ? "No hangers yet. Hang pieces from your rail or an inspo first." : "Your rail is empty. Heart pieces in the shop or link your membership."}
              </p>
            )}
            <ul className="grid grid-cols-2 gap-2">
              {tray.map((t: TrayPiece) => (
                <li key={t.key} className="flex items-center gap-2 rounded-[14px] border border-border bg-card p-2">
                  <img src={t.product.image_url} alt="" className="size-12 shrink-0 rounded-[10px] object-cover" />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-xs font-medium">{t.product.name}</p>
                    <p className="text-[11px] text-muted-foreground">{t.owned ? "Yours" : inr(t.product.price_inr)}</p>
                  </div>
                  <Button size="sm" variant={has(t.product.id) ? "secondary" : "outline"} aria-label={has(t.product.id) ? `Take ${t.product.name} off` : `Add ${t.product.name}`}
                    onClick={() => (has(t.product.id) ? remove(t.product.id) : add({ product: t.product, owned: t.owned }))}>
                    {has(t.product.id) ? "On" : "Add"}
                  </Button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-[20px] border border-border bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="display text-xl">Style it for me</p>
              <Button size="sm" variant="hero" disabled={runStyle.isPending || !tray.length} onClick={() => runStyle.mutate({})}>
                {runStyle.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Style it
              </Button>
            </div>
            <div className="mb-4 flex flex-wrap gap-2">
              {FORMALITY.map(([k, l]) => (
                <Chip key={k} onClick={() => !runStyle.isPending && runStyle.mutate({ formality: k })}>{l}</Chip>
              ))}
            </div>
            {style?.message && <p className="mb-3 text-sm text-muted-foreground">{style.message}</p>}
            {style?.options.map((o, i) => (
              <button
                key={i}
                onClick={() => {
                  const byId = new Map(o.items.map((it) => [it.product.id, it]));
                  const order = (o.layout ?? []).length
                    ? [...(o.layout ?? [])].sort((a, b) => a.z - b.z).map((l) => byId.get(l.product_id)!).filter(Boolean)
                    : o.items;
                  setLayers(order.map((it) => ({ product: it.product, owned: !!it.owned || owned.has(it.product.id) })));
                  setAutoDress(true);
                }}
                className="mb-3 block w-full rounded-[14px] border border-border p-3 text-left hover:bg-muted"
              >
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="font-semibold">Look {i + 1}</span>
                  <span className="text-muted-foreground">
                    {o.owned_count === o.items.length ? "All yours" : `${inr(o.total_inr)}${o.owned_count ? " to buy" : ""}`}
                  </span>
                </div>
                <div className="flex gap-1.5">
                  {o.items.map((it) => (
                    <img key={it.product.id} src={it.product.image_url} alt={it.product.name} className="size-12 rounded-[8px] object-cover" />
                  ))}
                </div>
                {o.reason && <p className="mt-2 text-xs text-muted-foreground">{o.reason}</p>}
                <p className="mt-1 text-[11px] text-muted-foreground">Tap to put it on your mannequin</p>
              </button>
            ))}
            {!!style?.extras.length && (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-semibold">Complete the look</p>
                {style.extras.map((c) => (
                  <div key={c.product.id} className="flex items-center gap-2 rounded-[14px] border border-border p-2">
                    <img src={c.product.image_url} alt="" className="size-12 rounded-[10px] object-cover" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium">{c.product.name}</p>
                      <p className="text-[11px] text-muted-foreground">{inr(c.product.price_inr)}{c.pairs_with_past ? ` · goes with your ${c.pairs_with_past}` : ""}</p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => add({ product: c.product, owned: false })}><Plus /> Add</Button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {looks.length > 0 && (
            <section>
              <SectionHead title="Saved looks" />
              <ul className="space-y-2">
                {looks.map((l) => (
                  <li key={l.id} className="flex items-center gap-3 rounded-[14px] border border-border bg-card p-3">
                    <button className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => fromLook(l)}>
                      <span className="flex -space-x-2">
                        {l.items.slice(0, 4).map((i) => (
                          <img key={i.product.id} src={i.product.image_url} alt="" className="size-9 rounded-full border-2 border-card object-cover" />
                        ))}
                      </span>
                      <span className="truncate text-sm">{l.name} · {l.items.length} pieces</span>
                    </button>
                    <Button variant="ghost" size="icon" aria-label={`Delete ${l.name}`} onClick={() => removeLook.mutate(l.id)}><Trash2 /></Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}

function FlatLay({
  layers,
  pos,
  setPos,
}: {
  layers: Layer[];
  pos: Record<string, { x: number; y: number }>;
  setPos: React.Dispatch<React.SetStateAction<Record<string, { x: number; y: number }>>>;
}) {
  const box = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);
  return (
    <div
      ref={box}
      role="region"
      aria-label="Flat lay"
      className="relative aspect-[3/4] touch-none overflow-hidden rounded-[20px] border border-border bg-card"
      onPointerMove={(e) => {
        if (!drag.current || !box.current) return;
        const r = box.current.getBoundingClientRect();
        const { id, dx, dy } = drag.current;
        setPos((s) => ({
          ...s,
          [id]: {
            x: Math.max(0, Math.min(70, ((e.clientX - r.left - dx) / r.width) * 100)),
            y: Math.max(0, Math.min(75, ((e.clientY - r.top - dy) / r.height) * 100)),
          },
        }));
      }}
      onPointerUp={() => (drag.current = null)}
    >
      {!layers.length && (
        <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">Add pieces, then drag them around.</p>
      )}
      {layers.map((l, i) => {
        const p = pos[l.product.id] ?? { x: 10 + i * 8, y: 10 + i * 6 };
        return (
          <img
            key={l.product.id}
            src={l.product.image_url}
            alt={l.product.name}
            draggable={false}
            onPointerDown={(e) => {
              const r = (e.target as HTMLElement).getBoundingClientRect();
              drag.current = { id: l.product.id, dx: e.clientX - r.left, dy: e.clientY - r.top };
              (e.currentTarget.parentElement as HTMLElement).setPointerCapture(e.pointerId);
            }}
            className="absolute w-[30%] cursor-grab rounded-[12px] active:cursor-grabbing"
            style={{ left: `${p.x}%`, top: `${p.y}%`, zIndex: i + 1 }}
          />
        );
      })}
    </div>
  );
}
