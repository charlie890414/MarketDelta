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
    return <main className="main"><div className="eyebrow">追蹤標的</div><h1>你的<br /><span style={{ color: "#d9ff62" }}>自選清單。</span></h1><p className="lede">聚焦於變化值得採取行動的公司。</p><section className="feed">{sections.map(({ list, items }) => <div className="change" key={list.id}><i className="rail" /><div className="ticker">{list.name}</div><div className="metric">{items.length} 個標的<span>{items.map(item => item.symbol).join(" · ") || "尚無標的"}</span></div><div className="delta">{items.length ? "使用中" : "空白"}</div><div className="score">{items.length}</div></div>)}</section><WatchlistManager /></main>;
  } catch { return <main className="main"><div className="eyebrow">追蹤標的</div><h1>你的<br /><span style={{ color: "#d9ff62" }}>自選清單。</span></h1><div className="empty">目前無法取得自選清單資料。</div></main>; }
}
