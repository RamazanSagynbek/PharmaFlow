const SPEEDS = [1, 2, 5, 10, 20];

function clock(seconds: number) {
  const s = Math.floor(seconds);
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function TopBar(props: {
  connected: boolean; running: boolean; speed: number; simTime: number; demo: boolean;
  onStart: () => void; onStop: () => void; onSpeed: (s: number) => void;
  onOrders: () => void; onDemo: () => void; onFullscreen: () => void;
}) {
  const status = !props.connected ? "НЕТ СВЯЗИ" : props.running ? "РАБОТА" : "СТОП";
  const statusClass = !props.connected ? "alarm" : props.running ? "ok" : "off";
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">+</span>
        <div>
          <div className="brand-name">PharmaFlow <span>HMI</span></div>
          <div className="brand-sub">Автоматизированный аптечный склад · Алматы</div>
        </div>
      </div>

      <div className={`status status-${statusClass}`}>
        <span className="status-dot" />
        {status}
      </div>

      <div className="clock" title="Время смены (симуляция)">
        <span>СМЕНА</span>{clock(props.simTime)}
      </div>

      <div className="controls">
        <button className="btn btn-start" onClick={props.onStart} disabled={!props.connected || props.running}>
          ▶ ПУСК
        </button>
        <button className="btn btn-stop" onClick={props.onStop} disabled={!props.connected || !props.running}>
          ■ СТОП
        </button>
        <div className="speed" role="group" aria-label="Скорость симуляции">
          {SPEEDS.map((s) => (
            <button key={s} className={s === props.speed ? "active" : ""} onClick={() => props.onSpeed(s)}>
              ×{s}
            </button>
          ))}
        </div>
        <button className="btn" onClick={props.onOrders} disabled={!props.connected}>+ Заказы аптек</button>
        <button className={`btn ${props.demo ? "btn-on" : ""}`} onClick={props.onDemo}
          title="Заказы поступают автоматически — режим для презентации">
          {props.demo ? "● Авто-демо" : "○ Авто-демо"}
        </button>
        <button className="btn btn-icon" onClick={props.onFullscreen} title="Полный экран (F11)">⛶</button>
      </div>
    </header>
  );
}
