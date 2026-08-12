import Link from "next/link";
import { getAlertDeliveries, getChanges, getDailyReports, getWatchlists, type Change } from "../../lib/api";

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
  let deliveries = [] as Awaited<ReturnType<typeof getAlertDeliveries>>;
  const [changeResult, reportResult, deliveryResult, watchlistResult] = await Promise.allSettled([
    getChanges({ market, category, severity, watchlistId: watchlistId ? Number(watchlistId) : undefined }),
    getDailyReports("market"),
    getAlertDeliveries(),
    getWatchlists(),
  ]);
  if (changeResult.status === "fulfilled") changes = changeResult.value;
  if (reportResult.status === "fulfilled") reports = reportResult.value;
  if (deliveryResult.status === "fulfilled") deliveries = deliveryResult.value;
  const watchlists = watchlistResult.status === "fulfilled" ? watchlistResult.value : [];

  const filters = [
    ["ALL SIGNALS", filterHref(), !market && !category && !severity && !watchlistId],
    ["US", filterHref("US"), market === "US"],
    ["TAIWAN", filterHref("TW"), market === "TW"],
    ["EXPECTATIONS", filterHref(undefined, "expectation"), category === "expectation"],
    ["PRICE", filterHref(undefined, "price"), category === "price"],
    ["FUNDAMENTAL", filterHref(undefined, "fundamental"), category === "fundamental"],
    ["FLOW", filterHref(undefined, "flow"), category === "flow"],
    ["NEWS", filterHref(undefined, "news"), category === "news"],
    ["CATALYST", filterHref(undefined, "event"), category === "event"],
    ["IMPORTANT", filterHref(undefined, undefined, "important"), severity === "important"],
    ["CRITICAL", filterHref(undefined, undefined, "critical"), severity === "critical"],
    ...watchlists.map((watchlist) => [watchlist.name.toUpperCase(), filterHref(undefined, undefined, undefined, String(watchlist.id)), watchlistId === String(watchlist.id)] as const),
  ] as const;
  const date = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date());
  const reportPayload = (reports[0]?.payload ?? {}) as ReportPayload;

  return (
    <main className="main">
      <div className="eyebrow">Market state / {date}</div>
      <h1>What changed<br /><span>while you were away.</span></h1>
      <p className="lede">A deterministic read of price, expectations and institutional flow. No narrative until the numbers have moved.</p>
      <nav className="toolbar" aria-label="Change feed filters">
        {filters.map(([label, href, selected]) => (
          <Link className={`pill ${selected ? "selected" : ""}`} href={href} key={label}>{label}</Link>
        ))}
      </nav>
      <div className="feed-meta">LAST 24 HOURS · SCORE 50+ · {changes.length} SIGNALS</div>
      {reports[0] && <section className="history-block">
        <div className="eyebrow">Daily report / {reports[0].report_date}</div>
        <div className="metric">{reports[0].title}<span>Persisted deterministic digest · {deliveries.length} alert deliveries</span></div>
      </section>}
      {reports[0]?.payload && <section className="history-block">
        <div className="eyebrow">Signal balance</div>
        <div className="history-list">
          {[...(reportPayload.biggest_positive ?? []), ...(reportPayload.biggest_negative ?? [])].slice(0, 10).map((item) => <div className="history-row" key={`report-${item.id}`}><span className="history-metric">{item.symbol}</span><span>{item.metric.replaceAll("_", " ")}</span><strong className={item.direction === "down" ? "negative" : ""}>{item.percentage_change == null ? "NEW" : `${item.percentage_change.toFixed(2)}%`}</strong></div>)}
          {(reportPayload.upcoming_catalysts ?? []).slice(0, 5).map((event) => <div className="history-row" key={`event-${event.id}`}><span className="history-date">{event.event_date ?? "TBD"}</span><span className="history-metric">{event.title}</span><span className="history-unit">CATALYST</span></div>)}
        </div>
      </section>}
      <section className="feed">
        {changes.length ? changes.map((change) => (
          <Link className="change" href={`/company/${change.symbol}`} key={change.id}>
            <i className={`rail ${change.direction === "down" ? "down" : ""}`} />
            <div className="ticker">{change.symbol}<span className="market-label">{change.market}</span></div>
            <div className="metric">{change.metric.replaceAll("_", " ")}
              <span>{change.period ?? "1D"} · {change.category} · {change.source_code ?? "unknown source"}</span>
            </div>
            <div className={`delta ${change.direction === "down" ? "negative" : ""}`}>
              {change.percentage_change == null ? "NEW" : `${change.percentage_change > 0 ? "+" : ""}${change.percentage_change.toFixed(2)}%`}
            </div>
            <div className="score"><strong>{Math.round(change.total_score)}</strong>{change.severity}</div>
          </Link>
        )) : <div className="empty"><strong>No scored changes yet.</strong><br />Run the collector pipeline to turn source snapshots into the first market diff.</div>}
      </section>
    </main>
  );
}
