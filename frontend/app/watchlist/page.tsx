import { getWatchlistItems, getWatchlists } from "../../lib/api";
import WatchlistManager from "./WatchlistManager";

export const dynamic = "force-dynamic";

export default async function Watchlist() {
  try {
    const lists = await getWatchlists();
    const sections = await Promise.all(lists.map(async list => {
      try {
        return { list, items: await getWatchlistItems(list.id) };
      } catch {
        return { list, items: [] };
      }
    }));
    return <main className="main"><div className="eyebrow">Tracked universe</div><h1>Your<br /><span style={{ color: "#d9ff62" }}>watchlists.</span></h1><p className="lede">Keep the engine focused on the names where a change is actionable.</p><section className="feed">{sections.map(({ list, items }) => <div className="change" key={list.id}><i className="rail" /><div className="ticker">{list.name}</div><div className="metric">{items.length} instruments<span>{items.map(item => item.symbol).join(" · ") || "No instruments yet"}</span></div><div className="delta">{items.length ? "ACTIVE" : "EMPTY"}</div><div className="score">{items.length}</div></div>)}</section><WatchlistManager /></main>;
  } catch { return <main className="main"><div className="eyebrow">Tracked universe</div><h1>Your<br /><span style={{ color: "#d9ff62" }}>watchlists.</span></h1><div className="empty">Watchlist data is unavailable.</div></main>; }
}
