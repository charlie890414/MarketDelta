"use client";

import { useEffect, useState } from "react";

const translations: Record<string, string> = {
  "市場變化 / 0.1": "MARKET DIFF / 0.1", "儀表板": "Dashboard", "自選清單": "Watchlist", "行事曆": "Calendar", "系統": "System",
  "市場狀態 / ": "Market state / ", "掌握你不在時": "What changed", "市場發生的變化。": "while you were away.", "以客觀資料追蹤價格、預期與法人資金流；數字尚未變動前，不妄下結論。": "A deterministic read of price, expectations and institutional flow. No narrative until the numbers have moved.",
  "全部訊號": "ALL SIGNALS", "美股": "US", "台股": "TAIWAN", "預期": "EXPECTATIONS", "價格": "PRICE", "基本面": "FUNDAMENTAL", "資金流": "FLOW", "新聞": "NEWS", "催化事件": "CATALYST", "重要": "IMPORTANT", "關鍵": "CRITICAL",
  "最近 24 小時 · 分數 50+ · ": "LAST 24 HOURS · SCORE 50+ · ", " 個訊號": " SIGNALS", "每日報告 / ": "Daily report / ", "已儲存的客觀摘要 · ": "Persisted deterministic digest · ", " 筆通知紀錄": " alert deliveries", "訊號概況": "Signal balance", "新增": "NEW", "待定": "TBD", "未知來源": "unknown source", "尚無已評分的變化。": "No scored changes yet.", "請執行資料蒐集流程，將來源快照轉換為第一筆市場差異。": "Run the collector pipeline to turn source snapshots into the first market diff.",
  "追蹤標的": "Tracked universe", "你的": "Your", "自選清單。": "watchlists.", "聚焦於變化值得採取行動的公司。": "Keep the engine focused on the names where a change is actionable.", " 個標的": " instruments", "尚無標的": "No instruments yet", "使用中": "ACTIVE", "空白": "EMPTY", "目前無法取得自選清單資料。": "Watchlist data is unavailable.", "管理追蹤標的": "Manage tracked universe", "新增自選清單": "New watchlist", "建立": "CREATE", "選擇清單": "Choose list", "股票代號或公司名稱": "Ticker or company", "搜尋": "SEARCH", "市場": "market", "加入": "ADD", "尚未追蹤": "Not tracked yet", "建立後即可加入選定的自選清單。": "Create it, then add it to the selected watchlist.", "公司名稱（選填）": "Company name (optional)", "建立並加入": "CREATE & ADD", "無說明": "No description", "刪除": "DELETE", "移除": "REMOVE",
  "未來催化事件 / 30 天內": "Upcoming catalysts / next 30 days", "下一個": "The next", "已知日期。": "known dates.", "財報、申報與公司事件，應與它們可能解釋的市場變化一併檢視。": "Earnings, filings and company events belong next to the changes they may explain.", "尚未載入未來事件；啟用事件蒐集器後，行事曆將自動補上資料。": "No upcoming events loaded. The calendar will fill as event collectors are enabled.", "目前無法取得事件資料。": "Event data is unavailable.",
  "系統狀態": "System status", "資料來源": "Source", "健康度。": "health.", "蒐集器與 API 分開執行，每一次嘗試都會留下工作紀錄。": "Collectors run separately from the API, with every attempt recorded as a job run.", "已擷取 ": "", " 筆失敗": " failed", "筆變化": "changes", "通知規則": "Alert rules", "分數 ≥ ": "score ≥ ", "所有市場": "all markets", "所有類別": "all categories", "開啟": "ON", "關閉": "OFF", "目前無法取得工作資料。": "Job data is unavailable.",
  "← 返回訊號列表": "← back to feed", "客觀變化與解讀內容分開呈現。": "Objective changes are kept separate from interpretation.", " 項變化": " CHANGES", " 筆觀測": " OBSERVATIONS", "這間公司尚無變化紀錄。": "No changes recorded for this company.", "快照歷史": "Snapshot history", "AI 解讀": "AI interpretation", "產生解讀": "GENERATE", "產生中...": "GENERATING...", "尚未產生解讀；上方仍可查看客觀變化。": "No interpretation generated. Objective changes remain available above.", "新聞 / 持股": "News / ownership", "來源": "source", "持股": "ownership", "目前無法取得公司資料。": "Company data is unavailable.",
};

function replaceText(locale: "zh-Hant" | "en") {
  const map = locale === "en" ? translations : Object.fromEntries(Object.entries(translations).map(([zh, en]) => [en, zh]));
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  nodes.forEach((node) => {
    const replacement = map[node.nodeValue ?? ""];
    if (replacement) node.nodeValue = replacement;
  });
}

export default function LanguageToggle() {
  const [locale, setLocale] = useState<"zh-Hant" | "en">("zh-Hant");
  useEffect(() => {
    const saved = document.cookie.match(/(?:^|; )mce_locale=(zh-Hant|en)/)?.[1] as "zh-Hant" | "en" | undefined;
    const next = saved ?? "zh-Hant";
    setLocale(next);
    document.documentElement.lang = next;
    if (next === "en") replaceText(next);
  }, []);
  function toggle() {
    const next = locale === "zh-Hant" ? "en" : "zh-Hant";
    replaceText(next);
    document.cookie = `mce_locale=${next}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = next;
    setLocale(next);
  }
  return <button className="locale-toggle pill" type="button" onClick={toggle} aria-label="切換語言">{locale === "zh-Hant" ? "EN" : "繁中"}</button>;
}
