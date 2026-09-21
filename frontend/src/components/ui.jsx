// Small shared presentation pieces. Nothing here fetches or decides anything --
// it exists so a badge means the same thing on the Ask screen and the queue.

export function Badge({ children, tone = "neutral", title }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {children}
    </span>
  );
}

export function ErrorNote({ children }) {
  return (
    <p className="error-note" role="alert">
      {children}
    </p>
  );
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>;
}

export function Spinner({ label }) {
  return (
    <p className="spinner" role="status">
      <span className="spinner-dot" aria-hidden="true" />
      {label}
    </p>
  );
}

/** Confidence against the threshold that gates routing, drawn rather than
 *  stated: the marker is where the API's own cutoff sits. */
export function ConfidenceMeter({ value, threshold }) {
  const confident = threshold === undefined || value >= threshold;
  const tone = confident ? "ok" : "warn";
  return (
    <div className="meter">
      <div className="meter-head">
        <span className="meter-label">Confidence</span>
        <span className={`meter-value meter-value-${tone}`}>{value.toFixed(2)}</span>
      </div>
      <div className="meter-track">
        <div className={`meter-fill meter-fill-${tone}`} style={{ width: `${clamp(value) * 100}%` }} />
        {threshold !== undefined && (
          <span
            className="meter-threshold"
            style={{ left: `${clamp(threshold) * 100}%` }}
            title={`routing threshold ${threshold.toFixed(2)}`}
          />
        )}
      </div>
      {threshold !== undefined && (
        <p className="meter-foot">
          {confident ? "above" : "below"} the {threshold.toFixed(2)} routing threshold
        </p>
      )}
    </div>
  );
}

function clamp(n) {
  return Math.max(0, Math.min(1, n));
}
