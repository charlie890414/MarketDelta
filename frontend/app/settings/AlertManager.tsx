"use client";

import { useState } from "react";

import { deleteAlert, updateAlert } from "../../lib/api";

type Alert = Awaited<ReturnType<typeof import("../../lib/api").getAlerts>>[number];

export default function AlertManager({ initialAlerts }: { initialAlerts: Alert[] }) {
  const [alerts, setAlerts] = useState(initialAlerts);
  const [message, setMessage] = useState("");

  async function toggle(alert: Alert) {
    try {
      const updated = await updateAlert(alert.id, { is_enabled: !alert.is_enabled });
      setAlerts((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setMessage("無法更新通知規則。");
    }
  }

  async function remove(alert: Alert) {
    try {
      await deleteAlert(alert.id);
      setAlerts((current) => current.filter((item) => item.id !== alert.id));
    } catch {
      setMessage("無法刪除通知規則。");
    }
  }

  return <>
    {alerts.map((alert) => <div className="change alert-row" key={alert.id}>
      <i className={`rail ${alert.is_enabled ? "" : "down"}`} />
      <div className="ticker">{alert.name}</div>
      <div className="metric">分數 ≥ {alert.min_score}<span>{alert.market ?? "所有市場"} · {alert.category ?? "所有類別"}</span></div>
      <button className={`pill ${alert.is_enabled ? "selected" : ""}`} onClick={() => toggle(alert)}>{alert.is_enabled ? "開啟" : "關閉"}</button>
      <button className="pill" onClick={() => remove(alert)}>刪除</button>
    </div>)}
    {message && <div className="empty">{message}</div>}
  </>;
}
