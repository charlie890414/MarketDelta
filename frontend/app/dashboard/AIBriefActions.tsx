"use client";

import { useState } from "react";
import { generateAIDailyBrief } from "../../lib/api";

export default function AIBriefActions() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function generate() {
    setBusy(true); setMessage("");
    try { await generateAIDailyBrief(); setMessage("已更新，重新整理即可查看。"); }
    catch { setMessage("產生失敗，請確認後端與資料庫狀態。"); }
    finally { setBusy(false); }
  }
  return <div className="toolbar"><button className="pill selected" onClick={generate} disabled={busy}>{busy ? "產生中..." : "更新 AI Brief"}</button>{message && <span className="feed-meta">{message}</span>}</div>;
}
