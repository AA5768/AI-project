// Correction capture at the point the answer is read, which is the only moment
// someone knows it is wrong. The original answer is not sent: the API copies it
// off the `query_log` row itself, so what gets stored is what the system
// actually said rather than what the browser still had on screen.

import { useState } from "react";
import { api } from "../api/client";
import { ErrorNote } from "./ui";

export default function CorrectionForm({ queryId }) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState("");
  const [by, setBy] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      setSaved(
        await api.createCorrection({
          query_id: queryId,
          corrected_answer: answer,
          corrected_by: by,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <p className="sent-note">
        Correction #{saved.id} recorded against query #{queryId}. It is on the review queue.
      </p>
    );
  }

  if (!open) {
    return (
      <button className="btn-secondary" onClick={() => setOpen(true)}>
        This answer is wrong
      </button>
    );
  }

  return (
    <form className="correction-form" onSubmit={submit}>
      <h4>What should it have said?</h4>
      <textarea
        rows={3}
        value={answer}
        required
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="The corrected answer"
      />
      <div className="correction-actions">
        <input
          value={by}
          required
          onChange={(e) => setBy(e.target.value)}
          placeholder="Your name"
          aria-label="Your name"
        />
        <button className="btn" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save correction"}
        </button>
        <button className="btn-secondary" type="button" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
    </form>
  );
}
