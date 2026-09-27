// Codex companion row. Quota is account-wide; token totals cover local transcripts.
const tok = n => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n || 0)
const label = mins => mins === 10080 ? "week" : mins % 1440 === 0 ? `${mins / 1440}d` : mins % 60 === 0 ? `${mins / 60}h` : `${mins}m`
const left = days => days >= 1 ? `${days.toFixed(1)}d` : `${Math.max(0, Math.ceil(days * 24))}h`
const age = ts => {
  const mins = Math.max(0, Math.floor((Date.now() / 1000 - ts) / 60))
  return mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`
}

export const CodexRow = ({ data }) => {
  if (!data) return <div className="row row2"><span className="lbl">codex</span><span className="hint" style={{ marginLeft: 12 }}>waiting for first collection…</span></div>
  const daily = data.daily || []
  const projects = data.projects || []
  const maxDay = Math.max(1, ...daily.map(d => d.tokens))
  const total = daily.reduce((n, d) => n + d.tokens, 0)
  return (
    <div className="row row2 codexRow">
      <div className="card cardInline">
        <span className="lbl">codex</span>
        <span className="hint">${data.subscription_usd}/mo</span>
        {data.collector_stale && <span style={{ color: "#FFB800" }}>collector stale</span>}
        <div className="tip">
          <span className="tipHead">Codex · subscription</span>
          <span className="tipVal">${data.subscription_usd}/month</span>{"\n"}
          <span className="tipKey">Collected {age(data.collected_at)}</span>
          <span className="tipNote">Subscription cost configured from your plan. Token totals are local activity, not a dollar balance or a bill.</span>
        </div>
      </div>
      {(data.windows || []).length === 0 && <span className="hint">quota not available yet</span>}
      {(data.windows || []).map(w => {
        const hot = w.used_pct >= 90 || w.projected_pct > 99
        const color = hot || w.stale ? "#FFB800" : "#4AE3FF"
        return <div className="card cardInline" key={`${w.bucket}-${w.slot}`}>
          <span className="lbl">{w.bucket === "codex" ? "" : `${w.bucket} · `}{label(w.minutes)}</span>
          <span style={{ width: 65, height: 5, background: "#293343", display: "inline-block" }}>
            <span style={{ width: `${Math.max(0, Math.min(100, w.used_pct))}%`, height: "100%", background: color, display: "block" }} />
          </span>
          <span className="val" style={{ color }}>{w.used_pct.toFixed(0)}%</span>
          <span className="hint">{w.expired ? "awaiting reset reading" : `reset ${left(w.days_left)}`}</span>
          <span className="hint">{w.stale ? `stale · ${age(w.observed_at)}` : age(w.observed_at)}</span>
          {!w.stale && w.budget_per_day != null && <span className="hint">{w.budget_per_day.toFixed(1)}%/day budget</span>}
          {!w.stale && w.projected_pct != null && <span style={{ color }}>{w.projected_pct > 99 ? "pace over budget" : "pace within budget"}</span>}
          <div className="tip">
            <span className="tipHead">Codex · {label(w.minutes)} allowance</span>
            <span className="tipVal">{w.used_pct.toFixed(1)}% used · {Math.max(0, 100 - w.used_pct).toFixed(1)}% remaining</span>{"\n"}
            <span className="tipKey">Reset </span><span className="tipVal">{new Date(w.reset_at * 1000).toLocaleString()}</span>{"\n"}
            <span className="tipKey">Observed {age(w.observed_at)} · {w.source === "app-server" ? "account quota" : "session quota snapshot"}</span>{"\n"}
            {w.projected_pct != null && <span className="tipVal">Projected {w.projected_pct.toFixed(0)}% at reset at recent pace</span>}
            <span className="tipNote">Budget targets 99% by reset. Projection uses observed quota changes within this same window over up to 24 hours; short bursts can skew it. Missing or expired quota stays unknown until a new reading.</span>
          </div>
        </div>
      })}
      <div className="card cardInline">
        <span className="lbl">today</span>
        <span className="val">{tok(data.today.tokens)} <span className="hint">tokens</span></span>
        <span className="hint">{data.today.responses.toLocaleString()} responses</span>
        <div className="tip">
          <span className="tipHead">Codex today · {data.timezone}</span>
          <span className="tipVal">{data.today.tokens.toLocaleString()} tokens · {data.today.responses.toLocaleString()} responses</span>{"\n"}
          <span className="tipKey">Input cache hit </span><span className="tipVal">{data.today.cache_hit_pct == null ? "—" : `${data.today.cache_hit_pct}%`}</span>
          <span className="tipNote">Input + output tokens. Cached input and reasoning are subsets, never added twice. Local transcripts only; cloud and other machines may contribute to quota without appearing here.</span>
        </div>
      </div>
      <div className="card cardInline">
        <span className="lbl">7 days</span>
        <span style={{ display: "inline-flex", gap: 3, height: 16, alignItems: "flex-end" }}>
          {daily.map(d => <span key={d.date} title={`${d.date}: ${tok(d.tokens)} tokens`} style={{ width: 5, height: Math.max(1, 16 * d.tokens / maxDay), background: "#4AE3FF", opacity: d.tokens ? 0.8 : 0.2 }} />)}
        </span>
        <span className="hint">{tok(total)}</span>
        {projects[0] && <span className="hint">top: {projects[0].project.split("/").pop()}</span>}
        <div className="tip">
          <span className="tipHead">Codex · last 7 calendar days</span>
          {daily.map(d => <div key={d.date}><span className="tipKey">{d.date} </span><span className="tipVal">{tok(d.tokens)}</span></div>)}
          <span className="tipHead">projects</span>
          {projects.map(p => <div key={p.project}><span className="tipKey">{p.project.split("/").pop()} </span><span className="tipVal">{tok(p.tokens)}</span></div>)}
          <span className="tipHead">models</span>
          {(data.models || []).map(m => <div key={m.model}><span className="tipKey">{m.model} </span><span className="tipVal">{tok(m.tokens)}</span></div>)}
          <span className="tipNote">Local transcript coverage. Days with no recorded usage may mean no local logs are available.</span>
        </div>
      </div>
    </div>
  )
}
