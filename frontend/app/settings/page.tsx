import { getJobs } from "../../lib/api";

export default async function Settings() {
  try {
    const jobs = await getJobs();
    return <main className="main"><div className="eyebrow">System status</div><h1>Source<br /><span style={{ color: "#d9ff62" }}>health.</span></h1><p className="lede">Collectors run separately from the API, with every attempt recorded as a job run.</p><section className="feed">{jobs.map(job => <div className="change" key={job.id}><i className={`rail ${job.status === "success" ? "" : "down"}`} /><div className="ticker">{job.job_name}</div><div className="metric">{job.status}<span>{new Date(job.started_at).toLocaleString()}</span></div><div className="delta">{job.items_fetched} fetched</div><div className="score"><strong>{job.items_changed}</strong>changes</div></div>)}</section></main>;
  } catch { return <main className="main"><div className="eyebrow">System status</div><h1>Source<br /><span style={{ color: "#d9ff62" }}>health.</span></h1><div className="empty">Job data is unavailable.</div></main>; }
}
