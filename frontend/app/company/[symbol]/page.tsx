import Link from "next/link";
import { getCompany, getCompanyChanges, getCompanyEvents, getCompanyHistory, getCompanyInterpretations, getCompanyNews, getCompanyOwnership } from "../../../lib/api";
import { changeDescription, changeDetails, changeTitle } from "../../../lib/change-copy";
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
      <Link className="eyebrow" href="/dashboard">← 返回訊號列表</Link>
      <h1>{company.symbol}<br /><span>{company.company_name}.</span></h1>
      <p className="lede">{company.market} / {company.exchange ?? "市場"} / {company.currency}。客觀變化與解讀內容分開呈現。</p>
      <nav className="toolbar" aria-label="公司頁面區段導覽">
        <a className="pill selected" href="#changes">{changes.length} 項變化</a>
        <a className="pill" href="#history">{history.length} 筆觀測</a>
      </nav>
      <section className="feed" id="changes">
        {changes.length ? changes.map((change) => <div className="change" key={change.id}>
          <i className={`rail ${change.direction === "down" ? "down" : ""}`} />
          <div className="ticker">{changeTitle(change)}</div>
          <div className="metric">{changeDescription(change)}
            <span>{changeDetails(change)}</span>
          </div>
          <div className={`delta ${change.direction === "down" ? "negative" : ""}`}>
            {change.percentage_change == null ? "新增" : `${change.percentage_change > 0 ? "+" : ""}${change.percentage_change.toFixed(2)}%`}
          </div>
          <div className="score"><strong>{Math.round(change.total_score)}</strong>分</div>
        </div>) : <div className="empty">這間公司尚無變化紀錄。</div>}
      </section>
      <section className="history-block" id="history">
        <div className="eyebrow">快照歷史</div>
        <div className="history-list">
          {history.slice(-24).reverse().map((point, index) => <div className="history-row" key={`${point.metric}-${point.observed_at}-${index}`}>
            <span className="history-date">{new Date(point.observed_at).toLocaleDateString("zh-TW", { day: "2-digit", month: "short" })}</span>
            <span className="history-metric">{point.metric.replaceAll("_", " ")}</span>
            <strong>{point.value}</strong>
            <span className="history-unit">{point.unit}</span>
          </div>)}
        </div>
      </section>
      <section className="history-block">
        <div className="eyebrow">未來催化事件</div>
        <div className="history-list">{events.slice(0, 8).map((event) => <div className="history-row" key={event.id}><span className="history-date">{event.event_date ?? "待定"}</span><span className="history-metric">{event.title}</span><span className="history-unit">{event.event_type}</span></div>)}</div>
      </section>
      <section className="history-block">
        <div className="eyebrow">AI 解讀</div>
        <InterpretationActions symbol={symbol} />
        {interpretations.length ? interpretations.slice(0, 3).map((item) => <article className="empty" key={item.id}>
          <strong>{item.summary}</strong><br />{item.why_it_matters}<br /><span className="history-unit">{item.model_provider} / {item.model_name} · 產生於 {new Date(item.generated_at).toLocaleString("zh-TW")}</span>
          {item.supporting_signals.length > 0 && <><br /><span className="history-unit">支持訊號：{item.supporting_signals.join(" · ")}</span></>}
          {item.contradictions.length > 0 && <><br /><span className="history-unit">相反訊號：{item.contradictions.join(" · ")}</span></>}
          {item.watch_next.length > 0 && <><br /><span className="history-unit">後續觀察：{item.watch_next.join(" · ")}</span></>}
        </article>) : <div className="empty">尚未產生解讀；上方仍可查看客觀變化。</div>}
      </section>
      <section className="history-block">
        <div className="eyebrow">新聞 / 持股</div>
        <div className="history-list">
          {news.slice(0, 5).map((item) => <div className="history-row" key={item.id}><span className="history-date">{new Date(item.published_at).toLocaleDateString("zh-TW")}</span><span className="history-metric">{item.headline}</span><span className="history-unit">{item.source_name ?? "來源"}</span></div>)}
          {ownership.slice(0, 5).map((item) => <div className="history-row" key={`ownership-${item.id}`}><span className="history-date">{item.snapshot_date}</span><span className="history-metric">{item.holder_bucket}</span><strong>{item.ownership_pct ?? "-"}%</strong><span className="history-unit">持股</span></div>)}
        </div>
      </section>
    </main>;
  } catch {
    return <main className="main"><Link className="eyebrow" href="/dashboard">← 返回訊號列表</Link><h1>{symbol}</h1><div className="empty">目前無法取得公司資料。</div></main>;
  }
}
