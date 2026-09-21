# Frontend — Meridian Microsystems Knowledge System

React + Vite, plain `fetch` against the Part 2 API. No state library: every
screen owns one request, so there is nothing to synchronize between them.

```bash
npm install
npm run dev        # http://localhost:5173
```

The API must be running at `http://localhost:8000` (see the root README).
Override with `VITE_API_BASE_URL` if it is somewhere else — note the backend's
CORS allowlist is `http://localhost:5173`, so a different frontend port needs a
matching change in [`backend/app/main.py`](../backend/app/main.py).

## Screens

| Screen | What it is |
|---|---|
| **Ask** | Question → answer rendered claim by claim, each with the citation markers for *that* sentence; metadata badges; a click-through source drawer; the routing card on the low-confidence path; a correction affordance on an answered query |
| **Review queue** | Gaps and corrections as a triage list, filterable by status, with resolve/reopen |
| **Measurement** | The first-30-days metric with its live value from `GET /metrics` |

## Structure

```
src/api/client.js          the only module that knows the API exists
src/pages/                 one file per screen
src/components/            AnswerCard, RoutingCard, SourceDrawer, CorrectionForm, ui primitives
src/index.css              design tokens (light/dark)
src/App.css                component styles
```

## Notes

- **One response, two branches.** `POST /query` returns either an answer with
  citations or a `routing` object; the page renders whichever came back rather
  than deciding for itself. Both branches show the retrieved sources, because a
  reviewer judging a routing decision needs the evidence it was made on.
- **Citations resolve.** Every marker and citation row opens
  `GET /documents/{id}` and scrolls to the cited chunk, so provenance is
  checkable in the UI, not just asserted in the response.
- **Sending is simulated, addressing is not.** `POST /routing/send` logs
  instead of emailing, but an unknown recipient is a 404 and surfaces as an
  error on the card.
