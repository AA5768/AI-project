---
title: Vantage 4.0 Scoping
date: 2026-02-05
meeting_type: product
project: Vantage 4.0
attendees:
  - Marcus Feld
  - Elena Vasquez
  - Hassan Idris
  - Victor Nwosu
  - Aisha Bello
  - Priya Raman
---

# Vantage 4.0 Scoping

Marcus Feld: The point of this meeting is to leave with a 4.0 scope we can actually build by September. Elena has a candidate list.

Elena Vasquez: Four things on the list. One, full EDA compliance, which means Interface A with E120 common equipment model, E125 equipment self-description, E134 data collection management, and E164 common metadata. Two, alarm handling that survives a real fab. Three, on-premises deployment for customers who will not put equipment telemetry in a cloud. Four, federated dashboards across multiple fabs for the big accounts.

Victor Nwosu: E164 is the one that keeps costing me deals. Two of the three fabs I have been in this quarter put E164 conformance in the purchase specification. If we are not conformant, our data plugs into their analytics stack as a custom integration and we get priced like a custom integration.

Marcus Feld: How much work is E164 on top of what 3.6 already does?

Elena Vasquez: We already emit E120 and E125. E164 is mostly constraining what we emit so the metadata is predictable rather than adding new data. Engineering estimated seven weeks.

Hassan Idris: Seven weeks of engineering and then a conformance test cycle. The E164 checker is unforgiving about naming and about how you model equipment hierarchy. I would budget two more weeks for the second and third pass through the checker.

Marcus Feld: So nine weeks. That fits. What about alarms?

Hassan Idris: Alarms are not a feature request, they are an outage waiting to happen. Last month a customer's deposition tool produced roughly 10,000 alarm events per minute for eleven minutes during a maintenance event. Our ingest pipeline accepted all of it, the dashboard queries timed out, and every other tool on that account went dark on our UI for the duration.

Aisha Bello: I had to explain that to the customer and I did not have a good explanation. From their side it looked like our product fell over because their tool had a bad day.

Hassan Idris: It did. We need deduplication at the edge agent, a rate limit per equipment, and a visible indication that we are shedding rather than silently dropping.

Elena Vasquez: That is about four weeks.

Marcus Feld: In. Alarm handling is in 4.0. On-premises deployment?

Elena Vasquez: On-prem is the expensive one. It is not just packaging. It is an installer, an upgrade path, a licence mechanism, and a support model for a version of our software we cannot see. Rough estimate is ten to twelve weeks and it touches every team.

Aisha Bello: How many customers actually need it?

Victor Nwosu: Two ask for it in every conversation. Verdant Power Semi will not sign a cloud deal at all, their security policy forbids it. Northgate would take cloud for the pilot and wants on-prem for production.

Priya Raman: I will say the uncomfortable thing. If we take on-prem and E164 and alarms in the same release, we will ship none of them well in September, and my team is also carrying Helios-3 through its first customer ship in the same month.

Marcus Feld: Agreed. Here is the decision. Vantage 4.0 scope is E164 conformance and alarm handling, plus the OEE calculation rework that Elena already has in flight. On-premises deployment moves to 4.1 and federated dashboards move behind it.

Elena Vasquez: I will update the roadmap deck and reissue it.

Victor Nwosu: I need something to say to Verdant that is not "later in the year".

Marcus Feld: Say 4.1, first half of 2027, and do not let anyone write a date on it in a contract before we have a plan. If they need a commitment sooner, bring it to me and we will decide with our eyes open.

Aisha Bello: What is the OEE rework, for those of us who will support it?

Elena Vasquez: Today we compute availability, performance, and quality in a way that is close to SEMI E10 but not actually E10. Different customers reconcile our number against their own MES and get different answers, and every one of those becomes a support ticket. We are moving to strict E10 state definitions and publishing how each number is derived, so a disagreement becomes checkable instead of a debate.

Aisha Bello: That will change the numbers customers are currently looking at.

Elena Vasquez: It will. Some accounts will see availability drop two or three points on the same equipment, because we were counting engineering time as productive.

Aisha Bello: Then I need six weeks of notice and a one-page explanation per account before it goes live. I am not having a customer discover that in a dashboard.

Elena Vasquez: Fair. I will write the note and give it to you before we cut the release candidate.

Marcus Feld: Target date for 4.0 general availability is the middle of September. Elena owns the scope document, Hassan owns the alarm design, and we review again at the end of April on EDA progress.
