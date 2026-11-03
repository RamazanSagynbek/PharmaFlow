import type { Metrics, Pharmacy, ToteDetail } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

export const api = {
  pharmacies: () => request<Pharmacy[]>("/api/pharmacies"),
  metrics: () => request<Metrics>("/api/metrics"),
  tote: (barcode: string) => request<ToteDetail>(`/api/totes/${barcode}`),
  start: () => post("/api/sim/start"),
  stop: () => post("/api/sim/stop"),
  speed: (speed: number) => post("/api/sim/speed", { speed }),
  demoOrders: (count: number) => post(`/api/demo/orders?count=${count}`),
  resolve: (barcode: string) => post(`/api/totes/${barcode}/resolve`),
};
