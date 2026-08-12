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
      setMessage("Interpretation generated. Refresh to view the latest result.");
    } catch {
      setMessage("No material changes are available for interpretation.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="toolbar"><button className="pill selected" disabled={busy} onClick={generate}>{busy ? "GENERATING..." : "GENERATE"}</button>{message && <span className="feed-meta">{message}</span>}</div>;
}
