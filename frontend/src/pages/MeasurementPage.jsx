// The measurement deliverable (Part 3 section 4), on screen rather than only in
// the README -- with the live number next to the claim, because a metric you
// cannot currently read is a plan, not instrumentation.
//
// Everything here comes from GET /metrics, which aggregates rows the system
// already writes: query_log, gaps, corrections, ingestion_runs.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Badge, Empty, ErrorNote, Spinner } from "../components/ui";
import { fileName, formatTimestamp, percent } from "../lib/format";

const TARGET = 0.7;

export default function MeasurementPage() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMetrics(await api.getMetrics());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="page">
      <div className="page-head">
        <h2>Measurement</h2>
        <p className="subtle">
          The first-30-days metric, read live from <code>GET /metrics</code>.
        </p>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}
      {loading && !metrics && <Spinner label="Loading metrics…" />}
      {metrics && <MetricsBody metrics={metrics} onRefresh={load} loading={loading} />}
    </section>
  );
}

function MetricsBody({ metrics, onRefresh, loading }) {
  const q = metrics.queries;
  const headline = q.answered_without_intervention;

  return (
    <>
      <article className="card headline">
        <div className="headline-main">
          <p className="headline-label">Queries answered without intervention</p>
          <p className="headline-value">{percent(headline)}</p>
          <p className="subtle">
            Neither routed to a human nor subsequently corrected, counted per query so a routed
            query that was also corrected is not double-counted. Target for the first 30 days:{" "}
            {percent(TARGET)}.
          </p>
        </div>
        <div className="headline-side">
          <Tile
            label={`Trailing ${q.recent.window}`}
            value={percent(q.recent.answered_without_intervention)}
            hint={`${q.recent.count} queries`}
            tone={toneFor(q.recent.answered_without_intervention, headline)}
          />
          <Tile label="All time" value={percent(headline)} hint={`${q.total} queries`} />
        </div>
      </article>

      <div className="tile-grid">
        <Tile label="Routing rate" value={percent(q.routing_rate)} hint={`trailing ${percent(q.recent.routing_rate)}`} />
        <Tile
          label="Correction rate"
          value={percent(q.correction_rate)}
          hint={`trailing ${percent(q.recent.correction_rate)}`}
        />
        <Tile
          label="Avg confidence"
          value={q.avg_confidence === null ? "—" : q.avg_confidence.toFixed(2)}
          hint={`threshold ${metrics.confidence_threshold.toFixed(2)}`}
        />
        <Tile label="Open gaps" value={metrics.gaps.open} hint={`${metrics.gaps.resolved} resolved`} />
        <Tile label="Corrections" value={metrics.corrections.total} hint={`${metrics.corrections.corrected_queries} queries`} />
        <Tile
          label="Latency"
          value={q.recent.latency_p50_ms === null ? "—" : `${Math.round(q.recent.latency_p50_ms)} ms`}
          hint={latencyHint(q.recent)}
        />
      </div>

      <article className="card">
        <h3>Why this number</h3>
        <p className="prose">
          The number to watch is the share of queries answered without intervention, because it is
          the only one that moves for both failure modes that matter: the system not knowing, and
          the system being wrong. Every query already writes a <code>query_log</code> row with its
          computed confidence, latency and a <code>routed</code> flag; every escalation writes a{" "}
          <code>gaps</code> row and every human fix a <code>corrections</code> row, both foreign-keyed
          back to that query — so the metric needs no new instrumentation and a weekly read is a
          single request. The trailing window beside the all-time figure is the early-warning signal:
          5% routing all-time against 40% over the last {q.recent.window} means the corpus has gone
          stale against what people are now asking, and ingestion health below shows whether the
          cause is in the corpus. Reading gaps and corrections together is deliberate — a rate that
          climbs by suppressing routing would show up as falling gaps and rising corrections.
        </p>
      </article>

      <article className="card">
        <div className="card-head">
          <h3>Confidence trend</h3>
          <button className="btn-secondary" onClick={onRefresh} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {q.confidence_trend.length === 0 ? (
          <Empty>No queries logged yet.</Empty>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Queries</th>
                <th>Avg confidence</th>
                <th>Routing rate</th>
              </tr>
            </thead>
            <tbody>
              {q.confidence_trend.map((day) => (
                <tr key={day.date}>
                  <td className="mono">{day.date}</td>
                  <td>{day.queries}</td>
                  <td>{day.avg_confidence === null ? "—" : day.avg_confidence.toFixed(2)}</td>
                  <td>{percent(day.routing_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </article>

      <article className="card">
        <h3>Weakest queries</h3>
        {q.lowest_confidence.length === 0 ? (
          <Empty>No queries logged yet.</Empty>
        ) : (
          <ul className="weak-list">
            {q.lowest_confidence.map((row) => (
              <li key={row.query_id}>
                <span className="mono">{row.confidence === null ? "—" : row.confidence.toFixed(2)}</span>
                <span>“{row.query_text}”</span>
                {row.routed && <Badge tone="warn">routed</Badge>}
                <span className="subtle">{formatTimestamp(row.timestamp)}</span>
              </li>
            ))}
          </ul>
        )}
      </article>

      <article className="card">
        <h3>Ingestion health</h3>
        <div className="tile-grid">
          <Tile label="Documents" value={metrics.ingestion.documents} hint={`${metrics.ingestion.chunks} chunks`} />
          <Tile
            label="Enrichment confidence"
            value={
              metrics.ingestion.enrichment_confidence_avg === null
                ? "—"
                : metrics.ingestion.enrichment_confidence_avg.toFixed(2)
            }
            hint={`min ${metrics.ingestion.enrichment_confidence_min?.toFixed(2) ?? "—"}`}
          />
          <Tile
            label="Parse failures"
            value={metrics.ingestion.last_run?.parse_failures ?? "—"}
            hint={
              metrics.ingestion.last_run
                ? `last run ${formatTimestamp(metrics.ingestion.last_run.finished_at)}`
                : "no run recorded"
            }
            tone={metrics.ingestion.last_run?.parse_failures ? "warn" : "neutral"}
          />
          <Tile
            label="Enrichment method"
            value={Object.entries(metrics.ingestion.enrichment_methods)
              .map(([method, n]) => `${method} ${n}`)
              .join(" · ") || "—"}
            hint={`${metrics.ingestion.fell_back} fell back`}
            small
          />
        </div>

        {metrics.ingestion.low_confidence_documents.length > 0 && (
          <>
            <h4 className="subhead">Documents enriched below 0.5</h4>
            <ul className="weak-list">
              {metrics.ingestion.low_confidence_documents.map((doc) => (
                <li key={doc.document_id}>
                  <span className="mono">{doc.enrichment_confidence.toFixed(2)}</span>
                  <span className="mono">{fileName(doc.source_path)}</span>
                  {doc.quality_flags.map((flag) => (
                    <Badge key={flag} tone="warn">
                      {flag}
                    </Badge>
                  ))}
                </li>
              ))}
            </ul>
          </>
        )}
      </article>

      <p className="subtle generated">Generated {formatTimestamp(metrics.generated_at)}</p>
    </>
  );
}

function Tile({ label, value, hint, tone = "neutral", small = false }) {
  return (
    <div className={`tile tile-${tone}`}>
      <p className="tile-label">{label}</p>
      <p className={small ? "tile-value tile-value-small" : "tile-value"}>{value}</p>
      {hint && <p className="tile-hint">{hint}</p>}
    </div>
  );
}

// The hint names which percentile the big number is, so with no queries logged
// it has to go too -- a bare "p50" under an em dash labels a value that is not
// there. The other tiles degrade inside their own sentence ("trailing —").
function latencyHint({ latency_p50_ms, latency_p95_ms }) {
  if (latency_p50_ms === null) return null;
  if (latency_p95_ms === null) return "p50";
  return `p50 · p95 ${Math.round(latency_p95_ms)} ms`;
}

// Trailing materially below all-time is the degradation signal worth colouring.
function toneFor(recent, allTime) {
  if (recent === null || allTime === null) return "neutral";
  return recent < allTime - 0.1 ? "warn" : "neutral";
}
