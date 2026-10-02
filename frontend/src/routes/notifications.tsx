import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { PageHead } from "@/components/wiw/bits";
import { markAllRead, useStore } from "@/lib/store";
import { openProduct } from "@/lib/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/notifications")({
  head: () => ({ meta: [{ title: "Notifications · Atelier" }] }),
  component: Notifications,
});

function Notifications() {
  const items = useStore((s) => s.notifications);
  return (
    <>
      <PageHead
        eyebrow="Updates"
        title="Notifications"
        actions={items.some((n) => !n.read) && <Button variant="outline" onClick={() => void markAllRead()}>Mark all read</Button>}
      />
      {items.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          Nothing yet. Price drops, restocks in your size and order updates for your wardrobe land here.
        </p>
      ) : (
        <ul className="divide-y divide-border border-y border-border">
          {items.map((n) => (
            <li key={n.id} className="flex gap-4 py-5">
              <span className={cn("mt-2 size-2 shrink-0 rounded-full", n.read ? "bg-border" : "bg-primary")} aria-label={n.read ? "Read" : "Unread"} />
              {n.product && (
                <button onClick={() => openProduct(n.product!.id)} className="shrink-0">
                  <img src={n.product.image_url} alt={n.product.name} className="size-14 rounded-[10px] object-cover" />
                </button>
              )}
              <div className="flex-1">
                <p className={cn("text-sm", !n.read && "font-semibold")}>{n.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{n.body}</p>
              </div>
              <time className="text-xs text-muted-foreground">{new Date(n.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</time>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
