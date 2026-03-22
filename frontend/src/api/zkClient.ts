/**
 * ZK-authenticated API client.
 * Reads token from sessionStorage (not localStorage) — clears on tab close.
 */

export class ZKApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = sessionStorage.getItem("zkToken");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ZKApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export async function zkGet<T>(path: string): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { headers: getHeaders() });
  return handleResponse<T>(res);
}

export async function zkPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers: getHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function zkDelete(path: string): Promise<void> {
  const res = await fetch(`/api/v1${path}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ZKApiError(res.status, body.detail || res.statusText);
  }
}
