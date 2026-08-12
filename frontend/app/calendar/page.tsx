import { getEvents } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function Calendar() {
  try {
    const events = await getEvents();
    return <main className="main"><div className="eyebrow">未來催化事件 / 30 天內</div><h1>下一個<br /><span>已知日期。</span></h1><p className="lede">財報、申報與公司事件，應與它們可能解釋的市場變化一併檢視。</p>{events.length ? <section className="feed">{events.map(event => <div className="change" key={event.id}><i className="rail neutral" /><div className="ticker">{event.event_date ?? "待定"}</div><div className="metric">{event.title}<span>{event.symbol ?? "市場"} · {event.event_type}</span></div><div className="delta">{event.status.toUpperCase()}</div><div className="score">催化事件</div></div>)}</section> : <div className="empty">尚未載入未來事件；啟用事件蒐集器後，行事曆將自動補上資料。</div>}</main>;
  } catch { return <main className="main"><div className="eyebrow">未來催化事件</div><h1>下一個<br /><span style={{ color: "#d9ff62" }}>已知日期。</span></h1><div className="empty">目前無法取得事件資料。</div></main>; }
}
