---
title: Helios-3 Throughput Checkpoint
date: 2026-06-04
meeting_type: engineering
project: Helios-3
attendees:
  - Tomas Lindqvist
  - Dana Okafor
  - Priya Raman
  - Marcus Feld
  - Ingrid Lund
  - Ryan Chen
---

# Helios-3 Throughput Checkpoint

Priya Raman: In March I said bring me the June measurement. This is it. Dana, numbers.

Dana Okafor: Measured on the engineering EFEM, two load ports, mapping enabled, 25 wafer lots, ceramic edge-grip blade, one kilohertz controller. Sustained throughput is 412 wafers per hour.

Marcus Feld: Against a committed 450.

Dana Okafor: Against a committed 450. And I want to be precise about the conditions, because the number moves. At reduced Z stroke, which means the load port and the aligner at similar heights, we measure 447. At full Z stroke, which is the configuration Northgate actually has, 412.

Tomas Lindqvist: Northgate's aligner sits 340 millimetres below their load port plane because of their module. So 412 is their number.

Priya Raman: Where do the 38 wafers go?

Dana Okafor: Twenty-two of them are settle time at the handoff, which is the controller bandwidth issue I raised in January and again in March. Eleven are the Z axis itself, which is a mechanical limit on acceleration because of the mass we are moving. Five are mapping, which we could speed up by sampling fewer points and I do not recommend it.

Ingrid Lund: I will state the obvious. Do not take acceleration up on the Z axis to buy throughput. Higher acceleration on the bellows is exactly what generates the wear debris we spent April chasing.

Dana Okafor: Agreed, and that is why I did not put it on the list as an option.

Marcus Feld: So the honest specification is 412 at full stroke.

Dana Okafor: The honest specification is 410 at full stroke, 445 at reduced stroke, with the Rev B controller taking full stroke to roughly 435. That is a model, not a measurement, because Rev B does not exist.

Priya Raman: Rev B was cut from the budget on the twenty-first of May with an explicit condition that it comes back if this number came in materially below 450. Here we are.

Marcus Feld: Is 412 materially below 450? It is eight percent.

Ryan Chen: It is material to Northgate because their module's cycle time is set by the handler. Their process engineer did the arithmetic in front of me in March and got 450 into a wafer starts number.

Priya Raman: Then the question is not whether we like 412, it is what we tell Northgate and when.

Ryan Chen: We tell them now, at 412, with the full stroke explanation, and we bring the Rev B plan as the path to 435. If they hear 412 from us in June they are annoyed. If they measure 412 themselves in October they are done with us.

Marcus Feld: I agree. I would rather renegotiate a specification than fail an acceptance test.

Priya Raman: Decision: we disclose 412 at full stroke to Northgate before the end of June, with a written specification change and the Rev B roadmap attached. Ryan owns the conversation, Marcus owns the specification change document.

Ryan Chen: I will set up the call for the week of the fifteenth.

Marcus Feld: I will have the specification change document drafted by the twelfth so Ryan is not carrying it verbally.

Priya Raman: On Rev B funding, I am going back to Yuki with this measurement, and I am going to ask for the 200,000 dollars to be restored in FY26 rather than FY27, because a board spin started in July is a board in customers' machines in Q1 and a board spin started in January is not.

Dana Okafor: If it is funded in July I can have Rev B silicon on the bench in September and a validated board in November.

Tomas Lindqvist: There is a second reason to start Rev B now that has nothing to do with throughput. Brunnen's last-time-buy letter for the encoder head arrived on the eleventh of May. We have until the end of November to place a final order. Rev B is where the replacement encoder goes.

Priya Raman: That did arrive then. It was a rumour in a standup note in May and nobody confirmed it.

Tomas Lindqvist: It arrived. I have the letter. I should have circulated it and I did not.

Priya Raman: Circulate it today, to me, Nadia, and Greg. And Nadia needs to size the last-time-buy quantity, which is a guess about 2027 volume that we should make deliberately rather than at the end of November.

Marcus Feld: Last question and then I will let people go. Does the 412 number change anything for Cobalt?

Ryan Chen: Cobalt's evaluation criteria are particles and footprint. They have never asked about throughput because their bottleneck is elsewhere. It changes nothing for them today.
