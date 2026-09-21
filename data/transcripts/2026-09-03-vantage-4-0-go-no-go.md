---
title: Vantage 4.0 Release Go / No-Go
date: 2026-09-03
meeting_type: product
project: Vantage 4.0
attendees:
  - Elena Vasquez
  - Hassan Idris
  - Marcus Feld
  - Aisha Bello
  - Victor Nwosu
  - Priya Raman
---

# Vantage 4.0 Release Go / No-Go

Marcus Feld: Go or no-go on Vantage 4.0 general availability, target the fifteenth of September. Elena, state the release contents and the known issues, then we decide.

Elena Vasquez: Contents. E164 conformance including the equipment model wizard, alarm deduplication and rate limiting at the edge agent, the SEMI E10 OEE rework, and the edge agent privilege reduction for E187.

Elena Vasquez: Conformance status. We passed the full E164 checker on the twenty-eighth of August, third attempt. E120 and E125 passed in April and have not regressed.

Hassan Idris: Alarm handling has been running in production on three accounts under a feature flag since the twelfth of August, including the account that produced the 10,000 per minute flood in January. We replayed that flood against the new pipeline. Ingest held, dashboards stayed up, and we shed 94 percent of the duplicate events with a visible banner saying so.

Marcus Feld: Known issues.

Elena Vasquez: Two that matter. First, the equipment model wizard does not support tools with more than sixteen process modules. There is one customer in the installed base with a twenty-module tool and the wizard fails at module seventeen with an unhelpful error.

Victor Nwosu: That is Cobalt's cluster tool.

Elena Vasquez: It is. The fix is not hard, it is a fixed-size buffer, but it needs a full regression cycle and that is eight days we do not have before the fifteenth.

Aisha Bello: Does Cobalt have to run the wizard on day one?

Elena Vasquez: No. Their existing flat model keeps working. They are not E164 conformant until they run it.

Victor Nwosu: Cobalt's purchase specification cites E164. If they upgrade and cannot become conformant, that is a contractual conversation, not an inconvenience.

Marcus Feld: Then Cobalt does not get the upgrade offered on the fifteenth. We hold them until 4.0.1. Aisha, can support manage a held account?

Aisha Bello: Yes, as long as it is one account and it is written down. Two becomes a mess.

Elena Vasquez: Second known issue, and this one is a promise we are breaking rather than a bug. The on-premises installer is not in 4.0. It was moved to 4.1 in the February scoping decision, and the roadmap deck that went out in March still shows on-premises at 4.0 general availability.

Victor Nwosu: I have been telling Verdant Power Semi 4.1 since February because I was in the February meeting. But their procurement team has the March deck, and their procurement team is the one writing the purchase order.

Marcus Feld: That deck is mine and it is wrong. I will reissue it today with on-premises in 4.1 and a dated revision note, and Victor takes the corrected version to Verdant personally rather than emailing it.

Victor Nwosu: I will call them before the deck lands so it is not a surprise in an inbox.

Priya Raman: I want to name the pattern rather than just fix the instance. This is the second time in a month that a stale customer-facing document has contradicted a decision we actually made. The Helios status deck said Vantage integration was in the acceptance criteria when it never was, and now the roadmap deck promises on-premises in 4.0.

Marcus Feld: Both are mine and I own it. The underlying problem is that decisions live in meeting notes and documents live somewhere else, and nothing connects them.

Priya Raman: Which is the thing Aisha raised in April and I put on my list as a discussion item. It has now cost us twice.

Aisha Bello: Three times if you count the field calls where the answer existed and nobody could find it.

Priya Raman: Then it graduates from a discussion item. Marcus, put a proposal in front of me in Q4 for how we make decisions findable, with a cost.

Marcus Feld: I will bring a proposal to the Q4 planning session.

Marcus Feld: Back to the decision in front of us. Aisha, support readiness?

Aisha Bello: Ready. The OEE change notes have gone to all nine affected accounts, the last one on the twenty-seventh of August. Two accounts pushed back, both accepted the explanation once they saw the E10 state definitions written out.

Hassan Idris: Operations readiness. Rollback is tested. We can roll back the application in eleven minutes. The one thing we cannot roll back cleanly is an equipment model that a customer confirms through the new wizard, because the old version does not understand the hierarchy.

Marcus Feld: What happens if we roll back after a customer runs the wizard?

Hassan Idris: They fall back to their flat model. Nothing is lost, they just redo the wizard after we roll forward again. It is annoying, not dangerous.

Marcus Feld: Acceptable. Then it is go. Vantage 4.0 general availability on the fifteenth of September, Cobalt held until 4.0.1, the roadmap deck reissued today, and 4.0.1 targeted for the middle of October with the wizard module limit fixed.

Elena Vasquez: I will publish the release notes and the upgrade guide on the eleventh so customers have four days before the upgrade window opens.
