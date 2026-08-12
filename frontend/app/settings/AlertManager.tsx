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
      setMessage("Could not update alert.");
    }
  }

  async function remove(alert: Alert) {
    try {
      await deleteAlert(alert.id);
      setAlerts((current) => current.filter((item) => item.id !== alert.id));
    } catch {
      setMessage("Could not delete alert.");
    }
  }

  return <>
    {alerts.map((alert) => <div className="change" key={alert.id}>
      <div className="ticker">{alert.name}</div>
      <div className="metric">score ≥ {alert.min_score}<span>{alert.market ?? "all markets"} · {alert.category ?? "all categories"}</span></div>
      <button className={`pill ${alert.is_enabled ? "selected" : ""}`} onClick={() => toggle(alert)}>{alert.is_enabled ? "ON" : "OFF"}</button>
      <button className="pill" onClick={() => remove(alert)}>DELETE</button>
    </div>)}
    {message && <div className="empty">{message}</div>}
  </>;
}
