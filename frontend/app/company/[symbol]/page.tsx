import Link from "next/link";
import { getCompany, getCompanyChanges, getCompanyHistory } from "../../../lib/api";

export default async function Company({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  try {
    const [company, changes, history] = await Promise.all([getCompany(symbol), getCompanyChanges(symbol), getCompanyHistory(symbol)]);
    return <main className="main">
      <Link className="eyebrow" href="/dashboard">← back to feed</Link>
      <h1>{company.symbol}<br /><span style={{ color: "#91a099" }}>{company.company_name}.</span></h1>
      <p className="lede">{company.market} / {company.exchange ?? "market"} / {company.currency}. Objective changes are kept separate from interpretation.</p>
      <div className="toolbar"><span className="pill selected">{changes.length} CHANGES</span><span className="pill">{history.length} OBSERVATIONS</span></div>
      <section className="feed">{changes.length ? changes.map(change => <div className="change" key={change.id}><i className={`rail ${change.direction === "down" ? "down" : ""}`} /><div className="ticker">{change.metric.replaceAll("_", " ")}</div><div className="metric">{change.previous_value ?? "NEW"} → {change.current_value ?? ""}<span>{change.category} · {change.period ?? "1D"} · {change.severity}</span></div><div className={`delta ${change.direction === "down" ? "negative" : ""}`}>{change.percentage_change == null ? "NEW" : `${change.percentage_change > 0 ? "+" : ""}${change.percentage_change.toFixed(2)}%`}</div><div className="score"><strong>{Math.round(change.total_score)}</strong>score</div></div>) : <div className="empty">No changes recorded for this company.</div>}</section>
    </main>;
  } catch {
    return <main className="main"><Link className="eyebrow" href="/dashboard">← back to feed</Link><h1>{symbol}</h1><div className="empty">Company data is unavailable.</div></main>;
  }
}
