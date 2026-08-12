import type { Change } from "./api";

const metricLabels: Record<string, string> = {
  benchmark_relative_return: "相對大盤表現",
  breakout: "20 日突破新高",
  close: "收盤價",
  drawdown: "距 20 日高點跌幅",
  eps_estimate: "每股盈餘預估",
  foreign_investor: "外資買賣超",
  investment_trust: "投信買賣超",
  monthly_revenue: "月營收",
  relative_volume: "相對成交量",
  volatility: "波動度",
  volume: "成交量",
};

function periodLabel(period: string | null) {
  if (period === "previous" || period === "1d") return "前一交易日";
  if (period === "5d") return "5 個交易日";
  if (period === "20d") return "20 個交易日";
  return period;
}

export function changeTitle(change: Change) {
  if (change.category === "news") return "新增新聞";
  if (change.category === "event") return "新增事件";
  if (change.metric.startsWith("holder_")) return "大戶持股";
  return metricLabels[change.metric] ?? change.metric.replaceAll("_", " ");
}

export function changeDescription(change: Change) {
  if (change.category === "news") return change.headline ?? `${change.symbol} 新增一則新聞`;
  if (change.category === "event") return change.event_title ?? `${change.symbol} 新增一項公司事件`;
  if (change.percentage_change == null) return `${change.symbol} 出現${changeTitle(change)}變化`;
  const direction = change.percentage_change >= 0 ? "增加" : "減少";
  const period = periodLabel(change.period);
  const comparedTo = period ? `較${period}` : "較前期";
  return `${change.symbol} ${changeTitle(change)}${comparedTo}${direction} ${Math.abs(change.percentage_change).toFixed(2)}%`;
}

export function changeContext(change: Change) {
  if (change.category === "news") return "新聞";
  if (change.category === "event") return "公司事件";
  return periodLabel(change.period) ?? "本期";
}

export function changeDetails(change: Change) {
  const source = change.source_name ?? change.source_code ?? "未知來源";
  const descriptor = change.category === "news" ? change.metric : change.severity;
  const isNews = change.category === "news";
  const label = isNews ? "發佈於" : change.category === "event" ? "事件日" : "資料日";
  const formatter = new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(isNews ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: "UTC",
  });
  const timestamp = change.effective_at ?? change.detected_at;
  const parsedDate = timestamp ? new Date(timestamp) : null;
  const date = parsedDate && !Number.isNaN(parsedDate.getTime())
    ? formatter.format(parsedDate)
    : "日期未提供";
  return `${changeContext(change)} · ${source} · ${descriptor} · ${label} ${date}`;
}
