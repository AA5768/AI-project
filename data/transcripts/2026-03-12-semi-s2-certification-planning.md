---
title: SEMI S2 Certification Planning
date: 2026-03-12
meeting_type: quality
project: Helios-3
attendees:
  - Claire Dubois
  - Tomas Lindqvist
  - Dana Okafor
  - Greg Salinas
  - Priya Raman
---

# SEMI S2 Certification Planning

Claire Dubois: I want to leave this meeting with a certification plan that has dates on it, because the S2 report is a deliverable in the Northgate acceptance package and right now it exists only in my head.

Priya Raman: Go.

Claire Dubois: SEMI S2 is an environmental, health and safety evaluation against about twenty sections. The ones that will cost us effort on Helios-3 are the risk assessment, hazardous energy isolation, ergonomics, and the seismic section. S8 is ergonomics specifically and we do it in the same pass. Then CE marking for Europe reuses most of the same file.

Tomas Lindqvist: Which of those do you expect to fail on the first pass?

Claire Dubois: Hazardous energy isolation. Today the EFEM has one main disconnect and the vacuum generator has its own supply that is not covered by it. An auditor will find that in ten minutes.

Tomas Lindqvist: That is a real finding. I will add a lockable isolation point for the vacuum supply in the next mechanical revision.

Claire Dubois: Second one is the light curtain muting during teach mode. Right now when an engineer enters teach mode the interlocks are bypassed entirely and the arm can move at full speed. Under S2 that has to be reduced speed with a hold-to-run device.

Dana Okafor: Reduced speed in teach is in the motion controller already, it is just not enforced. I can make it mandatory in firmware. The hold-to-run pendant is hardware we do not have.

Priya Raman: What does the pendant cost us in schedule?

Dana Okafor: The pendant is a catalogue part, maybe 900 dollars. The work is the safety-rated input path into the controller, which is about three weeks.

Priya Raman: Do it. Dana owns the reduced-speed teach mode and the hold-to-run input, three weeks.

Dana Okafor: Taking it.

Claire Dubois: Third area is documentation, and this is the one that always slips. S2 wants a hazard analysis, a manual with specific warnings, a decommissioning plan, and material declarations for every chemical and every substance in the machine. That last one means chasing every supplier for a declaration.

Greg Salinas: How many suppliers?

Claire Dubois: For a first build, around 40 that matter. Adhesives, lubricants, cable jacketing, the ceramic, the elastomer seals.

Greg Salinas: My receiving team can chase declarations, but not while also building the first production-intent machine in June. Pick one.

Priya Raman: Nadia's team owns supplier communication anyway. Claire, send Nadia the declaration list and have her team collect them. Greg's people build machines.

Claire Dubois: I will send the list to Nadia by Monday.

Tomas Lindqvist: What is the actual evaluation schedule?

Claire Dubois: The evaluation needs a build-representative machine. If the production-intent EFEM is in the cleanroom on the thirtieth of June, I run the on-tool evaluation through July, the third-party assessor comes the second week of August, and the report is signed by the end of August. That assumes no major findings.

Priya Raman: And with a major finding?

Claire Dubois: A major finding means a design change, a rebuild of the affected subsystem, and a re-evaluation of that section. Add three to five weeks.

Priya Raman: Which is exactly the September ship date, gone. Claire, do a paper pre-assessment against the S2 checklist in April, before the build, so that the findings we can predict are fixed in the drawing and not in the machine.

Claire Dubois: That is what I wanted to be asked for. I will run a paper pre-assessment and circulate findings by the seventeenth of April.

Priya Raman: Decision: we fund the paper pre-assessment in April and we hold the third-party assessor slot for the second week of August now, even though the machine does not exist yet.

Claire Dubois: Assessor slots book eight weeks out, so holding it now costs us a deposit of about 4,000 dollars that we lose if we move.

Priya Raman: Pay the deposit. The alternative is finding out in July that nobody is available until October.
