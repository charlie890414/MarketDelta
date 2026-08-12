import { getAlertDeliveries, getAlerts, getJobs } from "../../lib/api";
import AlertManager from "./AlertManager";

export const dynamic = "force-dynamic";

export default async function Settings() {
  try {
    const [jobsResult, alertsResult, deliveriesResult] = await Promise.allSettled([getJobs(), getAlerts(), getAlertDeliveries()]);
    const jobs = jobsResult.status === "fulfilled" ? jobsResult.value : [];
    const alerts = alertsResult.status === "fulfilled" ? alertsResult.value : [];
    const deliveries = deliveriesResult.status === "fulfilled" ? deliveriesResult.value : [];
      return <main className="main"><div className="eyebrow">System status</div><h1>Source<br /><span style={{ color: "#d9ff62" }}>health.</span></h1><p className="lede">Collectors run separately from the API, with every attempt recorded as a job run.</p><section className="feed">{jobs.map(job => <div className="change" key={job.id}><i className={`rail ${job.status === "success" ? "" : "down"}`} /><div className="ticker">{job.job_name}</div><div className="metric">{job.status}<span>{new Date(job.started_at).toLocaleString()}{job.error_summary ? ` · ${job.error_summary}` : ""}</span></div><div className="delta">{job.items_fetched} fetched</div><div className="score"><strong>{job.items_changed}</strong>{job.items_failed ? `${job.items_failed} failed` : "changes"}</div></div>)}</section><section className="history-block"><div className="eyebrow">Alert rules</div><AlertManager initialAlerts={alerts} /><div className="feed-meta">{deliveries.length} recorded deliveries</div></section></main>;
  } catch { return <main className="main"><div className="eyebrow">System status</div><h1>Source<br /><span style={{ color: "#d9ff62" }}>health.</span></h1><div className="empty">Job data is unavailable.</div></main>; }
}
