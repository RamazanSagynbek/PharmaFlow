import { useEffect, useState } from "react";
import { api } from "../api";
import type { ToteDetail } from "../types";

const STATUS: Record<string, string> = {
  created: "Создан", in_process: "На конвейере", packed: "Упакован", rejected: "Брак",
};
const LOCATION: Record<string, string> = {
  start: "Старт", auto: "Автомат", manual: "Ручной отбор", sorter: "Сортер", dock: "Док", reject: "Зона брака",
};

export function ToteModal({ barcode, onClose }: { barcode: string; onClose: () => void }) {
  const [tote, setTote] = useState<ToteDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.tote(barcode).then((t) => alive && setTote(t)).catch((e) => alive && setError(String(e)));
    load();
    const timer = window.setInterval(load, 1500);
    return () => { alive = false; window.clearInterval(timer); };
  }, [barcode]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <h3>Лоток <code>{barcode}</code></h3>
            {tote && (
              <p>
                {tote.pharmacy_name} ({tote.pharmacy_code}) · заказ №{tote.order_id} · док Д{tote.dock}
              </p>
            )}
          </div>
          <button className="btn btn-icon" onClick={onClose} aria-label="Закрыть">✕</button>
        </header>
        {error && <p className="t-alarm">{error}</p>}
        {tote && (
          <>
            <div className="chips">
              <span className="chip">{STATUS[tote.status] ?? tote.status}</span>
              <span className="chip">Зона: {LOCATION[tote.location] ?? tote.location}</span>
              {tote.recirculations > 0 && <span className="chip chip-warn">Повторных кругов: {tote.recirculations}</span>}
            </div>
            <table>
              <thead>
                <tr><th>Препарат</th><th>Серия</th><th>Годен до</th><th>Кол-во</th><th>Зона</th><th></th></tr>
              </thead>
              <tbody>
                {tote.items.map((i, k) => (
                  <tr key={k}>
                    <td>
                      {i.product_name}
                      {i.is_cold && <span className="tag tag-cold">❄ холод</span>}
                      {i.is_rx && <span className="tag">Rx</span>}
                    </td>
                    <td><code>{i.batch_series}</code></td>
                    <td>{new Date(i.batch_expiry).toLocaleDateString("ru-RU")}</td>
                    <td className="num">{i.qty}</td>
                    <td>{i.zone === "auto" ? "Автомат" : "Ручная"}</td>
                    <td className={i.picked ? "t-ok" : "t-muted"}>{i.picked ? "✓ отобрано" : "ожидает"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="hint">Серии подобраны по FEFO: первой отгружается партия с ближайшим сроком годности.</p>
          </>
        )}
      </div>
    </div>
  );
}
