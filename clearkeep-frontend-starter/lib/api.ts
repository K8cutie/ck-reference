// lib/api.ts
// Minimal fetch wrapper for ClearKeep that:
// - Uses NEXT_PUBLIC_API_BASE or defaults to http://127.0.0.1:8000
// - Sends X-API-Key automatically if you've saved one via setApiKey()
// - Keeps existing apiGet/apiPost/apiPatch/apiDelete signatures.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

// ---- optional API key storage (browser) ------------------------------------
function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("ck_api_key");
}

export function setApiKey(value: string | null) {
  if (typeof window === "undefined") return;
  if (!value) window.localStorage.removeItem("ck_api_key");
  else window.localStorage.setItem("ck_api_key", value);
}

// Build headers while preserving any passed-in headers
function withHeaders(hasJsonBody: boolean, init?: RequestInit): RequestInit {
  const key = getApiKey();
  const base: Record<string, string> = {};
  if (key) base["X-API-Key"] = key;
  if (hasJsonBody) base["Content-Type"] = "application/json";
  return {
    ...init,
    headers: { ...base, ...(init?.headers || {}) },
  };
}

async function toJson<T>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    // Try to extract useful error from JSON `detail` if present
    if (ct.startsWith("application/json")) {
      const j = await res.json().catch(() => null);
      const msg =
        j && typeof j === "object" && "detail" in j
          ? (j as any).detail
          : JSON.stringify(j ?? {});
      throw new Error(typeof msg === "string" ? msg : "HTTP " + res.status);
    }
    throw new Error("HTTP " + res.status);
  }
  if (ct.startsWith("application/json")) return (await res.json()) as T;
  // Fallback: text
  return (await res.text()) as unknown as T;
}

// ---------------------- public API (signatures unchanged) -------------------
export async function apiGet<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...withHeaders(false, init),
  });
  return toJson<T>(res);
}

export async function apiPost<T>(path: string, body: unknown, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: JSON.stringify(body),
    ...withHeaders(true, init),
  });
  return toJson<T>(res);
}

export async function apiPatch<T>(path: string, body: unknown, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    ...withHeaders(true, init),
  });
  return toJson<T>(res);
}

export async function apiDelete<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    ...withHeaders(false, init),
  });
  return toJson<T>(res);
}
