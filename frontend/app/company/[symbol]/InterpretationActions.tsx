"use client";

import { useState } from "react";

import { generateCompanyInterpretation } from "../../../lib/api";

export default function InterpretationActions({ symbol }: { symbol: string }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    setMessage("");
    try {
      await generateCompanyInterpretation(symbol);
      setMessage("已產生解讀；重新整理即可查看最新結果。");
    } catch {
      setMessage("目前沒有可供解讀的重大變化。");
    } finally {
      setBusy(false);
    }
  }

  return <div className="toolbar"><button className="pill selected" disabled={busy} onClick={generate}>{busy ? "產生中..." : "產生解讀"}</button>{message && <span className="feed-meta">{message}</span>}</div>;
}
