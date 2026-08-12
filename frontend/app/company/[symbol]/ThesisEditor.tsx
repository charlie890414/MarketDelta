"use client";

import { useState } from "react";
import { saveCompanyThesis } from "../../../lib/api";

type Thesis = {
  thesis: string; key_kpis: string[]; catalysts: string[]; risks: string[]; invalidation_conditions: string[];
};

const split = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);

export default function ThesisEditor({ symbol, initial }: { symbol: string; initial?: Partial<Thesis> & Pick<Thesis, "thesis"> }) {
  const [thesis, setThesis] = useState(initial?.thesis ?? "");
  const [kpis, setKpis] = useState(initial?.key_kpis?.join("\n") ?? "");
  const [catalysts, setCatalysts] = useState(initial?.catalysts?.join("\n") ?? "");
  const [risks, setRisks] = useState(initial?.risks?.join("\n") ?? "");
  const [invalidation, setInvalidation] = useState(initial?.invalidation_conditions?.join("\n") ?? "");
  const [message, setMessage] = useState("");

  async function save() {
    if (!thesis.trim()) return setMessage("請先寫下核心投資論點。");
    try {
      await saveCompanyThesis(symbol, { thesis, key_kpis: split(kpis), catalysts: split(catalysts), risks: split(risks), invalidation_conditions: split(invalidation) });
      setMessage("已儲存；下次 AI 解讀會以此論點檢驗新訊號。");
    } catch { setMessage("儲存失敗，請稍後再試。"); }
  }

  return <div className="history-list">
    <textarea aria-label="核心投資論點" value={thesis} onChange={(e) => setThesis(e.target.value)} placeholder="核心投資論點：為何持有這家公司？" />
    <textarea aria-label="關鍵 KPI" value={kpis} onChange={(e) => setKpis(e.target.value)} placeholder="關鍵 KPI（每行一項）" />
    <textarea aria-label="催化劑" value={catalysts} onChange={(e) => setCatalysts(e.target.value)} placeholder="預期催化劑（每行一項）" />
    <textarea aria-label="風險" value={risks} onChange={(e) => setRisks(e.target.value)} placeholder="主要風險（每行一項）" />
    <textarea aria-label="失效條件" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} placeholder="論點失效條件（每行一項）" />
    <div className="toolbar"><button className="pill selected" onClick={save}>儲存 Thesis</button>{message && <span className="feed-meta">{message}</span>}</div>
  </div>;
}
