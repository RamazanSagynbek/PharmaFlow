import type { Metrics, SimEvent, Snapshot } from "../types";
import type { Alarm } from "../useWarehouse";

const EVENT_TONE: Record<string, string> = {
  packed: "ok", scanned: "info", no_read: "warn", rejected: "alarm", inducted: "info",
};

function Gauge({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const tone = pct >= 90 ? "alarm" : pct >= 75 ? "warn" : "ok";
  return (
    <div className="gauge">
      <div className="gauge-head"><span>{label}</span><b>{pct}%</b></div>
      <div className="gauge-track"><div className={`gauge-fill tone-${tone}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

export function SidePanel({ snapshot, metrics, alarms, log, onResolve, onSelect }: {
  snapshot: Snapshot; metrics: Metrics | null; alarms: Alarm[];
  log: (SimEvent & { at: Date })[]; onResolve: (barcode: string) => void; onSelect: (barcode: string) => void;
}) {
  const s = snapshot.stats;
  const orders = metrics?.orders ?? {};
  const inSystem = snapshot.totes.length;

  return (
    <aside className="side">
      <section className="card">
        <h2>Показатели</h2>
        <div className="kpis">
          <div className="kpi kpi-main"><b>{snapshot.throughput_per_hour.toFixed(0)}</b><span>лотков / час</span></div>
          <div className="kpi"><b>{inSystem}</b><span>на конвейере</span></div>
          <div className="kpi"><b>{s.packed}</b><span>упаковано</span></div>
          <div className="kpi"><b>{s.units_auto + s.units_manual}</b><span>упаковок отобрано</span></div>
          <div className={`kpi ${s.rejected ? "kpi-alarm" : ""}`}><b>{s.rejected}</b><span>в брак</span></div>
        </div>
        <Gauge label="Загрузка A-frame" value={snapshot.utilization.auto} />
        <Gauge label="Загрузка сборщиков" value={snapshot.utilization.manual} />
        <div className="orders-line">
          Заказы: <b>{orders.shipped ?? 0}</b> отгружено · <b>{(orders.in_progress ?? 0) + (orders.allocated ?? 0)}</b> в работе
          {orders.exception ? <> · <b className="t-alarm">{orders.exception}</b> с ошибкой</> : null}
        </div>
      </section>

      <section className="card">
        <h2>Аварии и предупреждения {alarms.length > 0 && <span className="badge">{alarms.length}</span>}</h2>
        {alarms.length === 0 ? (
          <p className="empty">Нет активных аварий</p>
        ) : (
          <ul className="alarms">
            {alarms.map((a) => (
              <li key={a.id} className={`alarm alarm-${a.level}`}>
                <span>{a.text}</span>
                {a.barcode && a.level === "red" && (
                  <button onClick={() => onResolve(a.barcode!)}>Разобрать вручную</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card card-log">
        <h2>Журнал событий</h2>
        <ul className="log">
          {log.map((e, i) => (
            <li key={`${e.barcode}-${e.type}-${e.t}-${i}`} className={`tone-${EVENT_TONE[e.type] ?? "muted"}`}
              onClick={() => onSelect(e.barcode)}>
              <time>{e.at.toLocaleTimeString("ru-RU")}</time>
              <code>{e.barcode.slice(-5)}</code>
              <span>{e.message}</span>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
