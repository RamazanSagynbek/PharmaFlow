/** SVG drawings of warehouse equipment. Gray when idle; color only signals state (ISA-101 style). */
import type { Pt } from "./layout";

const pts = (points: Pt[]) => points.map((p) => `${p.x},${p.y}`).join(" ");

export function Belt({ points, running, speed, width = 30 }: {
  points: Pt[]; running: boolean; speed: number; width?: number;
}) {
  const duration = `${(1.1 / Math.sqrt(Math.max(speed, 0.5))).toFixed(2)}s`;
  return (
    <g>
      <polyline points={pts(points)} fill="none" stroke="#1f2730" strokeWidth={width + 8}
        strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={pts(points)} fill="none" stroke="#2e3844" strokeWidth={width}
        strokeLinejoin="round" />
      <polyline points={pts(points)} fill="none" stroke="#44515f" strokeWidth={width - 4}
        strokeDasharray="3 13" strokeLinejoin="round" className="belt-dash"
        style={{ animationDuration: duration, animationPlayState: running ? "running" : "paused" }} />
    </g>
  );
}

export function ZonePanel({ x, y, w, h, num, title, subtitle, lamp }: {
  x: number; y: number; w: number; h: number; num?: string; title: string; subtitle?: string;
  lamp: "ok" | "warn" | "alarm" | "off";
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} className="zone-panel" />
      {num && (
        <g transform={`translate(${x + 14}, ${y + 14})`}>
          <rect width={24} height={24} rx={6} className="zone-num" />
          <text x={12} y={17} textAnchor="middle" className="zone-num-text">{num}</text>
        </g>
      )}
      <text x={x + (num ? 46 : 14)} y={y + 26} className="zone-title">{title}</text>
      {subtitle && <text x={x + (num ? 46 : 14)} y={y + 42} className="zone-sub">{subtitle}</text>}
      <circle cx={x + w - 18} cy={y + 20} r={7} className={`lamp lamp-${lamp}`} />
    </g>
  );
}

/** Zone 1: magazine of empty totes and the barcode label printer. */
export function Induction({ queue }: { queue: number }) {
  return (
    <g>
      {[0, 1, 2, 3, 4].map((i) => (
        <rect key={i} x={62} y={206 + i * 13} width={58} height={11} rx={2}
          fill="#24426e" stroke="#3b6fb6" strokeWidth={1} />
      ))}
      <rect x={56} y={196} width={70} height={84} rx={4} fill="none" stroke="#566476" strokeWidth={2} />
      <text x={91} y={296} textAnchor="middle" className="eq-label">МАГАЗИН ЛОТКОВ</text>

      <rect x={160} y={214} width={62} height={48} rx={5} className="equipment" />
      <rect x={170} y={224} width={42} height={8} rx={2} fill="#0e1217" />
      <rect x={176} y={258} width={30} height={30} fill="#e5e7eb" />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <rect key={i} x={179 + i * 2.8} y={263} width={i % 3 === 0 ? 1.8 : 1} height={14} fill="#111" />
      ))}
      <text x={191} y={207} textAnchor="middle" className="eq-label">ПРИНТЕР ЭТИКЕТОК</text>

      <text x={150} y={392} textAnchor="middle" className="eq-value">
        {queue > 0 ? `В очереди: ${queue}` : "Очередь пуста"}
      </text>
    </g>
  );
}

const CHANNEL_COLORS = ["#c2410c", "#0369a1", "#15803d", "#a16207", "#7e22ce", "#be123c",
  "#0f766e", "#4d7c0f", "#b45309", "#1d4ed8", "#9d174d", "#047857", "#6d28d9", "#0e7490"];

/** Zone 2: A-frame automatic dispenser with drug channels over the belt. */
export function AFrame({ busy, running }: { busy: boolean; running: boolean }) {
  const left = 352, right = 508, top = 186, bottom = 302;
  return (
    <g>
      <polygon points={`${left},${bottom} ${right},${bottom} ${right - 26},${top} ${left + 26},${top}`}
        className={busy ? "equipment equipment-active" : "equipment"} />
      {CHANNEL_COLORS.map((c, i) => {
        const x = left + 30 + i * 7.6;
        return <rect key={i} x={x} y={top + 10} width={5} height={bottom - top - 22} rx={1}
          fill={c} opacity={0.85} />;
      })}
      <rect x={left + 22} y={top - 12} width={right - left - 44} height={14} rx={3} fill="#3a4655" />
      <text x={(left + right) / 2} y={top - 20} textAnchor="middle" className="eq-label">
        A-FRAME · 14 каналов
      </text>
      {busy && running && [0, 1, 2, 3].map((i) => (
        <circle key={i} cx={414 + i * 11} cy={304} r={3.2} className="pill-drop"
          fill={CHANNEL_COLORS[i * 3]} style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </g>
  );
}

/** Zone 3: shelving rack with medicine boxes. */
export function Rack({ x, y, cols = 7, rows = 3, label }: {
  x: number; y: number; cols?: number; rows?: number; label: string;
}) {
  const cw = 20, rh = 15;
  return (
    <g>
      <rect x={x} y={y} width={cols * cw + 8} height={rows * rh + 8} rx={3} fill="#1b232d"
        stroke="#4a5767" strokeWidth={1.5} />
      {Array.from({ length: rows * cols }, (_, i) => {
        const r = Math.floor(i / cols), c = i % cols;
        const tone = ["#5b6b7d", "#6b7c8f", "#4f5e6f", "#7a8a9c"][(r * 3 + c * 7) % 4];
        return <rect key={i} x={x + 5 + c * cw} y={y + 5 + r * rh} width={cw - 4} height={rh - 4}
          rx={1.5} fill={tone} />;
      })}
      <text x={x + (cols * cw + 8) / 2} y={y - 6} textAnchor="middle" className="eq-label">{label}</text>
    </g>
  );
}

export function Fridge({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <rect x={x} y={y} width={58} height={62} rx={4} fill="#123047" stroke="#38bdf8" strokeWidth={1.5} />
      <line x1={x + 29} y1={y + 4} x2={x + 29} y2={y + 58} stroke="#38bdf8" strokeOpacity={0.4} />
      <text x={x + 29} y={y + 38} textAnchor="middle" fontSize={22} fill="#7dd3fc">❄</text>
      <text x={x + 29} y={y + 76} textAnchor="middle" className="eq-label">+2…+8 °C</text>
    </g>
  );
}

/** Picker at a workstation bay next to the belt. */
export function Worker({ bay, busy, label }: { bay: Pt; busy: boolean; label: string }) {
  const above = bay.y < 330;
  const wy = above ? bay.y - 44 : bay.y + 44;
  return (
    <g>
      <rect x={bay.x - 30} y={bay.y - 22} width={60} height={44} rx={5} fill="none"
        stroke={busy ? "#38bdf8" : "#4a5767"} strokeWidth={1.5} strokeDasharray="5 4" />
      <line x1={bay.x} y1={above ? bay.y + 22 : bay.y - 22} x2={bay.x} y2={330 + (above ? -18 : 18)}
        stroke="#3a4655" strokeWidth={6} />
      {/* outer <g> positions, inner <g> animates: a CSS transform would override the SVG one */}
      <g transform={`translate(${bay.x + 44}, ${wy})`}>
        <g className={busy ? "worker worker-busy" : "worker"}>
          <circle cx={0} cy={-12} r={8} />
          <path d="M -12 14 Q -12 -2 0 -2 Q 12 -2 12 14 Z" />
        </g>
      </g>
      <text x={bay.x + 44} y={above ? wy - 26 : wy + 30} textAnchor="middle" className="eq-label">{label}</text>
    </g>
  );
}

/** Zone 4: barcode scanner gantry with a laser line. */
export function Scanner({ x, y, flash }: { x: number; y: number; flash: boolean }) {
  return (
    <g>
      <rect x={x - 16} y={y - 40} width={32} height={80} rx={5} fill="none" stroke="#7a8a9c" strokeWidth={4} />
      <rect x={x - 22} y={y - 50} width={44} height={14} rx={3} className="equipment" />
      <line x1={x} y1={y - 36} x2={x} y2={y + 36} stroke="#ef4444" strokeWidth={flash ? 3 : 1.5}
        opacity={flash ? 1 : 0.35} className={flash ? "laser-flash" : undefined} />
      <text x={x} y={y - 58} textAnchor="middle" className="eq-label">СКАНЕР ШТРИХКОДА</text>
    </g>
  );
}

export function Dock({ dock, laneY, busy, packed, pharmacies, x }: {
  dock: number; laneY: number; busy: boolean; packed: number; pharmacies: string[]; x: number;
}) {
  return (
    <g>
      {/* packing table */}
      <rect x={x - 28} y={laneY - 26} width={56} height={52} rx={4} fill="none"
        stroke={busy ? "#22c55e" : "#4a5767"} strokeWidth={busy ? 2.5 : 1.5} />
      {/* carton */}
      <g transform={`translate(${x + 46}, ${laneY - 16})`}>
        <g className={busy ? "carton carton-busy" : "carton"}>
          <rect width={34} height={30} rx={2} />
          <path d="M 0 0 L 17 9 L 34 0" fill="none" strokeWidth={1.5} />
          <line x1={17} y1={9} x2={17} y2={30} strokeWidth={1} />
        </g>
      </g>
      {/* dock door + truck */}
      <rect x={x + 96} y={laneY - 34} width={72} height={68} rx={4} fill="#1b232d" stroke="#4a5767" />
      {[0, 1, 2, 3, 4].map((i) => (
        <line key={i} x1={x + 100} y1={laneY - 24 + i * 12} x2={x + 164} y2={laneY - 24 + i * 12}
          stroke="#2e3844" strokeWidth={4} />
      ))}
      <text x={x + 132} y={laneY + 5} textAnchor="middle" className="dock-num">Д{dock}</text>
      <text x={x - 28} y={laneY - 34} className="eq-label">{pharmacies.join(" · ")}</text>
      <text x={x + 63} y={laneY + 34} textAnchor="middle" className="eq-value">{packed} кор.</text>
    </g>
  );
}

export function RejectBin({ x, y, count }: { x: number; y: number; count: number }) {
  return (
    <g>
      <defs>
        <pattern id="hazard" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="12" height="12" fill="#1b232d" />
          <rect width="6" height="12" fill={count ? "#7f1d1d" : "#3a2a2a"} />
        </pattern>
      </defs>
      <rect x={x - 46} y={y - 22} width={92} height={44} rx={4} fill="url(#hazard)"
        stroke={count ? "#ef4444" : "#5b4545"} strokeWidth={2} />
      <text x={x} y={y + 5} textAnchor="middle" className="reject-label">БРАК {count || ""}</text>
    </g>
  );
}
