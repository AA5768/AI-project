---
title: Tallgrass Semiconductor Kestrel-2 Evaluation Debrief
date: 2026-06-18
meeting_type: sales
project: Kestrel-2
attendees:
  - Victor Nwosu
  - Ryan Chen
  - Marcus Feld
  - Tomas Lindqvist
  - Aisha Bello
---

# Tallgrass Semiconductor Kestrel-2 Evaluation Debrief

Victor Nwosu: Two weeks on Tallgrass's floor in Penang with the Kestrel-2 evaluation unit. I will give you what they liked, what they did not, and what they asked for.

Victor Nwosu: What they liked. Per-site temperature accuracy. They ran a 4-site correlation at minus 40 and got site-to-site spread of 0.6 degrees. Their incumbent handler is around 2.4 degrees and their yield engineer has been fighting a site-correlated bin shift for a year. He was, and I am quoting the tone not the words, visibly happy.

Ryan Chen: That is the thing that wins the deal.

Victor Nwosu: They also liked throughput. We measured 7,850 units per hour on their device against our 8,000 target, and their incumbent does 6,400. Nobody complained about 7,850.

Marcus Feld: What did they not like?

Victor Nwosu: Three things. Changeover time, contactor life, and the purge air requirement, in that order of heat.

Victor Nwosu: Changeover. They timed us at 31 minutes with our engineer doing it. Our published specification is under 25 minutes. Their own operators, untrained, took 52.

Tomas Lindqvist: Thirty-one with the dry-break fitting installed?

Victor Nwosu: With the dry-break fitting. The auto-teach routine was not on the evaluation unit, which is most of the gap.

Tomas Lindqvist: Then 31 minus the four to five minutes of manual realignment is about 26, which is roughly where I said we would land. I would still not publish 25.

Marcus Feld: The datasheet says under 25 and I wrote it in April. I will change it to under 30 and I will stop letting a target become a published number.

Victor Nwosu: Contactor life is the one that could actually lose us the deal. Their requirement is 500,000 insertions before contactor replacement. Our qualified number is 250,000.

Tomas Lindqvist: Our 250,000 is the socket manufacturer's number, not ours. We buy the contactor.

Victor Nwosu: Tallgrass knows that. Their point is that their incumbent, with the same class of contactor, gets 480,000 because the handler's plunge force is better controlled. They think our plunge is overshooting.

Tomas Lindqvist: That is a testable claim and it might be right. Our plunge control is open loop against a spring, with a force sensor only on site one.

Marcus Feld: What would it take to instrument all four sites and close the loop?

Tomas Lindqvist: Force sensors on all four sites, about 700 dollars a site, and a control loop change from Dana. Six weeks and maybe 40,000 of engineering.

Ryan Chen: What is the deal worth?

Victor Nwosu: Their initial order would be four handlers, so about 1.4 million dollars, and Tallgrass runs about sixty handlers across two sites. It is a long-term account, not one order.

Marcus Feld: Then we do the work. But I am not committing 500,000 insertions to them before we have measured it.

Victor Nwosu: I did not commit anything. What I told them was that we would investigate plunge force control and come back with data in eight weeks.

Ryan Chen: That is the right answer and it also keeps us in the evaluation. Their decision date is the end of September.

Marcus Feld: Decision: we fund the four-site force sensing and closed-loop plunge control, target data back to Tallgrass by the middle of August. Tomas owns the hardware, Dana owns the control loop. Victor sets the customer expectation at data, not a number.

Tomas Lindqvist: I will have the sensor bracket design done in two weeks so purchasing can order.

Victor Nwosu: Third item, purge air. We ship the membrane dryer in the machine, which was the right call, because their house clean dry air measures minus 38 degrees dew point and our machine did not care.

Aisha Bello: What does the dryer do to the service model? That is a consumable.

Victor Nwosu: Membrane cartridge is a two-year replacement, about 1,100 dollars. It should be on the preventive maintenance schedule and it is not, because the schedule was written before the dryer existed.

Aisha Bello: Then I have a gap in the service documentation on a machine we are trying to sell. I will get the PM schedule updated. Who signs off on it?

Tomas Lindqvist: Send it to me, I will review it.

Aisha Bello: I will have a revised Kestrel-2 preventive maintenance schedule to Tomas by the end of the month.
