import { FolderPlus, Folder } from "lucide-react";
import { inr } from "@/lib/api";
import type { RailItem } from "@/lib/types";
import { openHang, openProduct } from "@/lib/ui";
import { SourceTag } from "./bits";

const fmtDate = (s: string) =>
  new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/**
 * Wardrobe rail: each piece hangs from a thin vertical thread above its card.
 * Scrolls sideways on every screen size.
 */
export function HangingRail({ items }: { items: RailItem[] }) {
  return (
    <ul className="no-scrollbar flex gap-8 overflow-x-auto pb-2">
      {items.map((it) => {
        const src = it.sources[0];
        return (
          <li
            key={it.product.id}
            className="group relative flex w-[150px] shrink-0 flex-col items-center"
          >
            <button
              onClick={() => openProduct(it.product.id)}
              className="w-full rounded-[20px] border border-line bg-card p-1.5 transition-transform duration-300 group-hover:-translate-y-1"
            >
              <span className="relative block overflow-hidden rounded-[16px]">
                <img
                  src={it.product.image_url}
                  alt={it.product.name}
                  loading="lazy"
                  className="aspect-[3/4] w-full object-cover"
                />
                {src && (
                  <span className="absolute bottom-2 left-2">
                    <SourceTag source={src} />
                  </span>
                )}
              </span>
            </button>
            <p className="mt-3 line-clamp-1 text-center text-sm font-medium">{it.product.name}</p>
            <p className="mt-0.5 text-center text-[11px] text-muted-foreground">
              {src?.detail ? src.detail : src?.at ? fmtDate(src.at) : inr(it.product.price_inr)}
              {src?.size ? ` · ${src.size}` : ""}
            </p>
            <button
              onClick={() => openHang(it.product)}
              className="mt-2 inline-flex min-h-9 items-center gap-1.5 rounded-full border border-line px-3 text-[11px] font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground"
            >
              {it.folder_ids.length ? <Folder className="size-3.5" aria-hidden /> : <FolderPlus className="size-3.5" aria-hidden />}
              {it.folder_ids.length
                ? `In ${it.folder_ids.length} folder${it.folder_ids.length > 1 ? "s" : ""}`
                : "Add to folders"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
