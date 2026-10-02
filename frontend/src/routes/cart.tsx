import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Loader2, Minus, Plus, Truck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageHead, SectionHead, Status } from "@/components/wiw/bits";
import { inr } from "@/lib/api";
import { checkout, setQty, useStore } from "@/lib/store";
import { openProduct } from "@/lib/ui";

export const Route = createFileRoute("/cart")({
  head: () => ({ meta: [{ title: "Your bag & orders · Atelier" }] }),
  component: CartPage,
});

function CartPage() {
  const cart = useStore((s) => s.cart);
  const totals = useStore((s) => s.cartTotals);
  const orders = useStore((s) => s.orders);
  const [placing, setPlacing] = useState(false);

  return (
    <>
      <PageHead eyebrow="Urban Thread" title="Your bag" />
      {cart.length === 0 ? (
        <div className="rounded-[20px] border border-dashed border-border p-12 text-center">
          <p className="display text-2xl">Your bag is empty</p>
          <Button asChild variant="hero" className="mt-6"><Link to="/shop">Go shopping</Link></Button>
        </div>
      ) : (
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
          <ul className="divide-y divide-border border-y border-border">
            {cart.map((c) => (
              <li key={c.id} className="flex gap-4 py-5">
                <button onClick={() => openProduct(c.product.id)} className="shrink-0">
                  <img src={c.product.image_url} alt={c.product.name} className="h-32 w-24 rounded-[14px] object-cover" />
                </button>
                <div className="min-w-0 flex-1">
                  <p className="font-serif text-lg font-light leading-tight">{c.product.name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Size {c.size}</p>
                  <div className="mt-1">
                    {c.in_stock ? (c.stock <= 2 ? <Status kind="warn">Only {c.stock} left</Status> : <Status kind="ok">In stock</Status>) : <Status kind="danger">Sold out</Status>}
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-1 rounded-full border border-border">
                      <Button variant="ghost" size="icon" aria-label={c.qty === 1 ? `Remove ${c.product.name}` : "Decrease quantity"} onClick={() => void setQty(c.id, c.qty - 1)}><Minus /></Button>
                      <span className="w-6 text-center text-sm" aria-live="polite">{c.qty}</span>
                      <Button variant="ghost" size="icon" aria-label="Increase quantity" onClick={() => void setQty(c.id, c.qty + 1)}><Plus /></Button>
                    </div>
                    <span className="font-semibold">{inr(c.line_total_inr)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {totals && (
            <aside className="h-fit rounded-[20px] border border-border bg-card p-6">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between"><dt className="text-muted-foreground">Subtotal</dt><dd>{inr(totals.subtotal_inr)}</dd></div>
                {totals.savings_inr > 0 && <div className="flex justify-between"><dt className="text-muted-foreground">You save</dt><dd>{inr(totals.savings_inr)}</dd></div>}
                <div className="flex justify-between"><dt className="text-muted-foreground">Shipping</dt><dd>{totals.shipping_inr ? inr(totals.shipping_inr) : "Free"}</dd></div>
                <div className="flex justify-between border-t border-border pt-3 text-base font-semibold"><dt>Total</dt><dd>{inr(totals.total_inr)}</dd></div>
              </dl>
              <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground"><Truck className="size-4" aria-hidden /> Delivery to {totals.city} in about {totals.delivery_days} days</p>
              <Button
                variant="hero"
                className="mt-6 w-full"
                disabled={placing}
                onClick={async () => {
                  setPlacing(true);
                  const o = await checkout();
                  setPlacing(false);
                  if (o) toast.success(`Order #${o.id} placed. Demo order, no payment taken.`);
                }}
              >
                {placing && <Loader2 className="animate-spin" />} Place order
              </Button>
              <p className="mt-3 text-center text-[11px] text-muted-foreground">Demo checkout: no payment is taken.</p>
            </aside>
          )}
        </div>
      )}

      <section className="mt-16">
        <SectionHead title="Orders" meta={`${orders.length}`} />
        {orders.length === 0 ? (
          <p className="text-sm text-muted-foreground">No orders yet.</p>
        ) : (
          <ul className="space-y-3">
            {orders.map((o) => (
              <li key={o.id} className="flex items-center gap-4 rounded-[16px] border border-border bg-card p-4">
                <div className="flex -space-x-3">
                  {o.items.slice(0, 3).map((i, k) => <img key={k} src={i.product.image_url} alt="" className="size-12 rounded-full border-2 border-card object-cover" />)}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">Order #{o.id}</p>
                  <p className="text-xs text-muted-foreground">{new Date(o.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} · {o.items.length} pieces</p>
                </div>
                <Status kind="ok">{o.status === "delivered" ? "Delivered" : "Confirmed"}</Status>
                <span className="text-sm font-semibold">{inr(o.total_inr)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
