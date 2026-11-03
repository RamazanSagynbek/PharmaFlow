import type { Pharmacy, SimTote, Snapshot } from "../types";
import type { Ghost } from "../useWarehouse";
import { AFrame, Belt, Dock, Fridge, Induction, Rack, RejectBin, Scanner, Worker, ZonePanel } from "./equipment";
import { BELT_Y, LANE_Y, LOOP, P, SLOTS, TOTE, VIEW, totePosition, toteFill } from "./layout";

interface Props {
  snapshot: Snapshot;
  running: boolean;
  speed: number;
  ghosts: Ghost[];
  packedPerDock: Record<number, number>;
  rejectedCount: number;
  scanFlash: boolean;
  pharmacies: Pharmacy[];
  selected: string | null;
  onSelect: (barcode: string) => void;
}

type Lamp = "ok" | "warn" | "alarm" | "off";

export function Mnemonic(props: Props) {
  const { snapshot, running, speed, ghosts, packedPerDock, rejectedCount, scanFlash, pharmacies } = props;
  const { equipment, queues } = snapshot;
  const lamp = (warn: boolean, alarm = false): Lamp =>
    !running ? "off" : alarm ? "alarm" : warn ? "warn" : "ok";

  const docks = [1, 2, 3, 4];
  const busyDocks = new Set(snapshot.totes.filter((t) => t.stage === "to_dock").map((t) => t.dock));
  const busySlots = new Set(equipment.manual);
  const pharmaciesByDock = (d: number) => pharmacies.filter((p) => p.dock === d).map((p) => p.code);

  return (
    <svg viewBox={`20 30 ${VIEW.w - 30} ${VIEW.h - 30}`} className="mnemonic" preserveAspectRatio="xMidYMid meet">
      {/* ---------------- zones ---------------- */}
      <ZonePanel x={28} y={70} w={262} h={350} num="1" title="СТАРТ" subtitle="лоток + штрихкод"
        lamp={lamp(queues.start > 6)} />
      <ZonePanel x={302} y={70} w={262} h={350} num="2" title="АВТОМАТ" subtitle="A-frame дозатор"
        lamp={lamp(queues.auto >= 5)} />
      <ZonePanel x={576} y={70} w={356} h={470} num="3" title="РУЧНОЙ ОТБОР" subtitle="сборщики, холодовая цепь"
        lamp={lamp(queues.manual >= 5)} />
      <ZonePanel x={944} y={70} w={182} h={620} num="4" title="СОРТЕР" subtitle="сканер и стрелки"
        lamp={lamp(false, rejectedCount > 0)} />
      <ZonePanel x={1138} y={40} w={444} h={570} title="ДОКИ ОТГРУЗКИ" subtitle="упаковка в коробки"
        lamp={lamp(Object.values(queues.docks).some((q) => q >= 4))} />

      {/* ---------------- static equipment ---------------- */}
      <Rack x={600} y={168} label="СТЕЛЛАЖ A" />
      <Rack x={600} y={470} cols={6} label="СТЕЛЛАЖ B" />
      <Fridge x={860} y={150} />

      {/* ---------------- belts ---------------- */}
      <Belt points={LOOP} running={running} speed={speed} width={22} />
      <Belt points={[P.beltStart, { x: P.spineX, y: BELT_Y }]} running={running} speed={speed} />
      <Belt points={[{ x: P.spineX, y: LANE_Y[1] }, { x: P.spineX, y: LANE_Y[4] }]}
        running={running} speed={speed} width={26} />
      {docks.map((d) => (
        <g key={d} opacity={busyDocks.has(d) ? 1 : 0.85}>
          <Belt points={[{ x: P.spineX, y: LANE_Y[d] }, { x: P.packX, y: LANE_Y[d] }]}
            running={running} speed={speed} width={26} />
          {busyDocks.has(d) && (
            <polygon points={`${P.spineX + 22},${LANE_Y[d] - 7} ${P.spineX + 34},${LANE_Y[d]} ${P.spineX + 22},${LANE_Y[d] + 7}`}
              fill="#22c55e" />
          )}
        </g>
      ))}
      <text x={1005} y={634} textAnchor="middle" className="eq-label-dim">повторный круг</text>

      {/* ---------------- active equipment ---------------- */}
      <Induction queue={queues.start} />
      <AFrame busy={equipment.auto !== null} running={running} />
      {SLOTS.slice(0, equipment.manual_workers).map((bay, i) => (
        <Worker key={i} bay={bay} busy={busySlots.has(i)} label={`Сборщик ${i + 1}`} />
      ))}
      <Scanner x={P.scanner.x} y={BELT_Y} flash={scanFlash} />
      <RejectBin x={P.rejectBin.x} y={P.rejectBin.y + 12} count={rejectedCount} />
      {docks.map((d) => (
        <Dock key={d} dock={d} x={P.packX} laneY={LANE_Y[d]} busy={!!equipment.docks[d]}
          packed={packedPerDock[d] ?? 0} pharmacies={pharmaciesByDock(d)} />
      ))}

      {/* ---------------- totes ---------------- */}
      {snapshot.totes.map((t) => {
        const pos = totePosition(t);
        return pos ? (
          <ToteGlyph key={t.barcode} tote={t} x={pos.x} y={pos.y} selected={props.selected === t.barcode}
            onClick={() => props.onSelect(t.barcode)} />
        ) : null;
      })}
      {queues.start > 4 && (
        <text x={P.induct.x - 22 - TOTE.gap * 3} y={BELT_Y + 34} textAnchor="middle" className="eq-value">
          +{queues.start - 4}
        </text>
      )}

      {ghosts.map((g) => {
        const x = g.kind === "packed" ? P.packX : P.rejectBin.x;
        const y = g.kind === "packed" ? LANE_Y[g.dock] : P.rejectBin.y;
        return (
          <g key={`${g.kind}-${g.barcode}`} style={{ transform: `translate(${x - TOTE.w / 2}px, ${y - TOTE.h / 2}px)` }}>
            <g className={g.kind === "packed" ? "ghost-packed" : "ghost-rejected"}>
              <ToteBody fill={1} stroke={g.kind === "rejected" ? "#ef4444" : "#22c55e"} />
            </g>
          </g>
        );
      })}
    </svg>
  );
}

function ToteBody({ fill, stroke, picking }: { fill: number; stroke?: string; picking?: boolean }) {
  const inner = Math.max(0, Math.min(1, fill)) * (TOTE.h - 8);
  return (
    <>
      <rect width={TOTE.w} height={TOTE.h} rx={4} fill="#2f6fdb" stroke={stroke ?? "#1e4fa3"}
        strokeWidth={stroke ? 2.5 : 1.5} className={picking ? "tote-picking" : undefined} />
      <rect x={4} y={4} width={TOTE.w - 14} height={TOTE.h - 8} rx={2} fill="#1b3f80" />
      {inner > 0 && (
        <rect x={4} y={4 + (TOTE.h - 8) - inner} width={TOTE.w - 14} height={inner} rx={2} fill="#e2e8f0" />
      )}
      {/* barcode label */}
      <rect x={TOTE.w - 9} y={5} width={6} height={TOTE.h - 10} fill="#f8fafc" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <rect key={i} x={TOTE.w - 8.4} y={7 + i * 2.6} width={4.8} height={i % 2 ? 0.8 : 1.4} fill="#111" />
      ))}
    </>
  );
}

function ToteGlyph({ tote, x, y, selected, onClick }: {
  tote: SimTote; x: number; y: number; selected: boolean; onClick: () => void;
}) {
  const recirc = tote.stage === "recirculating";
  const picking = tote.stage === "auto_pick" || tote.stage === "manual_pick" || tote.stage === "packing";
  const stroke = selected ? "#facc15" : recirc ? "#f59e0b" : undefined;
  return (
    <g className="tote" onClick={onClick}
      style={{ transform: `translate(${x - TOTE.w / 2}px, ${y - TOTE.h / 2}px)` }}>
      <title>{`${tote.barcode} · заказ ${tote.order_id} · док ${tote.dock}`}</title>
      <ToteBody fill={toteFill(tote)} stroke={stroke} picking={picking} />
      {tote.has_cold && <text x={-4} y={-3} fontSize={13} fill="#7dd3fc">❄</text>}
      {tote.has_rx && <text x={tote.has_cold ? 9 : -4} y={-3} className="rx-badge">Rx</text>}
      {recirc && <text x={TOTE.w / 2} y={TOTE.h + 13} textAnchor="middle" className="recirc-label">
        круг {tote.recirculations}</text>}
    </g>
  );
}
