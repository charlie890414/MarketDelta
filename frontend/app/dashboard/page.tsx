import Link from "next/link";
import { getChanges, getDailyReports, getWatchlists, type Change } from "../../lib/api";
import { changeDescription, changeDetails } from "../../lib/change-copy";
import AIBriefActions from "./AIBriefActions";

export const dynamic = "force-dynamic";

type DashboardProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

type ReportPayload = {
  biggest_positive?: Change[];
  biggest_negative?: Change[];
  upcoming_catalysts?: { id: number; event_date: string | null; title: string }[];
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function filterHref(market?: string, category?: string, severity?: string, watchlistId?: string) {
  const params = new URLSearchParams();
  if (market) params.set("market", market);
  if (category) params.set("category", category);
  if (severity) params.set("severity", severity);
  if (watchlistId) params.set("watchlist_id", watchlistId);
  const query = params.toString();
  return query ? `/dashboard?${query}` : "/dashboard";
}

export default async function Dashboard({ searchParams }: DashboardProps) {
  const params = await searchParams;
  const market = first(params.market);
  const category = first(params.category);
  const severity = first(params.severity);
  const watchlistId = first(params.watchlist_id);
  let changes = [] as Awaited<ReturnType<typeof getChanges>>;
  let reports = [] as Awaited<ReturnType<typeof getDailyReports>>;
  let aiReports = [] as Awaited<ReturnType<typeof getDailyReports>>;
  const [changeResult, reportResult, watchlistResult] = await Promise.allSettled([
    getChanges({ market, category, severity, watchlistId: watchlistId ? Number(watchlistId) : undefined }),
    getDailyReports("market"),
    getWatchlists(),
  ]);
  if (changeResult.status === "fulfilled") changes = changeResult.value;
  if (reportResult.status === "fulfilled") reports = reportResult.value;
  const aiReportResult = await Promise.allSettled([getDailyReports("ai_market")]);
  if (aiReportResult[0].status === "fulfilled") aiReports = aiReportResult[0].value;
  const watchlists = watchlistResult.status === "fulfilled" ? watchlistResult.value : [];

  const filters = [
    ["全部訊號", filterHref(), !market && !category && !severity && !watchlistId],
    ["美股", filterHref("US"), market === "US"],
    ["台股", filterHref("TW"), market === "TW"],
    ["預期", filterHref(undefined, "expectation"), category === "expectation"],
    ["價格", filterHref(undefined, "price"), category === "price"],
    ["基本面", filterHref(undefined, "fundamental"), category === "fundamental"],
    ["資金流", filterHref(undefined, "flow"), category === "flow"],
    ["新聞", filterHref(undefined, "news"), category === "news"],
    ["催化事件", filterHref(undefined, "event"), category === "event"],
    ["重要", filterHref(undefined, undefined, "important"), severity === "important"],
    ["關鍵", filterHref(undefined, undefined, "critical"), severity === "critical"],
    ...watchlists.map((watchlist) => [watchlist.name.toUpperCase(), filterHref(undefined, undefined, undefined, String(watchlist.id)), watchlistId === String(watchlist.id)] as const),
  ] as const;
  const date = new Intl.DateTimeFormat("zh-TW", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date());
  const reportPayload = (reports[0]?.payload ?? {}) as ReportPayload;
  const isFiltered = Boolean(market || category || severity || watchlistId);
  const liveChangesById = new Map(changes.map((change) => [String(change.id), change]));
  const dailyHighlights = Array.from(
    new Map<number, Change>(
      [...(reportPayload.biggest_positive ?? []), ...(reportPayload.biggest_negative ?? [])]
        .map((change): [number, Change] => [change.id, liveChangesById.get(String(change.id)) ?? change]),
    ).values(),
  ).slice(0, 3);
  const highlights = dailyHighlights.length ? dailyHighlights : changes.slice(0, 3);

  return (
    <main className="main">
      <div className="eyebrow">市場狀態 / {date}</div>
      <h1>掌握你不在時<br /><span>市場發生的變化。</span></h1>
      <p className="lede">以客觀資料追蹤價格、預期與法人資金流；數字尚未變動前，不妄下結論。</p>
      <nav className="toolbar" aria-label="訊號篩選條件">
        {filters.map(([label, href, selected]) => (
          <Link className={`pill ${selected ? "selected" : ""}`} href={href} key={label}>{label}</Link>
        ))}
      </nav>
      <div className="feed-meta">最近 24 小時 · 分數 50+ · {changes.length} 個訊號</div>
      {reports[0] && <section className="history-block">
        <div className="eyebrow">每日報告 / {reports[0].report_date}</div>
        <div className="metric">{reports[0].title}<span>已儲存的客觀摘要</span></div>
      </section>}
      {!isFiltered && highlights.length > 0 && <section className="signal-section">
        <div className="section-heading"><div><div className="eyebrow">今日重點</div><h2>系統替你挑出的 {highlights.length} 件事</h2></div><a className="pill" href="#all-signals">查看全部 {changes.length} 個訊號</a></div>
        <div className="highlight-list">
          {highlights.map((change) => <Link className="highlight" href={`/company/${change.symbol}`} key={`highlight-${change.id}`}><i className={`rail ${change.direction === "down" ? "down" : ""}`} /><div className="ticker">{change.symbol}<span className="market-label">{change.market}</span></div><div className="metric">{changeDescription(change)}<span>{changeDetails(change)}</span></div><div className="score"><strong>{Math.round(change.total_score)}</strong>{change.severity === "critical" ? "關鍵" : "高優先"}</div></Link>)}
        </div>
      </section>}
      <section className="history-block">
        <div className="eyebrow">AI Market Brief</div>
        <AIBriefActions />
        {aiReports[0] ? <div className="metric">{String((aiReports[0].payload as { summary?: string }).summary ?? "")}<span>僅使用已儲存的變化與催化事件；非投資建議。</span></div> : <div className="empty">尚未產生 AI Daily Brief。</div>}
      </section>
      <section className="signal-section" id="all-signals">
        <div className="section-heading"><div><div className="eyebrow">全部訊號</div><h2>{isFiltered ? "篩選結果" : "可點入追查完整資料"}</h2></div><span className="section-count">{changes.length} 個訊號</span></div>
        <div className="feed">
        {changes.length ? changes.map((change) => (
          <Link className="change" href={`/company/${change.symbol}`} key={change.id}>
            <i className={`rail ${change.direction === "down" ? "down" : ""}`} />
            <div className="ticker">{change.symbol}<span className="market-label">{change.market}</span></div>
            <div className="metric">{changeDescription(change)}
              <span>{changeDetails(change)}</span>
            </div>
            <div className={`delta ${change.direction === "down" ? "negative" : ""}`}>
              {change.percentage_change == null ? "新增" : `${change.percentage_change > 0 ? "+" : ""}${change.percentage_change.toFixed(2)}%`}
            </div>
            <div className="score"><strong>{Math.round(change.total_score)}</strong>{change.severity}</div>
          </Link>
        )) : <div className="empty"><strong>尚無已評分的變化。</strong><br />請執行資料蒐集流程，將來源快照轉換為第一筆市場差異。</div>}
        </div>
      </section>
    </main>
  );
}
