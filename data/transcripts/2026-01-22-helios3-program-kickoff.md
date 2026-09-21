---
title: Helios-3 Program Kickoff
date: 2026-01-22
meeting_type: engineering
project: Helios-3
attendees:
  - Priya Raman
  - Marcus Feld
  - Tomas Lindqvist
  - Dana Okafor
  - Ingrid Lund
  - Claire Dubois
  - Nadia Haddad
  - Ryan Chen
---

# Helios-3 Program Kickoff

Priya Raman: This is the kickoff for Helios-3, our next-generation 300 millimetre atmospheric wafer handler and the EFEM it sits in. Marcus, give everyone the commercial frame before we go technical.

Marcus Feld: Two customers are waiting on this. Northgate Micro wants a pilot tool on their Chandler line for a thin-film module they are bringing up. Cobalt Foundry Group is evaluating us as a second EFEM supplier, and they will not even look at us without a qualified 300 millimetre handler. Northgate is the one with a date attached.

Ryan Chen: Northgate's date is the end of September. Their module install window is fixed by their fab calendar and if we miss it we wait for the next one, which is February 2027. That is the whole deal, not a phase of it.

Priya Raman: Understood. So the committed first customer ship is the thirtieth of September 2026. Tomas, walk us through the spec we are signing up to.

Tomas Lindqvist: Dual-arm SCARA on a vertical Z stage, atmospheric, edge-grip end effectors. Throughput target is 450 wafers per hour on a two-load-port configuration with mapping enabled. Teach repeatability plus or minus 25 micrometres at the load port and at the aligner. Mean cycles between interventions of 500,000.

Ingrid Lund: And the cleanliness number, which matters more than any of those to the customer. We are committing to three or fewer particle adders at 0.05 micrometres and above per wafer pass, measured on both sides.

Priya Raman: Is three adders achievable with the arm architecture as drawn?

Ingrid Lund: On the model, yes. In practice the risk is not the arm, it is the airflow in the EFEM box. Every cable carrier and every gap in the top plate is a place where the downflow breaks and you recirculate. I want to be in the mechanical design reviews from the start, not shown a finished box in July.

Tomas Lindqvist: You are invited to all of them. I will add you to the review series today.

Dana Okafor: On motion control. The servo loop on the prototype board runs the position loop at one kilohertz. For the settle times we need at 450 wafers per hour I would rather be at four kilohertz, which means a new controller board.

Priya Raman: Cost and schedule of the board spin?

Dana Okafor: Roughly nine weeks including fabrication and bring-up, and about 80,000 dollars of NRE. I am not asking for it today. I am telling you it is the thing I will come back and ask for in April.

Priya Raman: Noted, and I would rather hear it in January than in April. Claire, certification.

Claire Dubois: SEMI S2 and S8 for the tool, CE marking for the European customers, and Northgate will want the S2 report as part of their acceptance package. The thing people forget is that the S2 evaluation needs a build-representative machine, not a prototype. If the first production-intent build is in August, the report will not exist in September.

Priya Raman: Then the first production-intent build has to be earlier. Tomas, what is the earliest?

Tomas Lindqvist: If the end-effector decision lands in early March, I can have a production-intent EFEM in the cleanroom by the end of June.

Claire Dubois: End of June works. Eight weeks of evaluation and report writing puts the S2 report in late August. Tight but real.

Priya Raman: Then that is the plan of record. Production-intent build by 30 June, S2 report by end of August, ship 30 September.

Nadia Haddad: I want to flag the supply side now rather than in June. The harmonic drive reducers for the theta and R axes come from Kaneda Precision and they are quoting sixteen weeks. The linear encoder heads are Brunnen, eleven weeks, single source. If the design freezes in March I can place long-lead orders in March and land parts in July. If the design moves in April, we ship in December.

Priya Raman: Everyone hear that. Design freeze is March. Nadia, put the long-lead list in front of me as soon as Tomas has a bill of materials.

Nadia Haddad: I will have the long-lead list by the second week of February.

Marcus Feld: One scope question. Northgate has asked whether Helios-3 can report through Vantage on day one, so their engineers see the handler's health next to the rest of the tool.

Elena is not here, but the connectivity work is not free on our side either.

Priya Raman: Decision: Helios-3 ships with the standard SECS/GEM interface at first customer ship and the Vantage integration follows in a later release. I do not want the handler programme carrying the software programme's schedule risk.

Marcus Feld: I will write that into the customer-facing scope document and send it to Northgate this week.

Ryan Chen: They will push back. I will take the conversation.

Priya Raman: Take it. Last item, budget. Yuki has given the programme 3.6 million dollars of NRE for FY26. That number includes the tooling and the first two builds and does not include Dana's board spin. Let us get to the March freeze without spending it twice.
