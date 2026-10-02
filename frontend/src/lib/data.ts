/** Typed calls to the Walk-In Wardrobe API (same origin; see lib/api.ts). */
import { api, MEDIA_BASE } from "./api";
import type { FolderDetail, FolderSummary, Inspo, Look, Me, PieceMatches, Product, ProductDetail, Rail, Vocab } from "./types";

export type CartItem = {
  id: number;
  product: Product;
  size: string;
  qty: number;
  line_total_inr: number;
  in_stock: boolean;
  stock: number;
};
export type Cart = {
  groups: { brand: string; store_id: string; items: CartItem[]; subtotal_inr: number; delivery_days: number }[];
  count: number;
  subtotal_inr: number;
  savings_inr: number;
  shipping_inr: number;
  total_inr: number;
  city: string;
  delivery_days: number;
};
export type OutfitItem = {
  hanger_index: number;
  hanger_id: number | null;
  piece_name: string;
  slot: string;
  product: Product;
  owned?: boolean;
  why?: string;
  reasons?: { code: string; label: string }[];
};
export type Outfit = {
  items: OutfitItem[];
  total_inr: number;
  occasion?: string | null;
  owned_count?: number;
  reason?: string;
  within_budget?: boolean;
  over_by_inr?: number;
  max_total_inr?: number | null;
  gaps?: string[];
  dropped?: string[];
  layout?: { product_id: string; x: number; y: number; w: number; z: number }[];
};
export type ChatMessage = {
  id: number;
  role: "assistant" | "user";
  content: string;
  payload: {
    outfit?: Outfit | null;
    products?: Product[];
    source?: string;
    actions?: string[];
    pending_preferences?: { summary: string } | null;
  };
  created_at: string;
};
export type Mannequin = {
  body_type: string;
  skin_tone: string;
  chosen: boolean;
  body_types?: string[];
  skin_tones?: string[];
};
export type Shop = {
  gender: string;
  category: string | null;
  subcategory: string | null;
  count: number;
  products: Product[];
  categories: { key: string; label: string; count: number }[];
  subcategories: { key: string; label: string; count: number }[];
};
export type StyleResult = {
  options: Outfit[];
  message?: string;
  complete_the_look: { product: Product; pairs_with_past: string | null }[];
};
export type Order = {
  id: number;
  total_inr: number;
  status: string;
  city: string;
  delivery_days: number;
  created_at: string;
  items: { product_id: string; size: string; qty: number; price_inr: number; product: Product }[];
};
export type Notification = {
  id: number;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  product: Product | null;
};
/** A piece available on a style board: a folder hanger's store product, or a rail piece. */
export type TrayPiece = { key: string; product: Product; owned: boolean; note: string };

export const mannequinUrl = (body: string, tone: string) => `${MEDIA_BASE}/api/mannequins/${body}-${tone}.png`;

export const getMe = () => api.get<Me>("/me");
export const getVocab = () => api.get<Vocab>("/vocab");
export const getRail = () => api.get<Rail>("/rail");
export const getFolders = () => api.get<FolderSummary[]>("/folders");
export const getFolder = (id: number) => api.get<FolderDetail>(`/folders/${id}`);
export const getShop = (gender = "women") => api.get<Shop>(`/shop?gender=${gender}`);
export const getProduct = (id: string) => api.get<ProductDetail>(`/products/${id}`);
export const getCart = () => api.get<Cart>("/cart");
export const getOrders = () => api.get<Order[]>("/orders");
export const getNotifications = () => api.get<Notification[]>("/notifications");
export const getWishlist = () => api.get<string[]>("/wishlist");
export const getMannequin = () => api.get<Mannequin>("/mannequin");

export const getChat = (folderId: number | null) =>
  api.get<ChatMessage[]>(`/chat${folderId ? `?folder_id=${folderId}` : ""}`);
export const sendChat = (message: string, folderId: number | null) =>
  api.post<ChatMessage>("/chat", { message, folder_id: folderId });
export const confirmChat = (id: number, accept: boolean) => api.post<ChatMessage>(`/chat/${id}/confirm`, { accept });

/** Dress the mannequin. product_ids in layer order, inside first. cachedOnly: only return a render that exists. */
export const tryOn = (product_ids: string[], cachedOnly = false) =>
  api.post<{ image_url: string | null; cached: boolean }>("/tryon", { product_ids, cached_only: cachedOnly });

/** Board pieces for a folder (its hangers' store products) or the rail. */
export async function getTray(folderId: number | null, ownedIds: Set<string>): Promise<TrayPiece[]> {
  if (folderId) {
    const r = await api.get<{ items: { hanger_id: number; piece: { name: string }; product: Product | null; source: string }[] }>(
      `/folders/${folderId}/tray`,
    );
    return r.items
      .filter((t) => t.product)
      .map((t) => ({ key: `h${t.hanger_id}`, product: t.product!, owned: ownedIds.has(t.product!.id), note: "" }));
  }
  const r = await api.get<{ items: { key: string; product: Product; owned: boolean; sources: string[] }[] }>("/rail/tray");
  return r.items.map((t) => ({ key: t.key, product: t.product, owned: t.owned, note: t.sources[0] ?? "" }));
}

const boardBase = (folderId: number | null) => (folderId ? `/folders/${folderId}` : "/rail");
export const getLooks = (folderId: number | null) => api.get<Look[]>(`${boardBase(folderId)}/looks`);
export const saveLookApi = (folderId: number | null, name: string, productIds: string[], reason = "") =>
  api.post<Look>(`${boardBase(folderId)}/looks`, {
    name,
    reason,
    placements: productIds.map((product_id, i) => ({ product_id, z: (i + 1) * 10 })),
  });
export const deleteLookApi = (id: number, folderId: number | null) =>
  api.del(folderId ? `/looks/${id}` : `/rail/looks/${id}`);
export const styleBoard = (folderId: number | null, body: { occasion?: string; formality?: string }) =>
  api.post<StyleResult>(`${boardBase(folderId)}/style`, body);

/** Add a whole look to the cart; the server picks the shopper's size, or says which pieces need one. */
export const lookToCart = (folderId: number | null, productIds: string[]) =>
  api.post<{ added: unknown[]; needs_size: { product: Product; reason: string }[]; failed: unknown[] }>(
    folderId ? `/cart/look/${folderId}` : "/rail/cart",
    { items: productIds.map((product_id) => ({ product_id })) },
  );

// inspo: upload a screenshot, tap pieces, hang store matches
export const uploadInspo = (file: File, folderId: number | null) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post<Inspo>(folderId ? `/folders/${folderId}/inspo` : "/inspo", fd);
};
export const getInspo = (id: number) => api.get<Inspo>(`/inspo/${id}`);
export const getUnfiledInspo = () => api.get<Inspo[]>("/inspo");
export const getPieceMatches = (inspoId: number, pieceId: number) =>
  api.get<PieceMatches>(`/inspo/${inspoId}/pieces/${pieceId}/matches`);
export const hangPiece = (inspoId: number, pieceId: number, product_id: string, folder_id: number | null) =>
  api.post<{ id: number; chosen_product_id: string | null }>(`/inspo/${inspoId}/pieces/${pieceId}/hang`, {
    product_id,
    folder_id,
  });
export const unhangPiece = (inspoId: number, pieceId: number) => api.del(`/inspo/${inspoId}/pieces/${pieceId}/hang`);
