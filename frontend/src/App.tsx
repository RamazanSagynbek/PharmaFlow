import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { SidePanel } from "./components/SidePanel";
import { TopBar } from "./components/TopBar";
import { ToteModal } from "./components/ToteModal";
import { Mnemonic } from "./hmi/Mnemonic";
import type { Metrics, Pharmacy } from "./types";
import { type Alarm, useWarehouse } from "./useWarehouse";

const DEMO_TARGET_TOTES = 12;

export default function App() {
  const wh = useWarehouse();
  const [pharmacies, setPharmacies] = useState<Pharmacy[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [demo, setDemo] = useState(() => new URLSearchParams(location.search).has("demo"));

  useEffect(() => { api.pharmacies().then(setPharmacies).catch(() => undefined); }, [wh.connected]);

  useEffect(() => {
    const load = () => api.metrics().then(setMetrics).catch(() => undefined);
    load();
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, []);

  // Presentation mode: keep the warehouse busy with incoming pharmacy orders
  const totesInSystem = wh.snapshot?.totes.length ?? 0;
  useEffect(() => {
    if (!demo || !wh.connected) return;
    if (!wh.running) api.start().catch(() => undefined);
    const timer = window.setInterval(() => {
      if (totesInSystem < DEMO_TARGET_TOTES) api.demoOrders(2).catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [demo, wh.connected, wh.running, totesInSystem]);

  const alarms = useMemo<Alarm[]>(() => {
    const list = [...wh.rejected];
    const q = wh.snapshot?.queues;
    if (q && wh.running) {
      if (q.auto >= 5) list.push({ id: "q-auto", level: "yellow", time: new Date(),
        text: `Очередь перед A-frame: ${q.auto} лотков` });
      if (q.manual >= 5) list.push({ id: "q-manual", level: "yellow", time: new Date(),
        text: `Перегрузка ручной зоны: ${q.manual} лотков ждут сборщика` });
      for (const [dock, n] of Object.entries(q.docks)) {
        if (n >= 4) list.push({ id: `q-dock-${dock}`, level: "yellow", time: new Date(),
          text: `Скопление на доке Д${dock}: ${n} лотков` });
      }
    }
    return list;
  }, [wh.rejected, wh.snapshot, wh.running]);

  const resolve = useCallback((barcode: string) => {
    api.resolve(barcode).then(() => wh.dismissReject(barcode)).catch(() => undefined);
  }, [wh]);

  const fullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => undefined);
  };

  const scanFlash = performance.now() - wh.lastScan < 350;

  return (
    <div className="app">
      <TopBar
        connected={wh.connected} running={wh.running} speed={wh.speed} simTime={wh.snapshot?.t ?? 0} demo={demo}
        onStart={() => api.start()} onStop={() => api.stop()} onSpeed={(s) => api.speed(s)}
        onOrders={() => api.demoOrders(5)} onDemo={() => setDemo((d) => !d)} onFullscreen={fullscreen}
      />
      <main className="main">
        <div className="stage">
          {wh.snapshot ? (
            <Mnemonic
              snapshot={wh.snapshot} running={wh.running} speed={wh.speed} ghosts={wh.ghosts}
              packedPerDock={wh.packedPerDock} rejectedCount={wh.rejected.length} scanFlash={scanFlash}
              pharmacies={pharmacies} selected={selected} onSelect={setSelected}
            />
          ) : (
            <div className="connecting">Подключение к складу…</div>
          )}
          <div className="legend">
            <span><i className="lg-tote" /> лоток</span>
            <span><i className="lg-fill" /> заполненность</span>
            <span><i className="lg-recirc" /> повторный круг</span>
            <span>❄ холодовая цепь</span>
            <span className="rx-badge-inline">Rx</span> рецептурный
            <span className="legend-hint">Нажмите на лоток, чтобы увидеть его содержимое</span>
          </div>
        </div>
        {wh.snapshot && (
          <SidePanel snapshot={wh.snapshot} metrics={metrics} alarms={alarms} log={wh.log}
            onResolve={resolve} onSelect={setSelected} />
        )}
      </main>
      {selected && <ToteModal barcode={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
