---
title: Northgate Micro Root Cause Review
date: 2026-04-16
meeting_type: escalation
project: Northgate Micro
attendees:
  - Ingrid Lund
  - Tomas Lindqvist
  - Nadia Haddad
  - Claire Dubois
  - Aisha Bello
  - Priya Raman
  - Greg Salinas
---

# Northgate Micro Root Cause Review

Ingrid Lund: I have been on Northgate's floor for five days. There are two causes, not one, and that is why the first day of testing was confusing.

Ingrid Lund: Cause one. The ceramic blade in that machine is from Cerapoint lot CP-220-0413. I measured the chamfer on the four contact pads with the retained sample from the same lot and it is out of specification on three of the four. The drawing calls for a 0.15 millimetre chamfer with a 0.4 micrometre surface finish. The retained sample measures between 0.08 and 0.11 millimetres with a finish around 1.6 micrometres. A rougher, sharper pad abrades the wafer edge exclusion zone and generates alumina debris, which then lands on the backside.

Tomas Lindqvist: That lot came in after we placed the production order, which means it came in after the purchase specification change we agreed in March.

Nadia Haddad: The purchase specification change was issued on the sixth of March. The first-article inspection requirement was in it. Cerapoint's certificate of conformance for lot 0413 says the first article passed.

Ingrid Lund: Their certificate says the first article passed. The retained sample from the same lot fails. Either they measured a different part or they measured it differently.

Priya Raman: That is a supplier quality problem and it is also our problem, because we accepted a certificate instead of measuring. Nadia, what is the corrective action?

Nadia Haddad: One hundred percent incoming dimensional inspection on the chamfer for the next three lots, then back to per-lot first article if all three are clean. And I will put a supplier corrective action request to Cerapoint asking how their first article passed.

Ingrid Lund: I want the retained sample programme formalised too. It is the only reason we solved this in five days instead of five weeks.

Priya Raman: Agreed. Both of those go in the 8D.

Ingrid Lund: Cause two, and this one is ours alone. The EFEM top plate has a gasket between the fan filter unit frame and the plate. On this machine the gasket is compressed unevenly at the rear left corner and there is a gap of roughly 1.5 millimetres over about 80 millimetres of length. Unfiltered air from above the plate is being pulled into the box. That contributes front-side adders, which were within limit but elevated, and it is why the box did not recover to baseline even after I swapped the blade.

Tomas Lindqvist: Is that a design problem or a build problem?

Ingrid Lund: Both. The gasket is the right material but the bolt pattern is too sparse at the corners, so a normal build variation opens a gap. I would add two fasteners per corner and I would add a smoke or particle check at the top plate as a build step.

Greg Salinas: Adding a leak check to the build adds about 40 minutes per machine. I can absorb that.

Priya Raman: Do it. Tomas, the fastener change goes into the next mechanical revision and into a field rework kit for the machines already built.

Tomas Lindqvist: How many machines already built?

Greg Salinas: Four. Northgate's pilot, two in our cleanroom, and one at Cobalt waiting for install.

Priya Raman: Then four rework kits. Tomas owns the kit definition, Greg owns the rework schedule.

Tomas Lindqvist: I will have the rework kit drawing and instructions by the twenty-fourth of April.

Aisha Bello: What is the recovery plan on Northgate's tool specifically? That is the question I get every morning at eight.

Ingrid Lund: I swapped in a blade from a good lot and reworked the gasket by hand on site. Send-ahead wafers now measure 2.1 adders backside and 1.9 front side, which is inside their limit and inside our spec. The tool is running as of yesterday afternoon.

Aisha Bello: Then I can close the daily bridge. I will move to a weekly update until the 8D is signed.

Claire Dubois: I need to say something about the wafers on hold. Northgate scrapped 31 wafers out of the 75 and reworked the rest. If we are going to talk about compensation, I do not want us paying for scrap that their own metrology says was recoverable.

Aisha Bello: They have given us the disposition data. Thirty-one scrapped, 44 reworked and passed.

Priya Raman: Yuki and I discussed the range. We are authorised to offer a 60,000 dollar service credit plus two additional preventive maintenance visits at no charge, and we are not offering wafer-value compensation, because their purchase terms cap our liability at the tool value and setting a precedent on wafer value would be a company-level decision, not an account decision.

Aisha Bello: I can work with that. I would like to lead with the two PM visits and the engineering changes, not with the money.

Priya Raman: Lead however you like, as long as the number does not move.

Claire Dubois: Last thing. This is a reportable nonconformance in our quality system and the 8D has to be signed by me before it goes to the customer. Who is writing it?

Ingrid Lund: I am writing D1 through D5. Nadia writes the supplier sections. Claire signs.

Claire Dubois: Then I need the draft by the twenty-fourth to have it to the customer by the thirtieth.
