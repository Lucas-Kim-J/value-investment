export interface ApiResult<T> {
  ok: boolean;
  status: number;
  data: T | null;
}

async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown } = {},
): Promise<ApiResult<T>> {
  const o: RequestInit = { credentials: "same-origin", headers: {} };
  if (opts.body !== undefined) {
    o.method = opts.method || "POST";
    (o.headers as Record<string, string>)["Content-Type"] = "application/json";
    o.body = JSON.stringify(opts.body);
  } else if (opts.method) {
    o.method = opts.method;
  }
  const r = await fetch(path, o);
  let data: T | null = null;
  try {
    data = (await r.json()) as T;
  } catch {
    /* non-JSON */
  }
  return { ok: r.ok, status: r.status, data };
}

export const apiGet = <T>(p: string) => api<T>(p);
export const apiPost = <T>(p: string, body?: unknown) => api<T>(p, { body: body ?? {} });
export const apiPut = <T>(p: string, body?: unknown) => api<T>(p, { method: "PUT", body });
export const apiDelete = <T>(p: string) => api<T>(p, { method: "DELETE" });

export async function me(): Promise<string | null> {
  const r = await api<{ user: string }>("/api/me");
  return r.data?.user ?? null;
}

export default api;
