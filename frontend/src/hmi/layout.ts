import type { SimTote } from "../types";

/** Mnemonic diagram geometry (SVG viewBox 0 0 1600 700). */
export interface Pt { x: number; y: number }

export const VIEW = { w: 1600, h: 700 };
export const BELT_Y = 330;
export const TOTE = { w: 38, h: 26, gap: 44 };

export const P = {
  beltStart: { x: 40, y: BELT_Y },
  induct: { x: 236, y: BELT_Y },
  aframe: { x: 430, y: BELT_Y },
  manualEntry: { x: 640, y: BELT_Y },
  manualExit: { x: 900, y: BELT_Y },
  scanner: { x: 1010, y: BELT_Y },
  spineX: 1100,
  packX: 1420,
  rejectBin: { x: 1010, y: 640 },
};

export const LANE_Y: Record<number, number> = { 1: 110, 2: 220, 3: 440, 4: 550 };

/** Picker workstations: bays above and below the belt. */
export const SLOTS: Pt[] = [
  { x: 720, y: 236 },
  { x: 830, y: 424 },
];

/** Recirculation loop after a no-read at the scanner. */
export const LOOP: Pt[] = [
  P.scanner,
  { x: 1060, y: BELT_Y },
  { x: 1060, y: 610 },
  { x: 950, y: 610 },
  { x: 950, y: BELT_Y },
  P.scanner,
];

export const dockPath = (dock: number): Pt[] => [
  P.scanner,
  { x: P.spineX, y: BELT_Y },
  { x: P.spineX, y: LANE_Y[dock] ?? BELT_Y },
  { x: P.packX, y: LANE_Y[dock] ?? BELT_Y },
];

/** Point at fraction t (0..1) along a polyline. */
export function along(points: Pt[], t: number): Pt {
  const segs = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
  const total = segs.reduce((a, b) => a + b, 0);
  let d = Math.min(Math.max(t, 0), 1) * total;
  for (let i = 0; i < segs.length; i++) {
    if (d <= segs[i] || i === segs.length - 1) {
      const k = segs[i] === 0 ? 0 : d / segs[i];
      return {
        x: points[i].x + (points[i + 1].x - points[i].x) * k,
        y: points[i].y + (points[i + 1].y - points[i].y) * k,
      };
    }
    d -= segs[i];
  }
  return points[points.length - 1];
}

const MAX_VISIBLE_QUEUE = 4;

/** Where a tote is drawn, or null if it is hidden deep in a queue. */
export function totePosition(t: SimTote): Pt | null {
  const q = t.queue_pos ?? 0;
  const p = t.progress;
  switch (t.stage) {
    case "queued":
      return q < MAX_VISIBLE_QUEUE ? { x: P.induct.x - 22 - TOTE.gap * q, y: BELT_Y } : null;
    case "to_auto":
      return along([P.induct, P.aframe], p);
    case "auto_wait":
      return { x: Math.max(P.aframe.x - TOTE.gap * (q + 1), P.induct.x + 10), y: BELT_Y };
    case "auto_pick":
      return P.aframe;
    case "to_manual":
      return along([P.aframe, P.manualEntry], p);
    case "manual_wait":
      return { x: Math.max(P.manualEntry.x - TOTE.gap * q, P.aframe.x + 50), y: BELT_Y };
    case "manual_pick":
      return SLOTS[t.slot ?? 0] ?? SLOTS[0];
    case "to_sorter":
      return along([P.manualExit, P.scanner], p);
    case "recirculating":
      return along(LOOP, p);
    case "to_dock":
      return along(dockPath(t.dock), p);
    case "dock_wait":
      return { x: P.packX - TOTE.gap * (q + 1), y: LANE_Y[t.dock] ?? BELT_Y };
    case "packing":
      return { x: P.packX, y: LANE_Y[t.dock] ?? BELT_Y };
    default:
      return null;
  }
}

/** How full the tote looks (0..1): A-frame fills it first, then the picker tops it up. */
export function toteFill(t: SimTote): number {
  const total = t.auto_units + t.manual_units;
  if (!total) return 0;
  const a = t.auto_units / total;
  const m = t.manual_units / total;
  switch (t.stage) {
    case "queued": case "to_auto": case "auto_wait":
      return 0;
    case "auto_pick":
      return a * t.progress;
    case "to_manual": case "manual_wait":
      return a;
    case "manual_pick":
      return a + m * t.progress;
    default:
      return 1;
  }
}
