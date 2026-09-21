---
title: Helios-3 End Effector Design Review
date: 2026-03-04
meeting_type: engineering
project: Helios-3
attendees:
  - Tomas Lindqvist
  - Ingrid Lund
  - Dana Okafor
  - Priya Raman
  - Claire Dubois
  - Nadia Haddad
---

# Helios-3 End Effector Design Review

Tomas Lindqvist: Three end-effector candidates. A Bernoulli non-contact head, a vacuum paddle, and a passive ceramic edge-grip blade. I will take the particle and slip data in that order.

Priya Raman: Headline first.

Tomas Lindqvist: The headline is that edge grip is the only one that meets three adders per pass on both sides, and it is also the most expensive and the hardest to source.

Ingrid Lund: Let me give the numbers, because the ranking is not close. Vacuum paddle averages 14 backside adders at 0.05 micrometres per pass. That is contact on the backside with an elastomer, so it is exactly what you would expect. Bernoulli is clean on contact, roughly two adders, but it moves a lot of air across the wafer surface and it drags whatever is in the EFEM onto the front side. In our box we measured nine front-side adders at 0.05.

Dana Okafor: Bernoulli also has a control problem. The wafer floats, and on a fast rotate the wafer walks on the cushion. We see up to 400 micrometres of positional drift at full speed, which we then have to correct at the aligner, and the correction costs throughput.

Tomas Lindqvist: Edge grip measured 1.8 adders per pass averaged over 50 passes, both sides, and there is no drift because the wafer is mechanically captured.

Priya Raman: So it is edge grip. What is the catch?

Tomas Lindqvist: The blade is alumina ceramic with a machined chamfer on the contact pads, from Cerapoint Ceramics. It is 3.8 times the cost of the vacuum paddle and Cerapoint is the only supplier we have qualified. Quoted lead time is thirteen weeks.

Nadia Haddad: Thirteen weeks on a single-source part on a programme that already has a sixteen-week harmonic drive. I want to say this plainly: we are building a bill of materials out of long-lead single-source components, and that is how programmes die.

Priya Raman: What can you do about it?

Nadia Haddad: For the ceramic specifically, not much this year. There are maybe three shops in the world that machine that chamfer to the tolerance Tomas needs. What I can do is negotiate buffer stock so we hold eight weeks of blades on our floor, and start a second-source qualification for the 2027 build.

Yuki is not in this meeting, but buffer stock is working capital and she will want to see the number.

Priya Raman: Take the buffer stock proposal to Yuki with a number attached. Decision for today: Helios-3 uses the Cerapoint alumina edge-grip blade. Tomas, freeze the end-effector design and update the design document.

Tomas Lindqvist: I will update the end-effector design document this week and issue it for review.

Claire Dubois: Does the edge-grip change affect the wafer-retention case for S2?

Tomas Lindqvist: It improves it. Mechanical capture means the wafer stays put on a power loss, where a vacuum paddle drops it. That is a better story.

Claire Dubois: Better, but it invalidates the retention test data I already have, which was taken on the vacuum paddle. I need to rerun the wafer-retention and emergency-stop drop tests with the ceramic blade. Three weeks of lab time and the lab is booked out.

Priya Raman: Book it now.

Claire Dubois: Booking today. I will confirm the slot by Friday.

Ingrid Lund: One condition on my sign-off. The chamfer geometry is what makes the particle number, and it is a machined feature on a brittle material. If a batch comes in with the chamfer out of tolerance, the blade still looks fine and still picks wafers, and we will not know until we see adders on a customer's wafer.

Nadia Haddad: Cerapoint provides a certificate of conformance per lot.

Ingrid Lund: A certificate is a piece of paper. I want incoming dimensional inspection on the chamfer, on every blade, at least until we have three good lots.

Nadia Haddad: That is a metrology cost and a receiving-inspection cost on every unit. I would rather do first-article inspection per lot.

Priya Raman: Ingrid, is per-lot first article enough?

Ingrid Lund: It is not what I would choose. I will accept it if we also hold a retained sample from each lot so that when something goes wrong we can go back and measure what we actually received.

Priya Raman: Do that. Per-lot first article plus retained samples. Nadia, write it into the purchase specification.

Nadia Haddad: I will add it to the Cerapoint purchase specification before we place the production order.

Dana Okafor: Last item from me and it is the one I flagged in January. With the ceramic blade the arm is stiffer and lighter, which means the position loop sees sharper transients on the settle. At one kilohertz we overshoot by about 60 micrometres and then settle. It is inside the plus or minus 25 micrometre repeatability spec at the handoff because we wait for settle, but waiting costs us throughput.

Priya Raman: Is one kilohertz unsafe or just slower?

Dana Okafor: Slower. Nothing about it is unsafe and nothing about it damages a wafer. It costs us somewhere between 20 and 40 wafers per hour.

Priya Raman: Then the board spin is deferred to Rev B and Helios-3 ships on the one kilohertz controller. Log it as a known limitation against the throughput spec.

Dana Okafor: I will log it. I disagree mildly, because I think we will find out in June that those 40 wafers per hour were the difference between meeting 450 and not.

Priya Raman: Then bring me the June measurement and we will revisit with data.
