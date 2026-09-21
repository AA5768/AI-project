---
title: Vantage EU Region Incident Postmortem
date: 2026-05-20
meeting_type: engineering
project: Vantage 4.0
attendees:
  - Hassan Idris
  - Elena Vasquez
  - Aisha Bello
  - Marcus Feld
---

# Vantage EU Region Incident Postmortem

Hassan Idris: Postmortem for the EU region outage on the nineteenth of May. Blameless, as always, and I wrote the timeline before this meeting so we are not reconstructing it from memory in the room.

Hassan Idris: Timeline. At 09:14 UTC a scheduled database maintenance task began a schema migration on the telemetry store. The migration took an exclusive lock on the equipment_state table for what we expected to be under ten seconds. It held it for 47 minutes because the table had grown to 1.9 billion rows and the migration was written against a test database with 40 million.

Elena Vasquez: So every dashboard query in the region blocked.

Hassan Idris: Every query that touched equipment state, which is essentially all of them. Ingest kept working, so no customer telemetry was lost. Dashboards, alerts, and the API returned timeouts for 47 minutes.

Aisha Bello: Eleven customers in the EU region. Four opened tickets during the window, one of them a fab with a shift change at that hour who thought their tools had gone offline.

Marcus Feld: Did anyone make a decision based on our being down?

Aisha Bello: No. The fab that called checked their own MES and saw the tools were fine. But it cost their shift lead twenty minutes at the worst possible time.

Hassan Idris: Our SLA in the EU is 99.5 percent monthly. This incident alone puts May at 99.2, so we have a contractual credit obligation to the two accounts that have credits in their agreement.

Aisha Bello: What is the credit?

Elena Vasquez: Five percent of the monthly fee for each. About 3,400 dollars total.

Marcus Feld: Pay it without being asked. A credit a customer has to chase is worse than no credit.

Aisha Bello: Agreed, and I would rather send it with the postmortem than after they ask for one.

Hassan Idris: Root cause and contributing factors. Root cause is that the migration was validated against a test database that is two orders of magnitude smaller than production. Contributing factor one, the migration had no lock timeout, so it waited rather than failing fast. Contributing factor two, we run scheduled maintenance at 09:14 UTC, which is mid-morning in Europe, because the schedule was written when all our customers were in North America.

Elena Vasquez: That third one is embarrassing and it is a one-line fix.

Hassan Idris: It is. Four actions. One, every migration gets a lock timeout and fails rather than blocks. Two, migrations are validated against a production-scale snapshot, which means we need to build one, which is the expensive action. Three, regional maintenance windows follow the region's local night. Four, we add a dashboard health check that alerts us before a customer does, because on the nineteenth we learned about it from a customer ticket at 09:26, twelve minutes in.

Marcus Feld: Which of those makes the 4.0 release?

Hassan Idris: One, three, and four are done this week, they are hours of work each. Two is a week and a half and it needs storage that costs about 900 dollars a month.

Elena Vasquez: Approve it. The whole incident is a test-data problem and we are proposing to not fix the test-data problem because it costs 900 dollars a month.

Marcus Feld: Approved. Hassan, when does the production-scale snapshot exist?

Hassan Idris: I will have the production-scale snapshot environment in place by the fifth of June, and after that no migration ships without running against it.

Aisha Bello: Can I send the customer-facing postmortem before the actions are complete?

Hassan Idris: Yes. Send it with the actions and the dates. I will give you the text today and I would rather it went out within 72 hours of the incident than be perfect.

Aisha Bello: I will send the customer postmortem and the credits tomorrow.
