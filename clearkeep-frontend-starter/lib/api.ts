const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  return json<T>(res);
}

export async function apiPost<T>(path: string, body: unknown, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    body: JSON.stringify(body),
    ...init,
  });
  return json<T>(res);
}

export async function apiPatch<T>(path: string, body: unknown, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    body: JSON.stringify(body),
    ...init,
  });
  return json<T>(res);
}

export async function apiDelete<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", ...init });
  return json<T>(res);
}
