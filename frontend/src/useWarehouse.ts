import { useEffect, useRef, useState } from "react";
import type { SimEvent, Snapshot, StateMessage } from "./types";

export interface Ghost {
  barcode: string;
  kind: "packed" | "rejected";
  dock: number;
  born: number; // performance.now()
}

export interface Alarm {
  id: string;
  level: "red" | "yellow";
  text: string;
  barcode?: string;
  time: Date;
}

export interface WarehouseState {
  connected: boolean;
  running: boolean;
  speed: number;
  snapshot: Snapshot | null;
  log: (SimEvent & { at: Date })[];
  ghosts: Ghost[];
  packedPerDock: Record<number, number>;
  rejected: Alarm[];
  lastScan: number; // performance.now() of the last scanner read
}

const GHOST_MS = 2200;
const LOG_SIZE = 60;

/** Live connection to the warehouse over WebSocket, with automatic reconnect. */
export function useWarehouse(): WarehouseState & { dismissReject: (barcode: string) => void } {
  const [state, setState] = useState<WarehouseState>({
    connected: false, running: false, speed: 5, snapshot: null, log: [], ghosts: [],
    packedPerDock: {}, rejected: [], lastScan: 0,
  });
  const retry = useRef<number>();

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setState((s) => ({ ...s, connected: true }));
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) retry.current = window.setTimeout(connect, 2000);
      };
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data) as StateMessage;
        const now = performance.now();
        setState((s) => {
          const packedPerDock = { ...s.packedPerDock };
          const ghosts = s.ghosts.filter((g) => now - g.born < GHOST_MS);
          const rejected = [...s.rejected];
          let lastScan = s.lastScan;
          for (const e of data.events) {
            if (e.type === "packed") {
              packedPerDock[e.detail.dock as number] = (packedPerDock[e.detail.dock as number] ?? 0) + 1;
              ghosts.push({ barcode: e.barcode, kind: "packed", dock: e.detail.dock as number, born: now });
            } else if (e.type === "rejected") {
              ghosts.push({ barcode: e.barcode, kind: "rejected", dock: 0, born: now });
              rejected.unshift({
                id: `rej-${e.barcode}`, level: "red", barcode: e.barcode, time: new Date(),
                text: `Лоток ${e.barcode}: штрихкод не считан ${e.detail.attempts} раза, зона брака`,
              });
            } else if (e.type === "scanned" || e.type === "no_read") {
              lastScan = now;
            }
          }
          const at = new Date();
          const log = [...data.events.map((e) => ({ ...e, at })).reverse(), ...s.log].slice(0, LOG_SIZE);
          return {
            connected: true, running: data.running, speed: data.speed, snapshot: data.snapshot,
            log, ghosts, packedPerDock, rejected, lastScan,
          };
        });
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry.current);
      ws?.close();
    };
  }, []);

  const dismissReject = (barcode: string) =>
    setState((s) => ({ ...s, rejected: s.rejected.filter((a) => a.barcode !== barcode) }));

  return { ...state, dismissReject };
}
