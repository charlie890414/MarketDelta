import Link from "next/link";
import { getChanges } from "../../lib/api";

type DashboardProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function filterHref(market?: string, category?: string, severity?: string) {
  const params = new URLSearchParams();
  if (market) params.set("market", market);
  if (category) params.set("category", category);
  if (severity) params.set("severity", severity);
  const query = params.toString();
  return query ? `/dashboard?${query}` : "/dashboard";
}

export default async function Dashboard({ searchParams }: DashboardProps) {
  const params = await searchParams;
  const market = first(params.market);
  const category = first(params.category);
  const severity = first(params.severity);
  let changes = [] as Awaited<ReturnType<typeof getChanges>>;
  try {
    changes = await getChanges({ market, category, severity });
  } catch {
    changes = [];
  }

  const filters = [
    ["ALL SIGNALS", filterHref(), !market && !category],
    ["US", filterHref("US"), market === "US"],
    ["TAIWAN", filterHref("TW"), market === "TW"],
    ["EXPECTATIONS", filterHref(undefined, "expectation"), category === "expectation"],
    ["IMPORTANT", filterHref(undefined, undefined, "important"), severity === "important"],
    ["CRITICAL", filterHref(undefined, undefined, "critical"), severity === "critical"],
  ] as const;
  const date = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date());

  return (
    <main className="main">
      <div className="eyebrow">Market state / {date}</div>
      <h1>What changed<br /><span style={{ color: "#d9ff62" }}>while you were away.</span></h1>
      <p className="lede">A deterministic read of price, expectations and institutional flow. No narrative until the numbers have moved.</p>
      <nav className="toolbar" aria-label="Change feed filters">
        {filters.map(([label, href, selected]) => (
          <Link className={`pill ${selected ? "selected" : ""}`} href={href} key={label}>{label}</Link>
        ))}
      </nav>
      <div className="feed-meta">LAST 24 HOURS · SCORE 50+ · {changes.length} SIGNALS</div>
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
