---
title: Kestrel-2 Thermal Architecture Review
date: 2026-02-19
meeting_type: engineering
project: Kestrel-2
attendees:
  - Tomas Lindqvist
  - Dana Okafor
  - Victor Nwosu
  - Claire Dubois
  - Priya Raman
  - Greg Salinas
---

# Kestrel-2 Thermal Architecture Review

Tomas Lindqvist: Kestrel-2 is the tri-temperature handler that docks to a customer's tester for back-end device test. Today is the thermal architecture, which is the part that decides whether the rest of the machine is easy or impossible.

Victor Nwosu: For context from the field, the requirement I keep hearing is minus 45 to plus 150 degrees Celsius at the device, soak to within two degrees in under six minutes, and 8,000 units per hour in a four-site configuration.

Dana Okafor: Those three numbers fight each other. Fast soak wants high thermal mass in the chuck. High throughput wants low thermal mass so you can index quickly. We are choosing where on that curve to sit.

Tomas Lindqvist: Two candidate architectures. One is a soak chamber with a conveyor and a separate contact chuck at the test site. Two is an active thermal head that carries the temperature to the device at the point of contact, no soak chamber.

Priya Raman: Which one do our competitors ship?

Victor Nwosu: Both exist in the market. The active head wins on changeover and floor space, the soak chamber wins on cost and on very high site counts.

Dana Okafor: The active head also gives us a much better story on temperature accuracy per site, because each site controls itself. With a shared soak chamber, site four is always two degrees off site one and the customer's yield engineer notices.

Greg Salinas: What does the active head do to our build cost?

Tomas Lindqvist: Each thermal head is roughly 11,000 dollars in parts. Four sites is 44,000 dollars against about 18,000 for a soak chamber. So we are 26,000 dollars more expensive per machine on a machine we want to sell around 340,000.

Priya Raman: And the customer pays that back in changeover time?

Victor Nwosu: In changeover time and in floor space, which in an OSAT is genuinely expensive. Penang floor space is not free.

Priya Raman: Decision: Kestrel-2 uses the active thermal head architecture. The per-site temperature accuracy is the differentiator and I do not want to defend a shared soak chamber to a yield engineer.

Tomas Lindqvist: Then I will close the architecture and start the detailed design.

Claire Dubois: Before you close it. At minus 45 degrees with an active head you have a cold surface exposed to the room. That is condensation and ice, and ice is both a quality problem and a safety finding under S2 if it drips onto anything electrical.

Dana Okafor: We purge. Dry air at a dew point below minus 60 degrees, flooded over the site during cold test.

Claire Dubois: Does the customer have dry air at minus 60?

Victor Nwosu: Most OSATs have clean dry air at around minus 40. Minus 60 means we either put a dryer in the machine or we write a facility requirement that will lose us deals.

Dana Okafor: Then we put the dryer in the machine. A membrane dryer sized for four sites is about 6,000 dollars and it means the machine works on whatever air the customer has.

Greg Salinas: That is 6,000 more on a machine we just made 26,000 more expensive.

Priya Raman: Correct, and the alternative is a machine that ices up in a customer's cleanroom in Penang. We take the dryer. Dana, write the purge requirement into the thermal specification, including the interlock behaviour if the dew point sensor reads high.

Dana Okafor: I will have the thermal specification updated by the end of next week.

Claire Dubois: And I want the dew point interlock in the risk assessment as a safety interlock, not just a process interlock. That changes how it has to be implemented.

Dana Okafor: Understood. Safety-rated sensor and a hard stop, not a software warning.

Tomas Lindqvist: Last open item is the contactor. The customer changes sockets between device types and today that is the longest part of a changeover. Target is a 20 minute changeover kit.

Victor Nwosu: I will believe 20 minutes when I see it. The current generation is around 45 and every OSAT complains.

Tomas Lindqvist: Twenty is the target. I am not committing to it until we have a prototype kit, which is April.

Priya Raman: Then say target, not commitment, in anything that leaves the building. Victor, hold the line on that with customers.
