export type Stage =
  | "queued" | "to_auto" | "auto_wait" | "auto_pick"
  | "to_manual" | "manual_wait" | "manual_pick"
  | "to_sorter" | "recirculating" | "to_dock" | "dock_wait"
  | "packing" | "packed" | "rejected";

export interface SimTote {
  barcode: string;
  order_id: number;
  stage: Stage;
  zone: string;
  progress: number;
  dock: number;
  recirculations: number;
  slot: number | null;
  queue_pos: number | null;
  auto_units: number;
  manual_units: number;
  has_cold: boolean;
  has_rx: boolean;
}

export interface Snapshot {
  t: number;
  totes: SimTote[];
  equipment: {
    auto: string | null;
    manual: (number | null)[];
    manual_workers: number;
    docks: Record<string, string | null>;
  };
  queues: { start: number; auto: number; manual: number; docks: Record<string, number> };
  utilization: { auto: number; manual: number };
  stats: {
    inducted: number; packed: number; rejected: number; no_reads: number;
    units_auto: number; units_manual: number;
  };
  throughput_per_hour: number;
}

export interface SimEvent {
  t: number;
  type: string;
  barcode: string;
  zone: string;
  detail: Record<string, unknown>;
  message: string;
}

export interface StateMessage {
  type: "hello" | "tick";
  running: boolean;
  speed: number;
  snapshot: Snapshot;
  events: SimEvent[];
}

export interface Pharmacy {
  id: number;
  code: string;
  name: string;
  address: string;
  dock: number;
}

export interface Metrics {
  orders: Record<string, number>;
  totes: Record<string, number>;
}

export interface ToteItem {
  sku: string;
  product_name: string;
  is_rx: boolean;
  is_cold: boolean;
  batch_series: string;
  batch_expiry: string;
  qty: number;
  zone: "auto" | "manual";
  picked: boolean;
}

export interface ToteDetail {
  barcode: string;
  order_id: number;
  status: string;
  location: string;
  dock: number;
  recirculations: number;
  pharmacy_code: string;
  pharmacy_name: string;
  items: ToteItem[];
}
