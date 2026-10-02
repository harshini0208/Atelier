import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { ArrowLeft, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Status } from "@/components/wiw/bits";
import { api, errorText, inr } from "@/lib/api";
import { getInspo, getPieceMatches, hangPiece, unhangPiece, uploadInspo } from "@/lib/data";
import { createFolder, refreshFolders, refreshRail, useStore } from "@/lib/store";
import { openProduct, takePendingInspo } from "@/lib/ui";
import type { Inspo, MatchItem, PieceMatches } from "@/lib/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/inspo")({
  validateSearch: z.object({ id: z.number().optional() }),
  head: () => ({ meta: [{ title: "Shop a look you saw · Atelier" }] }),
  component: InspoPage,
});

const STEPS = ["Finding the pieces in your outfit…", "Reading colours, fabrics and fit…", "Drawing boxes around each piece…", "Almost there…"];

function Analyzing({ src }: { src: string | null }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setI((x) => Math.min(x + 1, STEPS.length - 1)), 2600);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center gap-4 py-10 text-center" role="status" aria-live="polite">
      <div className="w-56 overflow-hidden rounded-[20px] bg-muted">
        {src ? <img src={src} alt="Your uploaded inspiration" className="aspect-[9/16] w-full object-cover opacity-80" /> : <div className="shimmer aspect-[9/16]" />}
      </div>
      <p className="flex items-center gap-2 text-sm font-medium"><Loader2 className="size-4 animate-spin" /> {STEPS[i]}</p>
      <p className="text-xs text-muted-foreground">We only look at clothing, never at who's wearing it.</p>
    </div>
  );
}

function InspoPage() {
  const { id } = Route.useSearch();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<string | null>(null);
  const started = useRef(false);
  const upload = useMutation({
    mutationFn: ({ file, folderId }: { file: File; folderId: number | null }) => uploadInspo(file, folderId),
    onSuccess: (i) => void navigate({ to: "/inspo", search: { id: i.id }, replace: true }),
    onError: (e) => toast.error(errorText(e)),
  });
  useEffect(() => {
    if (id || started.current) return;
    const p = takePendingInspo();
    if (!p) return;
    started.current = true;
    setPreview(URL.createObjectURL(p.file));
    upload.mutate(p);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!id) {
    if (upload.isPending || (started.current && !upload.isError)) return <Analyzing src={preview} />;
    return (
      <div className="py-20 text-center">
        <p className="display text-3xl">Upload a screenshot to start</p>
        <p className="mt-3 text-sm text-muted-foreground">Saw an outfit you love? Upload it from your wardrobe and we'll find each piece in store.</p>
        <Button asChild variant="hero" className="mt-6"><Link to="/">Back to wardrobe</Link></Button>
      </div>
    );
  }
  return <Review inspoId={id} />;
}

function Review({ inspoId }: { inspoId: number }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const folders = useStore((s) => s.folders);
  const { data: inspo, error } = useQuery({ queryKey: ["inspo", inspoId], queryFn: () => getInspo(inspoId) });
  const [active, setActive] = useState<number | null>(null);
  const [folderId, setFolderId] = useState<number | null>(null);
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const [liked, setLiked] = useState<Set<number>>(new Set());   // tapped before a folder was chosen
  const [nudge, setNudge] = useState<string | null>(null);

  useEffect(() => {
    if (inspo?.folder_id && folderId === null) setFolderId(inspo.folder_id);
    if (inspo && active === null) setActive(inspo.pieces[0]?.id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inspo]);

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["inspo", inspoId] }),
      qc.invalidateQueries({ queryKey: ["piece-matches"] }),
      qc.invalidateQueries({ queryKey: ["unfiled"] }),
      refreshFolders(),
      refreshRail(),
    ]);
  };

  /** Liking a piece hangs its best store match in the chosen folder. */
  const autoHang = async (pid: number, fid: number) => {
    const m = await qc.fetchQuery({ queryKey: ["piece-matches", pid], queryFn: () => getPieceMatches(inspoId, pid) });
    if (m.hanger) return;
    const top = (m.for_you[0] ?? m.also_view[0])?.product;
    await hangPiece(inspoId, pid, top?.id ?? (null as unknown as string), fid);
    toast.success(top ? `${top.name} is on your hanger` : "Saved as a wish: nothing close in store yet");
  };
  const pick = (pid: number) => {
    setActive(pid);
    setNudge(null);
    const hung = inspo?.pieces.find((p) => p.id === pid)?.selected;
    if (hung) return;
    if (folderId) void autoHang(pid, folderId).then(refresh).catch((e) => toast.error(errorText(e)));
    else setLiked((s) => new Set(s).add(pid));
  };
  useEffect(() => {
    // a folder was just chosen: hang everything liked so far
    if (!folderId || liked.size === 0) return;
    const pending = [...liked];
    setLiked(new Set());
    void Promise.all(pending.map((pid) => autoHang(pid, folderId))).then(refresh).catch((e) => toast.error(errorText(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folderId]);

  const done = useMutation({
    mutationFn: async () => {
      const fresh = await qc.fetchQuery({ queryKey: ["inspo", inspoId], queryFn: () => getInspo(inspoId) });
      const ids = fresh.pieces.filter((p) => p.selected).map((p) => p.id);
      return api.post(`/inspo/${inspoId}/select`, { piece_ids: ids, folder_id: folderId });
    },
    onSuccess: async () => {
      await refresh();
      const target = folderId ?? inspo?.folder_id;
      await navigate(target ? { to: "/folders/$id", params: { id: String(target) } } : { to: "/" });
    },
    onError: (e) => toast.error(errorText(e)),
  });

  if (error) return <p className="py-20 text-center text-sm text-muted-foreground">{errorText(error)}</p>;
  if (!inspo) return <div className="shimmer h-96 rounded-[24px]" />;
  const hungCount = inspo.pieces.filter((p) => p.selected).length;
  const piece = inspo.pieces.find((p) => p.id === active) ?? null;
  const visible = inspo.pieces.filter((p) => p.box && !(p.manual && p.box[0] === 0 && p.box[2] === 1000));

  const finish = () => {
    if (liked.size && !folderId) return setNudge("Choose a folder to save the pieces you liked.");
    if (!hungCount && !liked.size) return setNudge("Tap the pieces you like first. Each one goes onto a hanger in your folder.");
    done.mutate();
  };

  return (
    <>
      <Link
        to={inspo.folder_id ? "/folders/$id" : "/"}
        params={{ id: String(inspo.folder_id ?? "") }}
        className="mb-6 inline-flex min-h-11 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {inspo.folder_id ? "Back to folder" : "Home"}
      </Link>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="relative mx-auto w-full max-w-sm self-start overflow-hidden rounded-[24px] border border-border bg-muted">
          <img src={inspo.image_url} alt="Your inspo screenshot" className="block w-full" />
          {visible.map((p) => {
            const [y0, x0, y1, x1] = p.box!;
            const on = active === p.id;
            return (
              <button
                key={p.id}
                onClick={() => pick(p.id)}
                aria-label={`${p.subcategory_label}: see store matches`}
                aria-pressed={on || !!p.selected}
                className={cn(
                  "absolute rounded-[10px] border-2 transition-colors",
                  on ? "border-primary bg-primary/10" : p.selected ? "border-ok" : "border-card/90 hover:border-primary",
                )}
                style={{ left: `${x0 / 10}%`, top: `${y0 / 10}%`, width: `${(x1 - x0) / 10}%`, height: `${(y1 - y0) / 10}%` }}
              >
                <span className="absolute -top-3 left-1 rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold text-primary-foreground">
                  {p.selected ? "✓ " : ""}{p.subcategory_label}
                </span>
              </button>
            );
          })}
        </div>

        <div>
          <p className="eyebrow mb-3">Tap a piece you love</p>
          <h1 className="display text-4xl sm:text-5xl">{inspo.pieces.length} piece{inspo.pieces.length === 1 ? "" : "s"} in this look</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Tap each piece you like. We hang its closest Urban Thread piece in your folder, and show the other options so you can swap.
          </p>
          {inspo.status !== "analyzed" && inspo.message && (
            <p className="mt-4 rounded-[14px] bg-muted p-3 text-sm"><Status kind="warn">{inspo.message}</Status></p>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            {inspo.pieces.map((p) => (
              <button key={p.id} onClick={() => pick(p.id)} aria-pressed={active === p.id}
                className={cn("flex min-h-11 items-center gap-2 rounded-full border px-2 pr-3 text-xs", active === p.id ? "border-primary bg-accent text-accent-foreground" : "border-border bg-card")}>
                {p.crop_url && <img src={p.crop_url} alt="" className="size-7 rounded-full object-cover" />}
                {p.selected && <Check className="size-3.5 text-ok" aria-label="On a hanger" />}
                {p.name}
              </button>
            ))}
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
            <label htmlFor="hang-in" className="text-muted-foreground">Hang pieces in</label>
            {newFolder === null ? (
              <select id="hang-in" value={folderId ?? ""} onChange={(e) => (e.target.value === "new" ? setNewFolder("") : setFolderId(Number(e.target.value)))}
                className={cn("h-11 rounded-full border bg-card px-4 text-sm", folderId ? "border-border" : "border-warn")}>
                <option value="" disabled>Choose a folder…</option>
                {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                <option value="new">+ New folder…</option>
              </select>
            ) : (
              <form className="flex gap-2" onSubmit={async (e) => {
                e.preventDefault();
                if (!newFolder.trim()) return;
                const f = await createFolder(newFolder.trim());
                setNewFolder(null);
                if (f) setFolderId(f.id);
              }}>
                <input autoFocus aria-label="New folder name" value={newFolder} onChange={(e) => setNewFolder(e.target.value)} maxLength={60}
                  placeholder="Folder name" className="h-11 rounded-full border border-border bg-card px-4 text-sm" />
                <Button type="submit" variant="outline">Create</Button>
              </form>
            )}
          </div>
          {liked.size > 0 && !folderId && (
            <p className="mt-2 text-xs text-warn">You liked {liked.size} piece{liked.size > 1 ? "s" : ""}. Choose a folder and we'll hang them.</p>
          )}

          {piece ? (
            <PieceMatchesPanel inspoId={inspoId} pieceId={piece.id} folderId={folderId} onChange={refresh} />
          ) : (
            <p className="mt-8 rounded-[20px] border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Tap a box on the image or a piece above to see what's in store.
            </p>
          )}
          {nudge && <p className="mt-6 text-sm text-warn">{nudge}</p>}
          <Button variant="hero" className="mt-6 w-full" disabled={done.isPending} onClick={finish}>
            {done.isPending ? <Loader2 className="animate-spin" /> : <Check />}
            {hungCount ? `Done: ${hungCount} piece${hungCount === 1 ? "" : "s"} on hangers` : "Done"}
          </Button>
        </div>
      </div>
    </>
  );
}

function PieceMatchesPanel({ inspoId, pieceId, folderId, onChange }: { inspoId: number; pieceId: number; folderId: number | null; onChange: () => Promise<void> }) {
  const { data: m } = useQuery({ queryKey: ["piece-matches", pieceId], queryFn: () => getPieceMatches(inspoId, pieceId) });
  const hang = useMutation({
    mutationFn: (productId: string | null) => hangPiece(inspoId, pieceId, productId as string, folderId),
    onSuccess: async () => {
      await onChange();
      toast.success("On your hanger");
    },
    onError: (e) => toast.error(errorText(e)),
  });
  const unhang = useMutation({
    mutationFn: () => unhangPiece(inspoId, pieceId),
    onSuccess: onChange,
    onError: (e) => toast.error(errorText(e)),
  });
  if (!m) return <div className="shimmer mt-8 h-64 rounded-[20px]" />;
  const chosen = m.hanger?.chosen_product_id ?? null;
  const canHang = !!folderId || !!m.hanger;
  return (
    <div className="mt-8 space-y-8">
      {m.gap_message && (
        <div className="rounded-[16px] border border-border bg-card p-4 text-sm">
          <Status kind="warn">{m.gap_message}</Status>
          {!m.hanger && (
            <Button size="sm" variant="outline" className="mt-3" disabled={!canHang || hang.isPending} onClick={() => hang.mutate(null)}>
              Save as a wish
            </Button>
          )}
        </div>
      )}
      <MatchRow title="For you" note="Fits the look and your preferences" items={m.for_you} chosen={chosen} disabled={!canHang || hang.isPending}
        onHang={(id) => hang.mutate(id)} />
      <MatchRow title="Also view" note="Great matches outside your size, budget or fabrics" items={m.also_view} chosen={chosen} disabled={!canHang || hang.isPending}
        onHang={(id) => hang.mutate(id)} />
      {m.hanger && (
        <Button variant="ghost" size="sm" onClick={() => unhang.mutate()} disabled={unhang.isPending}>Remove from hangers</Button>
      )}
    </div>
  );
}

function MatchRow({ title, note, items, chosen, disabled, onHang }: {
  title: string; note: string; items: MatchItem[]; chosen: string | null; disabled: boolean; onHang: (productId: string) => void;
}) {
  if (!items.length) return null;
  return (
    <section>
      <div className="mb-3 flex items-end justify-between border-b border-border pb-2">
        <h2 className="display text-2xl">{title}</h2>
        <span className="text-xs text-muted-foreground">{note}</span>
      </div>
      <ul className="no-scrollbar -mx-5 flex gap-3 overflow-x-auto px-5 pb-2 sm:mx-0 sm:px-0">
        {items.map((it) => {
          const p = it.product;
          const on = chosen === p.id;
          return (
            <li key={p.id} className="w-40 shrink-0">
              <button onClick={() => openProduct(p.id)} className={cn("block w-full overflow-hidden rounded-[16px] bg-muted", on && "ring-2 ring-primary")}>
                <img src={p.image_url} alt={p.name} className="aspect-[3/4] w-full object-cover" />
              </button>
              <p className="mt-2 line-clamp-2 text-xs font-medium">{p.name}</p>
              <p className="text-xs text-muted-foreground">{inr(p.price_inr)}</p>
              <div className="mt-1.5 space-y-1">
                {it.reasons.length
                  ? it.reasons.map((r) => <div key={r.label}><Status kind="warn">{r.label}</Status></div>)
                  : <Status kind="ok">Fits your preferences</Status>}
              </div>
              <Button size="sm" variant={on ? "default" : "outline"} className="mt-2 w-full" disabled={disabled || on} onClick={() => onHang(p.id)}>
                {on ? "On your hanger" : chosen ? "Swap to this" : "Hang it"}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export type { Inspo, PieceMatches };
