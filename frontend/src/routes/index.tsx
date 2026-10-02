import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Brush, MessageCircle, Plus, Upload, BadgeCheck, CreditCard, Folder, ImagePlus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Brand, Chip } from "@/components/wiw/bits";
import { HangingRail } from "@/components/wiw/Rail";
import { createFolder, linkMembership, useStore } from "@/lib/store";
import { getShop, getUnfiledInspo } from "@/lib/data";
import { inr } from "@/lib/api";
import { openProduct, openStylist, setPendingInspo } from "@/lib/ui";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Your wardrobe · Atelier" }] }),
  component: Home,
});

const FILTERS = [
  { k: "all", l: "All" },
  { k: "online", l: "Bought online" },
  { k: "in_store", l: "Bought in store" },
  { k: "cart", l: "In your bag" },
  { k: "wishlist", l: "Wishlist" },
] as const;

function SectionTitle({ title, meta, action }: { title: React.ReactNode; meta?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4">
      <h2 className="font-serif text-xl text-foreground">{title}</h2>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
        {meta && <span className="uppercase tracking-widest">{meta}</span>}
        {action}
      </div>
    </div>
  );
}

function Home() {
  const navigate = useNavigate();
  const me = useStore((s) => s.me);
  const rail = useStore((s) => s.rail);
  const folders = useStore((s) => s.folders);
  const [filter, setFilter] = useState<string>("all");
  const [newName, setNewName] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const { data: shop } = useQuery({ queryKey: ["shop", "women"], queryFn: () => getShop(me?.preferences?.gender_fit === "men" ? "men" : "women") });
  const { data: unfiled = [] } = useQuery({ queryKey: ["unfiled"], queryFn: getUnfiledInspo });
  const picks = useMemo(
    () => [...(shop?.products ?? [])].sort((a, b) => (b.added_at ?? "").localeCompare(a.added_at ?? "")).slice(0, 4),
    [shop],
  );

  const items = useMemo(
    () => (rail?.items ?? []).filter((i) => filter === "all" || i.sources.some((s) => s.kind === filter)),
    [rail, filter],
  );
  const first = me?.name.split(" ")[0] ?? "";

  const upload = (f?: File) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      toast.error("Please choose an image (PNG, JPG or WebP screenshot).");
      return;
    }
    setPendingInspo(f, null);
    void navigate({ to: "/inspo" });
  };

  return (
    <div>
      <header className="mb-10 flex flex-col gap-5 sm:mb-12 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="brand-script text-[42px] leading-[1.15] text-foreground sm:text-[56px]">Hi {first}.</h1>
          <p className="mt-2 font-serif text-base italic text-muted-foreground sm:text-[19px]">
            Your wardrobe, hung and ready to style.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><Link to="/board"><Brush /> Style on canvas</Link></Button>
          <Button
            variant="hero"
            onClick={() =>
              window.matchMedia("(min-width: 1024px)").matches
                ? document.getElementById("stylist-input")?.focus()
                : openStylist(true)
            }
          >
            <MessageCircle /> Ask the stylist
          </Button>
        </div>
      </header>

      {/* The rail: pieces hanging side by side */}
      <section className="mb-14" aria-labelledby="rail-h">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 id="rail-h" className="eyebrow">Current rail</h2>
          <span className="text-xs text-muted-foreground">{rail?.items.length ?? 0} pieces</span>
        </div>
        {rail && rail.items.length > 0 && (
          <div className="no-scrollbar -mx-5 mb-5 flex gap-2 overflow-x-auto px-5 sm:mx-0 sm:px-0" role="tablist" aria-label="Filter your rail">
            {FILTERS.map((f) => {
              const n = f.k === "all" ? rail.items.length : rail.counts[f.k];
              if (f.k !== "all" && !n) return null;
              return (
                <Chip key={f.k} active={filter === f.k} onClick={() => setFilter(f.k)}>
                  {f.l} <span className="opacity-60">{n}</span>
                </Chip>
              );
            })}
          </div>
        )}
        {rail && rail.items.length === 0 ? (
          <p className="rounded-[20px] border border-dashed border-line p-8 text-center text-sm text-muted-foreground">
            Your rail is empty. Heart pieces in the shop, or link your membership below to bring in what you've bought.
          </p>
        ) : (
          <HangingRail items={items} />
        )}
        <Link
          to="/shop"
          className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line px-4 text-xs font-semibold uppercase tracking-widest text-primary transition-colors hover:bg-surface-2"
        >
          <Plus className="size-4" aria-hidden /> Add pieces
        </Link>
      </section>

      {/* Shop a look you saw: a compact upload strip right under the rail */}
      <section className="mb-14" aria-label="Shop a look you saw">
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}
          className="upload-card flex flex-col gap-4 rounded-[20px] px-5 py-5 sm:flex-row sm:items-center sm:px-6"
        >
          <span className="grid size-11 shrink-0 place-items-center rounded-full border border-white/40 bg-white/15">
            <ImagePlus className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-serif text-lg leading-tight">Shop a look you saw</p>
            <p className="mt-1 text-xs opacity-85 sm:text-sm">
              Upload a screenshot from Instagram or Pinterest. We find each piece in store, in your size and budget.
            </p>
          </div>
          <input ref={file} type="file" accept="image/*" className="sr-only" aria-label="Choose an inspo screenshot" onChange={(e) => upload(e.target.files?.[0])} />
          <Button variant="outline" className="shrink-0" onClick={() => file.current?.click()}><Upload /> Upload inspo</Button>
        </div>
        {unfiled.length > 0 && (
          <div className="mt-4">
            <p className="eyebrow mb-2">Not in a folder yet</p>
            <div className="no-scrollbar flex gap-3 overflow-x-auto">
              {unfiled.map((i) => (
                <Link key={i.id} to="/inspo" search={{ id: i.id }} className="w-20 shrink-0 overflow-hidden rounded-[12px] border border-line bg-card">
                  <img src={i.image_url} alt="Unsorted inspo" className="aspect-[9/16] w-full object-cover" />
                  <span className="block px-2 py-1 text-[10px] text-muted-foreground">{i.pieces.length} pieces</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* The studio */}
      <div className="min-w-0">
        <section className="mb-12">
          <SectionTitle title="Collections" meta={`${folders.length} folders`} />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {folders.map((f) => (
              <Link
                key={f.id}
                to="/folders/$id"
                params={{ id: String(f.id) }}
                className="group flex min-h-[150px] flex-col justify-between rounded-[24px] border border-line bg-card p-6 transition-colors hover:bg-surface-2"
              >
                {f.cover_images.length ? (
                  <span className="grid size-10 place-items-center overflow-hidden rounded-2xl bg-accent">
                    <img src={f.cover_images[0]} alt="" className="size-full object-cover" />
                  </span>
                ) : (
                  <span className="grid size-10 place-items-center rounded-2xl bg-accent text-primary">
                    <Folder className="size-5" aria-hidden />
                  </span>
                )}
                <span>
                  <span className="block font-serif text-lg text-foreground group-hover:underline">{f.name}</span>
                  <span className="mt-0.5 block text-[10px] uppercase tracking-widest text-muted-foreground">
                    {f.hanger_count} hangers
                  </span>
                </span>
              </Link>
            ))}
            {newName === null ? (
              <button
                onClick={() => setNewName("")}
                className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-[24px] border-2 border-dashed border-line text-sm text-muted-foreground hover:bg-surface-2"
              >
                <Plus className="size-5" aria-hidden />
                New folder
                <span className="px-4 text-center text-[11px] text-muted-foreground">Office edit, Goa trip, sangeet…</span>
              </button>
            ) : (
              <form
                className="flex min-h-[150px] flex-col justify-center gap-3 rounded-[24px] border border-line bg-card p-4"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const name = newName.trim();
                  setNewName(null);
                  if (name && (await createFolder(name))) toast.success(`“${name}” is ready`);
                }}
              >
                <input
                  autoFocus
                  aria-label="Folder name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Folder name"
                  maxLength={60}
                  className="h-11 rounded-full border border-line bg-background px-4 text-sm"
                />
                <Button type="submit" size="sm">Create</Button>
              </form>
            )}
          </div>
        </section>

        {rail && (
          <section className="mb-12">
            {rail.member_linked ? (
              <div className="flex flex-col gap-4 rounded-[24px] membership-card p-8 sm:flex-row sm:items-center">
                <BadgeCheck className="size-8 shrink-0" aria-hidden />
                <div className="flex-1">
                  <p className="font-serif text-2xl">Membership linked</p>
                  <p className="mt-1 text-sm opacity-80">Your in-store purchases land on your rail automatically.</p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4 rounded-[24px] membership-card p-8 sm:flex-row sm:items-center">
                <CreditCard className="size-8 shrink-0" aria-hidden />
                <div className="flex-1">
                  <p className="font-serif text-2xl">Link your membership</p>
                  <p className="mt-1 text-sm opacity-80">
                    Bring in everything you've bought at Urban Thread, online and in store.
                    <span className="italic"> Demo: a sample purchase history is added.</span>
                  </p>
                </div>
                <Button
                  variant="outline"
                  className="shrink-0"
                  disabled={linking}
                  onClick={async () => {
                    setLinking(true);
                    const r = await linkMembership();
                    setLinking(false);
                    if (r) toast.success(`${r.added} pieces from your purchases are on your rail`);
                  }}
                >
                  {linking && <Loader2 className="animate-spin" />} Link membership
                </Button>
              </div>
            )}
          </section>
        )}


        {picks.length > 0 && (
          <section className="mb-4">
            <SectionTitle
              title={<>New in <Brand className="text-[1.35em] align-[-0.12em]" /></>}
              action={<Link to="/shop" className="text-[11px] font-semibold uppercase tracking-widest text-primary hover:underline">Visit shop</Link>}
            />
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {picks.map((p) => (
                <button key={p.id} onClick={() => openProduct(p.id)} className="group text-left">
                  <span className="mb-2.5 block aspect-[4/5] overflow-hidden rounded-[16px] border border-line bg-surface-2">
                    <img
                      src={p.image_url}
                      alt={p.name}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                    />
                  </span>
                  <span className="flex flex-col gap-1">
                    <span className="truncate text-[13px] font-medium leading-snug">{p.name}</span>
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{p.primary_color.replace(/_/g, " ")}</span>
                      <span className="font-serif text-[13px] font-semibold text-primary">{inr(p.price_inr)}</span>
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
