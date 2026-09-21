---
title: Vantage EDA Interface A Deep Dive
date: 2026-04-30
meeting_type: engineering
project: Vantage 4.0
attendees:
  - Elena Vasquez
  - Hassan Idris
  - Victor Nwosu
  - Marcus Feld
---

# Vantage EDA Interface A Deep Dive

Elena Vasquez: We are failing the E164 conformance checker on equipment hierarchy and I want to decide the model today, because every week we spend deciding is a week not spent implementing.

Hassan Idris: The failure is specific. E164 says the equipment model has to represent physical structure, and the checker walks the hierarchy expecting equipment, then subsystem, then module, with types from E120. We currently emit a flat list of data sources with names the customer chose.

Victor Nwosu: Which is how it grew. In 3.x a customer could name anything anything, and several of them have named things after the engineer who installed the tool.

Elena Vasquez: Three options. One, we generate the hierarchy automatically from the SECS/GEM equipment constants where the tool exposes them. Two, we ask the customer to map their structure once, in a wizard, at install. Three, we ship a library of pre-built models per tool type and the customer picks.

Hassan Idris: Option one works on maybe half of the installed base. The older tools do not expose enough to build a hierarchy from, and a wrong automatic hierarchy is worse than no hierarchy because it looks authoritative.

Victor Nwosu: Option three is attractive to a customer right up to the moment their tool is not in the library, and then it is worse than a wizard.

Elena Vasquez: So it is the wizard, with automatic pre-population where the tool exposes enough.

Hassan Idris: That is what I would build. Auto-populate, show the engineer what we inferred, make them confirm it, and store the confirmation with a timestamp and a user so we can tell later whether a model was inferred or asserted.

Marcus Feld: How long?

Hassan Idris: The inference and storage is two weeks. The wizard user interface is three. They overlap somewhat, so four weeks to a release candidate.

Elena Vasquez: That fits the September date with two weeks to spare, which we will spend on the conformance checker.

Marcus Feld: Decision made then. Wizard with auto-population, and we record whether the model was inferred or confirmed.

Victor Nwosu: There is a migration question. What happens to the existing installed base at upgrade? If a customer upgrades to 4.0 and their hierarchy is a flat list, do their dashboards break?

Hassan Idris: They do not break. The flat list keeps working, it is just not E164 conformant until they run the wizard. I would put a banner in the interface that says so.

Victor Nwosu: Then I need that stated clearly in the release notes, because a customer who bought on E164 conformance and then upgrades and finds they are not conformant until they do work will be annoyed.

Elena Vasquez: I will write it into the release notes and into the upgrade guide.

Marcus Feld: One more topic. E187 cybersecurity keeps coming up in fab purchase specifications. Where are we?

Hassan Idris: E187 is a baseline: supported operating systems, network security, endpoint protection, authentication. Our edge agent runs on Windows IoT and we currently ship it with a service account that has more privilege than it needs, and we do not enforce password rotation on the local admin.

Marcus Feld: Is that a 4.0 item or a 4.1 item?

Hassan Idris: The privilege reduction is a two-week item and it is embarrassing that it is not done. The rest is a programme.

Elena Vasquez: Take the two weeks in 4.0. I will not scope the rest until we have a customer requirement with a date on it.

Victor Nwosu: Cobalt's purchase specification has E187 in it. I will get you the exact clause so you are scoping against the real text and not against a summary.

Elena Vasquez: Send it this week and I will add it to the 4.1 planning input.
