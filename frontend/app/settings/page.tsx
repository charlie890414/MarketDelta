import { getJobs } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function Settings() {
  try {
    const jobs = await getJobs();
      return <main className="main"><div className="eyebrow">系統狀態</div><h1>資料來源<br /><span>健康度。</span></h1><p className="lede">蒐集器與 API 分開執行，每一次嘗試都會留下工作紀錄。</p><section className="feed">{jobs.map(job => <div className="change job-run" key={job.id}><i className={`rail ${job.status === "success" ? "" : "down"}`} /><div className="ticker job-name" title={job.job_name}>{job.job_name}</div><div className="metric">{job.status}<span>{new Date(job.started_at).toLocaleString("zh-TW")}{job.error_summary ? ` · ${job.error_summary}` : ""}</span></div><div className="delta">已擷取 {job.items_fetched}</div><div className="score"><strong>{job.items_changed}</strong>{job.items_failed ? `${job.items_failed} 筆失敗` : "筆變化"}</div></div>)}</section></main>;
  } catch { return <main className="main"><div className="eyebrow">系統狀態</div><h1>資料來源<br /><span style={{ color: "#d9ff62" }}>健康度。</span></h1><div className="empty">目前無法取得工作資料。</div></main>; }
}
