---
title: Northgate Micro Particle Excursion — Escalation Bridge
date: 2026-04-09
meeting_type: escalation
project: Northgate Micro
attendees:
  - Aisha Bello
  - Ingrid Lund
  - Tomas Lindqvist
  - Victor Nwosu
  - Ryan Chen
  - Priya Raman
  - Marcus Feld
---

# Northgate Micro Particle Excursion — Escalation Bridge

Aisha Bello: This is the escalation bridge for Northgate Micro. Their Helios-3 pilot handler is down and has been since Tuesday morning. I will state the facts and then we work the problem.

Aisha Bello: Northgate's metrology caught a particle excursion on Tuesday. Wafers coming out of the thin-film module were showing an average of 22 adders at 0.05 micrometres on the backside against their limit of 5. They traced it to our handler by running a send-ahead wafer through the handler with no process step, and it picked up 19 adders on the pass.

Priya Raman: So it is us. Say that out loud so nobody wastes a day being defensive.

Aisha Bello: It is us, on the evidence we have. They have three lots on hold, 75 wafers, and the tool has been down four days.

Ryan Chen: I need to add the commercial context. This is the pilot tool that decides whether we get the production order for eleven more. Their director of equipment engineering used the phrase "supplier review" on the call this morning.

Ingrid Lund: I want the data before I speculate. What did they measure, with what, and on which side?

Victor Nwosu: I was on site yesterday. Their metrology is a surfscan, 0.05 micrometre threshold, both sides measured, and the adders are overwhelmingly backside. Front side is within limit at two to three adders.

Ingrid Lund: Backside-dominant points at the end effector, because that is the only thing touching the backside. Front side clean tells me the airflow in the box is probably fine.

Tomas Lindqvist: We qualified the ceramic blade at 1.8 adders per pass both sides. Something changed between our lab and their floor.

Ingrid Lund: Or something changed between the blade we qualified and the blade in that machine. Which lot is in the pilot tool?

Tomas Lindqvist: I will have to check the build record.

Ingrid Lund: Check it today. If it is not from the lot I qualified, that is where I start.

Aisha Bello: What can I tell Northgate in the next two hours?

Priya Raman: Tell them we accept it is our handler, we have an engineer on a plane tonight, and we will have a preliminary root cause within five working days and an 8D report within three weeks. Do not tell them a cause. We do not have one.

Aisha Bello: Who is on the plane?

Ingrid Lund: Me. I need to measure it myself on their floor and I need to bring a retained blade from our lot and swap it, because that is the fastest experiment that tells us something.

Priya Raman: Go. Victor, you are already cleared for site access, so you meet Ingrid there.

Victor Nwosu: I will be there Friday morning.

Marcus Feld: Are we exposed on the other pilot accounts? Cobalt has not installed yet but they are watching.

Aisha Bello: Cobalt has not installed. Tallgrass is Kestrel, different machine, not affected.

Priya Raman: Ingrid, what else could produce backside adders even if the blade is fine? I do not want a single-hypothesis investigation.

Ingrid Lund: Three other candidates. Wear debris from the Z-axis bellows falling onto the blade when the arm is parked low. A filter bypass in the EFEM top plate, which would be front side mostly but can recirculate. And the customer's own load port, which we did not build. I will rule them in or out with a sequence of send-ahead wafers, each one isolating a stage.

Ryan Chen: What do we say about the wafers on hold? Those are real dollars for them.

Priya Raman: We say nothing about compensation today. Once we have root cause we will make a proposal, and I would rather make a generous one late than a cheap one now.

Ryan Chen: They will ask.

Aisha Bello: They will, and I will hold the line, but I want to know internally what the range is so I am not surprised.

Priya Raman: Yuki and I will put a range together this week. Ryan, do not commit a number.

Aisha Bello: Daily bridge at eight in the morning Pacific until the tool is back up. I will send the invite after this call and I will write the customer update within the hour.
