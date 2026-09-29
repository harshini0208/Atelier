const USER_KEY = "wiw.user";

export function currentUserId(): string {
  try {
    return localStorage.getItem(USER_KEY) || "aanya";
  } catch {
    return "aanya";
  }
}

export function setCurrentUserId(id: string) {
  try {
    localStorage.setItem(USER_KEY, id);
  } catch {
    /* private mode: the header still works for this tab via reload-free state */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-User-Id": currentUserId() };
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
