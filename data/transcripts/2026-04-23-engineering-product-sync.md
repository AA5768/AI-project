---
title: Engineering and Product Sync
date: 2026-04-23
meeting_type: cross-functional
project: Portfolio
attendees:
  - Priya Raman
  - Marcus Feld
  - Elena Vasquez
  - Tomas Lindqvist
  - Dana Okafor
  - Aisha Bello
---

# Engineering and Product Sync

Marcus Feld: Standing cross-functional sync. Three topics: Helios-3 recovery after Northgate, Vantage 4.0 progress, and the Kestrel-2 changeover kit.

Priya Raman: Helios-3 first. The Northgate tool is back up and the 8D is in draft. What that cost us is two weeks of Ingrid and Tomas, which came out of the production-intent build.

Tomas Lindqvist: The thirtieth of June build date is now the seventh of July in my plan. That is a week, and Claire's S2 schedule has no week in it.

Marcus Feld: Does the ship date move?

Priya Raman: Not yet. A week of float existed and we just spent it. If anything else happens, the ship date moves and I will say so early rather than at the end of September.

Elena Vasquez: Vantage 4.0. E164 work is about 60 percent done. We passed the E120 and E125 sections of the conformance checker on the first attempt and we are failing E164 on equipment hierarchy naming, which is what Hassan predicted.

Marcus Feld: Recoverable by September?

Elena Vasquez: Yes. It is a rework of how we model a tool with multiple process modules, and it is about three weeks. The alarm work is done and in internal testing. The OEE rework is done and I have the per-account explanation notes drafted for Aisha.

Aisha Bello: I have them. I have sent two of the nine and I am pacing the rest so I am not having nine hard conversations in one week.

Marcus Feld: Which accounts will be unhappy?

Aisha Bello: Verdant Power Semi, because their availability number drops 3.1 points and their operations director reports that number upward. And Northgate, because they are already unhappy with us and this is one more thing.

Elena Vasquez: I can hold Northgate's account on the old calculation for one release cycle. It is a flag.

Priya Raman: Do not do that.

Elena Vasquez: Say more.

Priya Raman: Because a per-account flag on the number that our product exists to produce is how you end up with two products. And because the old number was wrong. We do not keep a customer on a wrong number to avoid a conversation.

Aisha Bello: I agree with Priya, but I want the conversation scheduled after the 8D closes, not before.

Elena Vasquez: That is a sequencing question, not a flag. I can live with that. Northgate gets the OEE change in the release, and Aisha picks the week she briefs them.

Marcus Feld: Agreed. Kestrel-2 changeover kit.

Tomas Lindqvist: Prototype kit is on the bench. Measured changeover on the bench is 38 minutes against a 20 minute target.

Marcus Feld: What is the 18 minutes?

Tomas Lindqvist: Eleven of it is the thermal head, because you have to break the coolant circuit and purge it before you can lift the head. Five is realignment of the contactor after the kit is seated. Two is miscellaneous.

Dana Okafor: The five minutes of realignment I can take out with an auto-teach routine using the existing camera. Maybe four weeks of work.

Tomas Lindqvist: The eleven minutes of coolant needs a quick-disconnect with a dry-break fitting, which is a mechanical change and about 1,800 dollars a machine.

Marcus Feld: So 20 minutes is reachable at 1,800 dollars and four weeks of Dana.

Tomas Lindqvist: Twenty-two, realistically. I would stop promising 20.

Marcus Feld: Then the datasheet says under 25 minutes and we are honest. Victor has been quoting 20 as a target and I would rather he quote something we beat.

Priya Raman: Decision: we fund the dry-break fitting and the auto-teach routine, and the published changeover specification is under 25 minutes. Marcus, fix the datasheet before the Tallgrass evaluation.

Marcus Feld: I will update the datasheet this week.

Aisha Bello: One item from support that nobody asked for. We have had four field calls in six weeks where the answer was in a document somebody wrote and nobody could find. The Northgate gasket geometry was in a design review from March that my team had no way to search.

Marcus Feld: That is a real cost and it is not on anyone's roadmap.

Priya Raman: Put it on mine as a discussion item for the Q3 planning session. Not a project yet.
