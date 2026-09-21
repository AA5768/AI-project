---
title: Kestrel-2 Plunge Force Data Review
date: 2026-08-20
meeting_type: engineering
project: Kestrel-2
attendees:
  - Tomas Lindqvist
  - Dana Okafor
  - Victor Nwosu
  - Marcus Feld
  - Claire Dubois
---

# Kestrel-2 Plunge Force Data Review

Tomas Lindqvist: We promised Tallgrass contactor life data by the middle of August. We are five days late and we have the data. Dana has the measurement.

Dana Okafor: Four sites instrumented with force sensors, 20,000 insertions logged per site, open loop first and then closed loop.

Dana Okafor: Open loop, which is what shipped on the evaluation unit, the peak plunge force per site is between 41 and 58 newtons against a target of 45. Site three is the bad one at 58. The overshoot is about 12 newtons on first contact and it rings for roughly 40 milliseconds before it settles.

Victor Nwosu: So Tallgrass was right.

Dana Okafor: Tallgrass was right. Their claim was that our plunge overshoots and it does, by up to 29 percent on the worst site.

Tomas Lindqvist: The cause is that we control position and let a spring set the force. Any variation in the socket stack-up becomes a force variation, and site three has the tallest stack-up.

Dana Okafor: Closed loop, with the force sensors in the loop, peak force is between 44.2 and 46.1 newtons across all four sites and the overshoot is under 2 newtons.

Marcus Feld: What does that do to contactor life?

Dana Okafor: I cannot answer that from 20,000 insertions. Contactor wear is a long-tail mechanism and the honest statement is that we have removed the overstress condition, not that we have measured the life.

Tomas Lindqvist: The socket manufacturer publishes a life curve against peak force. At 58 newtons their curve says roughly 240,000 insertions. At 46 it says 520,000.

Marcus Feld: So we can say we meet 500,000 by reference to the supplier's curve.

Claire Dubois: We can say the supplier's published curve indicates 520,000 at our measured force. That is a different sentence and it is the one I will sign.

Victor Nwosu: That sentence is fine for Tallgrass. What they wanted was evidence that we understood the mechanism, and a force trace across four sites before and after is exactly that.

Marcus Feld: Is there a real life test we can start?

Dana Okafor: Yes. A continuous insertion test to 500,000 on one site is about six weeks of machine time, unattended overnight. I would start it now and report at the end of the quarter, after Tallgrass has already decided.

Marcus Feld: Start it anyway. If we win the deal we will need it for the next customer, and if we lose it we will need it more.

Tomas Lindqvist: I will start the 500,000 insertion life test on the engineering handler this week.

Victor Nwosu: What do I send Tallgrass and when?

Dana Okafor: I will have a short data package written by Monday. Force traces per site, before and after, the control change description, and Claire's sentence about the supplier curve.

Victor Nwosu: Then I will get on a call with their engineering manager on Tuesday and walk it through rather than emailing a PDF into silence.

Marcus Feld: Decision: closed-loop plunge control becomes standard on all Kestrel-2 machines, not an option, and the four force sensors go into the base bill of materials.

Tomas Lindqvist: That is 2,800 dollars a machine. Owen will notice.

Marcus Feld: Owen can notice. It is 2,800 dollars against a 340,000 dollar machine and it is the difference between a 250,000 and a 500,000 insertion claim.

Claire Dubois: One quality note. A force sensor in a safety-adjacent motion path needs a defined failure behaviour. If a sensor fails open, what does the plunge do?

Dana Okafor: Right now it would read zero and the loop would drive to maximum. That is a real problem and I am glad you asked before we shipped it.

Claire Dubois: That is exactly the kind of thing I am for.

Dana Okafor: I will add sensor plausibility checking and a fail-safe that reverts to the position-controlled profile with a fault flag. Two weeks, and it goes in before the first production machine.
