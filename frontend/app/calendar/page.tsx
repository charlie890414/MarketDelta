import { getEvents } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function Calendar() {
  try {
    const events = await getEvents();
    return <main className="main"><div className="eyebrow">Upcoming catalysts / next 30 days</div><h1>The next<br /><span style={{ color: "#d9ff62" }}>known dates.</span></h1><p className="lede">Earnings, filings and company events belong next to the changes they may explain.</p>{events.length ? <section className="feed">{events.map(event => <div className="change" key={event.id}><i className="rail" /><div className="ticker">{event.event_date ?? "TBD"}</div><div className="metric">{event.title}<span>{event.symbol ?? "MARKET"} · {event.event_type}</span></div><div className="delta">{event.status.toUpperCase()}</div><div className="score">CATALYST</div></div>)}</section> : <div className="empty">No upcoming events loaded. The calendar will fill as event collectors are enabled.</div>}</main>;
  } catch { return <main className="main"><div className="eyebrow">Upcoming catalysts</div><h1>The next<br /><span style={{ color: "#d9ff62" }}>known dates.</span></h1><div className="empty">Event data is unavailable.</div></main>; }
}
