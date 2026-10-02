import { useSyncExternalStore } from "react";
import type { Product } from "./types";

type UI = { productId: string | null; hangProduct: Product | null; stylistOpen: boolean };
let ui: UI = { productId: null, hangProduct: null, stylistOpen: false };
const ls = new Set<() => void>();
const set = (p: Partial<UI>) => {
  ui = { ...ui, ...p };
  ls.forEach((l) => l());
};
export const useUI = <T,>(sel: (u: UI) => T) =>
  useSyncExternalStore(
    (l) => {
      ls.add(l);
      return () => ls.delete(l);
    },
    () => sel(ui),
    () => sel(ui),
  );
export const openProduct = (id: string | null) => set({ productId: id });
export const openHang = (p: Product | null) => set({ hangProduct: p });
export const openStylist = (v: boolean) => set({ stylistOpen: v });

/** The screenshot a shopper just picked for "Shop a look you saw", uploaded by the inspo page. */
let pendingInspo: { file: File; folderId: number | null } | null = null;
export const setPendingInspo = (file: File, folderId: number | null = null) => (pendingInspo = { file, folderId });
export const takePendingInspo = () => {
  const p = pendingInspo;
  pendingInspo = null;
  return p;
};
