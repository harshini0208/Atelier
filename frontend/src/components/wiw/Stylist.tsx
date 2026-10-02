import { useEffect, useRef, useState } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { errorText, inr } from "@/lib/api";
import { confirmChat, getChat, lookToCart, saveLookApi, sendChat, type ChatMessage, type Outfit } from "@/lib/data";
import { refreshCart, refreshMe, refreshRail, useStore } from "@/lib/store";
import { openProduct, openStylist } from "@/lib/ui";

const RAIL_SUGGESTIONS = [
  "Style my rail for a weekend brunch",
  "What can I wear to work this week?",
  "Find me a blazer under ₹4,000",
];
const FOLDER_SUGGESTIONS = [
  "Make it work for a beach wedding under ₹5,000",
  "Make it more casual",
  "Put it on my board",
  "Add the look to my cart",
];

/** Which folder the stylist is talking about: the open folder page, or a folder's style board. */
export function useStylistFolder(): number | null {
  const loc = useRouterState({ select: (s) => s.location });
  const m = loc.pathname.match(/^\/folders\/(\d+)/);
  if (m) return Number(m[1]);
  const f = (loc.search as { folder?: number }).folder;
  return loc.pathname === "/board" && f ? Number(f) : null;
}

export function OutfitCard({ outfit, folderId }: { outfit: Outfit; folderId: number | null }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toBuy = outfit.items.filter((i) => !i.owned);
  const total = outfit.total_inr;
  const ids = outfit.items.map((i) => i.product.id);
  const board = useMutation({
    mutationFn: () => saveLookApi(folderId, outfit.occasion ? `For ${outfit.occasion}` : "Stylist pick", ids, outfit.occasion ?? ""),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["looks"] });
      openStylist(false);
      await navigate({ to: "/board", search: folderId ? { folder: folderId } : {} });
    },
    onError: (e) => toast.error(errorText(e)),
  });
  const cart = useMutation({
    mutationFn: () => lookToCart(folderId, toBuy.map((i) => i.product.id)),
    onSuccess: async (r) => {
      await Promise.all([refreshCart(), refreshRail()]);
      toast.success(
        `${r.added.length} piece${r.added.length === 1 ? "" : "s"} added to your bag` +
          (r.needs_size.length ? `. Pick a size for ${r.needs_size.map((n) => n.product.name).join(", ")}` : ""),
      );
    },
    onError: (e) => toast.error(errorText(e)),
  });
  return (
    <div className="mt-3 rounded-[16px] border border-border bg-background p-3">
      <div className="grid grid-cols-4 gap-2">
        {outfit.items.map((i) => (
          <button key={i.product.id} className="min-w-0 text-left" onClick={() => openProduct(i.product.id)} title={i.why ?? i.product.name}>
            <div className="aspect-[3/4] overflow-hidden rounded-[10px] bg-muted">
              <img src={i.product.image_url} alt={i.product.name} className="h-full w-full object-cover" />
            </div>
            <p className="mt-1 truncate text-[10px] text-muted-foreground">
              {i.owned ? "Yours" : inr(i.product.price_inr)}
            </p>
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">To buy</span>
        <span className="font-semibold">{toBuy.length === 0 ? "All yours" : inr(total)}</span>
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="outline" size="sm" className="flex-1" disabled={board.isPending} onClick={() => board.mutate()}>
          {board.isPending && <Loader2 className="animate-spin" />} Open on board
        </Button>
        {toBuy.length > 0 && (
          <Button size="sm" className="flex-1" disabled={cart.isPending} onClick={() => cart.mutate()}>
            {cart.isPending && <Loader2 className="animate-spin" />}
            {toBuy.length < outfit.items.length ? `Add ${toBuy.length} to cart` : "Add look to cart"}
          </Button>
        )}
      </div>
    </div>
  );
}

function Pending({ m, folderId }: { m: ChatMessage; folderId: number | null }) {
  const qc = useQueryClient();
  const go = useMutation({
    mutationFn: (accept: boolean) => confirmChat(m.id, accept),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["chat", folderId] });
      await refreshMe();
    },
    onError: (e) => toast.error(errorText(e)),
  });
  const p = m.payload.pending_preferences;
  if (!p) return null;
  return (
    <div className="mt-2 rounded-[14px] border border-border bg-card p-3 text-xs">
      <p className="mb-2">Save to your preferences: <b>{p.summary}</b>?</p>
      <div className="flex gap-2">
        <Button size="sm" disabled={go.isPending} onClick={() => go.mutate(true)}><Check /> Save</Button>
        <Button size="sm" variant="outline" disabled={go.isPending} onClick={() => go.mutate(false)}>Keep as is</Button>
      </div>
    </div>
  );
}

export function StylistPanel() {
  const folderId = useStylistFolder();
  const folderName = useStore((s) => s.folders.find((f) => f.id === folderId)?.name);
  const qc = useQueryClient();
  const key = ["chat", folderId] as const;
  const { data: chat = [] } = useQuery({ queryKey: key, queryFn: () => getChat(folderId) });
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const send = useMutation({
    mutationFn: (message: string) => sendChat(message, folderId),
    onMutate: (message) => {
      qc.setQueryData<ChatMessage[]>(key, (old = []) => [
        ...old,
        { id: -Date.now(), role: "user", content: message, payload: {}, created_at: "" },
      ]);
    },
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["looks"] });
      void refreshCart();
      void refreshMe();
    },
    onError: (e) => toast.error(errorText(e)),
  });
  useEffect(() => {
    // scrollIntoView returns a Promise in recent Chrome; an effect must not return it
    void end.current?.scrollIntoView({ block: "end" });
  }, [chat.length, send.isPending]);

  const submit = (t: string) => {
    if (!t.trim() || send.isPending) return;
    send.mutate(t.trim());
    setText("");
  };
  const suggestions = folderId ? FOLDER_SUGGESTIONS : RAIL_SUGGESTIONS;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border px-5 py-4">
        <p className="eyebrow">Urban Thread{folderName ? ` · ${folderName}` : ""}</p>
        <p className="display text-xl">Your stylist</p>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5" aria-live="polite">
        {chat.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="ml-8 rounded-[16px] rounded-br-sm bg-primary px-4 py-3 text-sm text-primary-foreground">
              {m.content}
            </div>
          ) : (
            <div key={m.id} className="mr-2">
              <div className="rounded-[16px] rounded-bl-sm bg-card px-4 py-3 text-sm leading-relaxed">{m.content}</div>
              {m.payload?.outfit && m.payload.outfit.items.length > 0 && <OutfitCard outfit={m.payload.outfit} folderId={folderId} />}
              {!!m.payload?.products?.length && (
                <div className="no-scrollbar mt-3 flex gap-2 overflow-x-auto">
                  {m.payload.products.map((p) => (
                    <button key={p.id} onClick={() => openProduct(p.id)} className="w-24 shrink-0 text-left">
                      <span className="block aspect-[3/4] overflow-hidden rounded-[10px] bg-muted">
                        <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" />
                      </span>
                      <span className="mt-1 block truncate text-[10px]">{p.name}</span>
                      <span className="block text-[10px] text-muted-foreground">{inr(p.price_inr)}</span>
                    </button>
                  ))}
                </div>
              )}
              <Pending m={m} folderId={folderId} />
              {m.payload?.actions?.map((a) => (
                <p key={a} className="mt-2 inline-flex items-center gap-1 text-[11px] text-ok"><Check className="size-3" /> {a}</p>
              ))}
            </div>
          ),
        )}
        {send.isPending && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Styling…
          </p>
        )}
        <div ref={end} />
      </div>
      <div className="border-t border-border px-4 py-3">
        <div className="no-scrollbar mb-3 flex gap-2 overflow-x-auto">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="min-h-9 shrink-0 rounded-full border border-border bg-card px-3 text-[11px] text-muted-foreground hover:text-foreground"
            >
              {s}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(text);
          }}
          className="flex items-center gap-2"
        >
          <label htmlFor="stylist-input" className="sr-only">
            Message your stylist
          </label>
          <input
            id="stylist-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={800}
            placeholder={folderId ? "Occasion, budget, how you'll wear it…" : "Style my rail, or find something…"}
            className="h-11 min-w-0 flex-1 rounded-full border border-border bg-card px-4 text-sm placeholder:text-muted-foreground focus:outline-2 focus:outline-primary"
          />
          <Button type="submit" size="icon" variant="hero" aria-label="Send" disabled={send.isPending || !text.trim()}>
            <ArrowUp />
          </Button>
        </form>
      </div>
    </div>
  );
}
