/**
 * The shopper's session, mirrored from the API: profile, rail, folders and their hangers, wishlist, cart, orders,
 * notifications and mannequin. Screens read it with useStore(selector); every change goes to the API first and the
 * affected slices are reloaded from the server, so what you see is what is saved.
 */
import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { api, errorText } from "./api";
import {
  getCart,
  getFolder,
  getFolders,
  getMannequin,
  getMe,
  getNotifications,
  getOrders,
  getRail,
  getWishlist,
  type Cart,
  type CartItem,
  type Notification,
  type Order,
} from "./data";
import type { FolderSummary, Inspo, Me, Product, Rail } from "./types";

export const THEMES = [
  { id: "sky-studio", label: "Sky Studio" },
  { id: "blush-noir", label: "Blush Noir" },
  { id: "espresso-peony", label: "Espresso Peony" },
  { id: "oat-wine", label: "Oat & Wine" },
  { id: "rose-gold-noir", label: "Rose Gold Noir" },
] as const;
export type ThemeId = (typeof THEMES)[number]["id"];

/** A hanger in a folder: the store product it holds, and where it came from. */
export type FolderHanger = { id: number; folderId: number; product: Product; fromInspo: boolean; size: string | null };

type State = {
  ready: boolean;
  me: Me | null;
  rail: Rail | null;
  folders: FolderSummary[];
  hangers: FolderHanger[];
  folderInspo: Record<number, Inspo[]>;
  wishlist: string[];
  cart: CartItem[];
  cartTotals: Omit<Cart, "groups"> | null;
  orders: Order[];
  notifications: Notification[];
  mannequin: { body: string; tone: string };
};

let state: State = {
  ready: false,
  me: null,
  rail: null,
  folders: [],
  hangers: [],
  folderInspo: {},
  wishlist: [],
  cart: [],
  cartTotals: null,
  orders: [],
  notifications: [],
  mannequin: { body: "slim", tone: "tan" },
};

const listeners = new Set<() => void>();
function set(patch: Partial<State> | ((s: State) => Partial<State>)) {
  state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
  listeners.forEach((l) => l());
}
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
export function useStore<T>(sel: (s: State) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => sel(state),
    () => sel(state),
  );
}
export const getState = () => state;

/** Run an API change; on failure show why (and keep the screen as the server has it). */
async function act<T>(fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn();
  } catch (e) {
    toast.error(errorText(e));
    return undefined;
  }
}

/* ---------- loading ---------- */
const setCart = (c: Cart) => {
  const { groups, ...totals } = c;
  set({ cart: groups.flatMap((g) => g.items), cartTotals: totals });
};
export async function refreshRail() {
  set({ rail: await getRail(), wishlist: await getWishlist() });
}
export async function refreshFolders() {
  const folders = await getFolders();
  const details = await Promise.all(folders.map((f) => getFolder(f.id)));
  const hangers: FolderHanger[] = [];
  const folderInspo: Record<number, Inspo[]> = {};
  for (const d of details) {
    folderInspo[d.id] = d.inspo;
    for (const h of d.hangers) {
      const product = h.chosen_product ?? h.top_match?.product;
      if (product)
        hangers.push({ id: h.id, folderId: d.id, product, fromInspo: !h.from_rail, size: h.chosen_size });
    }
  }
  set({ folders, hangers, folderInspo });
}
export async function refreshCart() {
  setCart(await getCart());
}
export async function refreshOrders() {
  set({ orders: await getOrders() });
}
export async function refreshNotifications() {
  set({ notifications: await getNotifications() });
}
export async function refreshMe() {
  set({ me: await getMe() });
}

let loading: Promise<void> | null = null;
export function loadSession(force = false) {
  if (loading && !force) return loading;
  loading = (async () => {
    const [me, mannequin] = await Promise.all([getMe(), getMannequin()]);
    set({ me, mannequin: { body: mannequin.body_type, tone: mannequin.skin_tone } });
    await Promise.all([refreshRail(), refreshFolders(), refreshCart(), refreshOrders(), refreshNotifications()]);
    set({ ready: true });
  })();
  return loading;
}
export function resetSession() {
  loading = null;
  set({ ready: false, me: null, rail: null, folders: [], hangers: [], folderInspo: {}, cart: [], orders: [], notifications: [] });
}

/* ---------- theme ---------- */
export function applyTheme(id: ThemeId) {
  document.documentElement.dataset["theme"] = id;
  try {
    localStorage.setItem("wiw.theme.v3", id);
  } catch {
    /* ignore */
  }
}
export function savedTheme(): ThemeId {
  try {
    const t = localStorage.getItem("wiw.theme.v3");
    if (t && THEMES.some((x) => x.id === t)) return t as ThemeId;
  } catch {
    /* ignore */
  }
  return "sky-studio";
}

/* ---------- profile ---------- */
export async function updateProfile(patch: { name: string; city: string }) {
  const r = await act(() => api.patch<{ name: string; city: string }>("/me", patch));
  if (r) set((s) => ({ me: s.me ? { ...s.me, ...r } : s.me }));
  return !!r;
}
export async function setMannequin(body: string, tone: string) {
  set({ mannequin: { body, tone } });
  await act(() => api.put("/mannequin", { body_type: body, skin_tone: tone }));
}

/* ---------- folders ---------- */
export async function createFolder(name: string, description = ""): Promise<FolderSummary | undefined> {
  const f = await act(() => api.post<FolderSummary>("/folders", { name, description }));
  if (f) set((s) => ({ folders: [...s.folders, f] }));
  return f;
}
/** Hang one piece in exactly these folders (and take it out of the others). */
export async function setPieceFolders(product: Product, folderIds: number[], size: string | null = null) {
  const r = await act(() => api.put(`/rail/${product.id}/folders`, { folder_ids: folderIds, size }));
  if (r) await Promise.all([refreshRail(), refreshFolders()]);
  return !!r;
}
export async function removeHanger(id: number) {
  const r = await act(() => api.del(`/hangers/${id}`));
  if (r) await Promise.all([refreshFolders(), refreshRail()]);
}
export async function moveHanger(id: number, folderId: number) {
  const r = await act(() => api.patch(`/hangers/${id}`, { folder_id: folderId }));
  if (r) await Promise.all([refreshFolders(), refreshRail()]);
}

/* ---------- wishlist / cart ---------- */
export async function toggleWish(id: string) {
  const on = state.wishlist.includes(id);
  set((s) => ({ wishlist: on ? s.wishlist.filter((x) => x !== id) : [...s.wishlist, id] }));
  const r = await act(() => (on ? api.del(`/wishlist/${id}`) : api.post("/wishlist", { product_id: id })));
  await refreshRail();
  if (r) toast.success(on ? "Removed from your wishlist" : "On your rail");
}
export async function addToCart(product: Product, size: string) {
  const c = await act(() => api.post<Cart>("/cart", { product_id: product.id, size, qty: 1 }));
  if (c) {
    setCart(c);
    void refreshRail();
  }
  return !!c;
}
export async function setQty(id: number, qty: number) {
  const c = await act(() => api.patch<Cart>(`/cart/${id}`, { qty }));
  if (c) setCart(c);
}
export async function checkout() {
  const o = await act(() => api.post<Order>("/checkout"));
  if (o) await Promise.all([refreshCart(), refreshOrders(), refreshNotifications(), refreshRail()]);
  return o;
}
export async function markAllRead() {
  await act(() => api.post("/notifications/read"));
  await refreshNotifications();
}
export async function linkMembership() {
  const r = await act(() => api.post<{ added: number; rail: Rail }>("/membership/link"));
  if (r) {
    set({ rail: r.rail });
    void refreshOrders();
  }
  return r;
}
