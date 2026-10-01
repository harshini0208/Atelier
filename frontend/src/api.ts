const USER_KEY = "wiw.user";
const ADMIN_KEY = "wiw.admin";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: works for this tab only */
  }
}

let memoryUser: string | null = null;

/** The shopper's profile id, created during onboarding. null = a fresh visitor. */
export function currentUserId(): string | null {
  return read(USER_KEY) ?? memoryUser;
}

export function setCurrentUserId(id: string | null) {
  memoryUser = id;
  write(USER_KEY, id);
}

export const adminToken = () => read(ADMIN_KEY);
export const setAdminToken = (t: string | null) => write(ADMIN_KEY, t);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const uid = currentUserId();
  if (uid) headers["X-User-Id"] = uid;
  const admin = adminToken();
  if (admin && (path.startsWith("/retailer") || path.startsWith("/demo"))) headers["X-Admin-Token"] = admin;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "We couldn't reach the wardrobe server. Check your connection and try again.");
  }
  if (!res.ok) {
    let msg = `Something went wrong (${res.status}).`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (j.detail && typeof j.detail.message === "string") msg = j.detail.message;
      else if (Array.isArray(j.detail)) msg = "Some of those details don't look right. Please check and try again.";
    } catch {
      /* not json */
    }
    if (res.status === 401 && uid) {
      // the saved profile no longer exists (e.g. the store data was reset): start onboarding again
      setCurrentUserId(null);
      window.location.assign("/welcome");
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T>(p: string) => request<T>("DELETE", p),
};

export const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export const pretty = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
