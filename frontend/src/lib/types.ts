export type Size = { size: string; stock: number };

export type Product = {
  id: string;
  store_id: string;
  brand: string;
  name: string;
  description: string;
  category: string;
  subcategory: string;
  subcategory_label: string;
  gender_fit: string;
  primary_color: string;
  secondary_color: string | null;
  pattern: string;
  fabric: string;
  silhouette: string;
  occasion_tags: string[];
  style_tags: string[];
  price_inr: number;
  mrp_inr: number;
  image_url: string;
  slot: string;
  sizes: Size[];
  in_stock: boolean;
  delivery_days?: number;
  added_at?: string;
};

export type ProductDetail = Product & {
  delivery: string;
  price_history: { price_inr: number; at: string }[];
  suggested_size: string | null;
};

export type Reason = { code: string; label: string };

export type MatchItem = {
  product: Product;
  score: number;
  display_score: number;
  good_match: boolean;
  reasons: Reason[];
  why: string[];
};

export type Piece = {
  id: number;
  inspo_id: number;
  idx: number;
  category: string;
  subcategory: string;
  subcategory_label: string;
  name: string;
  color: string;
  secondary_color: string | null;
  pattern: string;
  fabric: string;
  silhouette: string;
  style_tags: string[];
  occasion_tags: string[];
  box: [number, number, number, number] | null;
  confidence: number;
  crop_url: string | null;
  selected: boolean | null;
  manual: boolean;
  slot: string;
};

export type Inspo = {
  id: number;
  folder_id: number | null;
  image_url: string;
  width: number;
  height: number;
  status: "analyzed" | "no_apparel" | "no_outfit" | "blurry" | "low_quality" | "failed";
  message: string;
  source: string;
  created_at: string;
  pieces: Piece[];
};

export type Coverage = {
  covered: number;
  covered_in_prefs: number;
  total: number;
  line: string;
  pieces: { hanger_id: number; name: string; subcategory: string; covered: boolean; covered_in_prefs: boolean }[];
};

export type Hanger = {
  id: number;
  folder_id: number;
  piece: Piece;
  chosen_product_id: string | null;
  chosen_size: string | null;
  chosen_product?: Product;
  top_match?: MatchItem | null;
  covered?: boolean;
  covered_in_prefs?: boolean;
  created_at: string;
  from_rail?: boolean;
};

export type FolderSummary = {
  id: number;
  name: string;
  description: string;
  hanger_count: number;
  inspo_count: number;
  cover_images: string[];
  inspo_images: string[];
};

export type FolderDetail = FolderSummary & {
  inspo: Inspo[];
  hangers: Hanger[];
  looks: { inspo_id: number; image_url: string | null; coverage: Coverage }[];
};

/** Store matches for one inspo piece (shown the moment it's tapped). */
export type PieceMatches = {
  for_you: MatchItem[];
  also_view: MatchItem[];
  closest: MatchItem[];
  covered: boolean;
  covered_in_prefs: boolean;
  piece: { id: number; name: string; crop_url: string | null; subcategory: string; subcategory_label: string; color: string; fabric: string };
  hanger: { id: number; chosen_product_id: string | null } | null;
  gap_message?: string;
};

export type Preferences = {
  budgets: Record<string, [number, number]>;
  sizes: Record<string, string>;
  fit: string;
  preferred_materials: string[];
  avoid_materials: string[];
  avoid_colors: string[];
  occasions: string[];
  gender_fit: string;
  city: string;
};

export type Me = {
  id: string;
  name: string;
  city: string;
  tagline: string;
  is_guest: boolean;
  preferences: Preferences | null;
  unread_notifications: number;
  cart_count: number;
};

export type Vocab = {
  categories: { key: string; label: string; subcategories: { key: string; label: string }[] }[];
  colors: { key: string; label: string; hex: string; family: string }[];
  fabrics: string[];
  occasions: string[];
  style_tags: string[];
  cities: string[];
  sizes: Record<string, Record<string, string[]>>;
};

export type RailSource = { kind: "online" | "in_store" | "cart" | "wishlist"; label: string; detail: string; size: string | null; at: string };
export type RailItem = { product: Product; sources: RailSource[]; owned: boolean; folder_ids: number[] };
export type Rail = { items: RailItem[]; counts: Record<string, number>; member_linked: boolean };

/** A saved look on a style board (folder or rail), in layer order via z. */
export type Look = {
  id: number;
  name: string;
  reason: string;
  created_at: string;
  total_inr: number;
  items: { product: Product; x: number; y: number; w: number; z: number }[];
};
