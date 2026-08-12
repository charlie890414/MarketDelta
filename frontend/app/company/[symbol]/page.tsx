import Link from "next/link";
import { getCompany, getCompanyChanges, getCompanyEvents, getCompanyHistory, getCompanyInterpretations, getCompanyNews, getCompanyOwnership } from "../../../lib/api";
import InterpretationActions from "./InterpretationActions";

export const dynamic = "force-dynamic";

export default async function Company({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  try {
    const [company, changes, history, interpretations, news, ownership, events] = await Promise.all([
      getCompany(symbol),
      getCompanyChanges(symbol),
      getCompanyHistory(symbol),
      getCompanyInterpretations(symbol),
      getCompanyNews(symbol),
      getCompanyOwnership(symbol),
      getCompanyEvents(symbol),
    ]);
    return <main className="main">
      <Link className="eyebrow" href="/dashboard">← back to feed</Link>
      <h1>{company.symbol}<br /><span style={{ color: "#91a099" }}>{company.company_name}.</span></h1>
      <p className="lede">{company.market} / {company.exchange ?? "market"} / {company.currency}. Objective changes are kept separate from interpretation.</p>
      <div className="toolbar"><span className="pill selected">{changes.length} CHANGES</span><span className="pill">{history.length} OBSERVATIONS</span></div>
      <section className="feed">
        {changes.length ? changes.map((change) => <div className="change" key={change.id}>
          <i className={`rail ${change.direction === "down" ? "down" : ""}`} />
          <div className="ticker">{change.metric.replaceAll("_", " ")}</div>
          <div className="metric">{change.previous_value ?? "NEW"} → {change.current_value ?? ""}
            <span>{change.category} · {change.period ?? "1D"} · {change.severity} · {change.source_code ?? "unknown source"}</span>
          </div>
          <div className={`delta ${change.direction === "down" ? "negative" : ""}`}>
            {change.percentage_change == null ? "NEW" : `${change.percentage_change > 0 ? "+" : ""}${change.percentage_change.toFixed(2)}%`}
          </div>
          <div className="score"><strong>{Math.round(change.total_score)}</strong>score</div>
        </div>) : <div className="empty">No changes recorded for this company.</div>}
      </section>
      <section className="history-block">
        <div className="eyebrow">Snapshot history</div>
        <div className="history-list">
          {history.slice(-24).reverse().map((point, index) => <div className="history-row" key={`${point.metric}-${point.observed_at}-${index}`}>
            <span className="history-date">{new Date(point.observed_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}</span>
            <span className="history-metric">{point.metric.replaceAll("_", " ")}</span>
            <strong>{point.value}</strong>
            <span className="history-unit">{point.unit}</span>
          </div>)}
        </div>
      </section>
      <section className="history-block">
        <div className="eyebrow">Upcoming catalysts</div>
        <div className="history-list">{events.slice(0, 8).map((event) => <div className="history-row" key={event.id}><span className="history-date">{event.event_date ?? "TBD"}</span><span className="history-metric">{event.title}</span><span className="history-unit">{event.event_type}</span></div>)}</div>
      </section>
      <section className="history-block">
        <div className="eyebrow">AI interpretation</div>
        <InterpretationActions symbol={symbol} />
        {interpretations.length ? interpretations.slice(0, 3).map((item) => <article className="empty" key={item.id}>
          <strong>{item.summary}</strong><br />{item.why_it_matters}<br /><span className="history-unit">{item.model_provider} / {item.model_name} · generated {new Date(item.generated_at).toLocaleString()}</span>
          {item.supporting_signals.length > 0 && <><br /><span className="history-unit">Supporting: {item.supporting_signals.join(" · ")}</span></>}
          {item.contradictions.length > 0 && <><br /><span className="history-unit">Contradictions: {item.contradictions.join(" · ")}</span></>}
          {item.watch_next.length > 0 && <><br /><span className="history-unit">Watch next: {item.watch_next.join(" · ")}</span></>}
        </article>) : <div className="empty">No interpretation generated. Objective changes remain available above.</div>}
      </section>
      <section className="history-block">
        <div className="eyebrow">News / ownership</div>
        <div className="history-list">
          {news.slice(0, 5).map((item) => <div className="history-row" key={item.id}><span className="history-date">{new Date(item.published_at).toLocaleDateString("en-GB")}</span><span className="history-metric">{item.headline}</span><span className="history-unit">{item.source_name ?? "source"}</span></div>)}
          {ownership.slice(0, 5).map((item) => <div className="history-row" key={`ownership-${item.id}`}><span className="history-date">{item.snapshot_date}</span><span className="history-metric">{item.holder_bucket}</span><strong>{item.ownership_pct ?? "-"}%</strong><span className="history-unit">ownership</span></div>)}
        </div>
      </section>
    </main>;
  } catch {
    return <main className="main"><Link className="eyebrow" href="/dashboard">← back to feed</Link><h1>{symbol}</h1><div className="empty">Company data is unavailable.</div></main>;
  }
}
