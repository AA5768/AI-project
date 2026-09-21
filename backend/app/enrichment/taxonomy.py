"""Controlled vocabularies for derived metadata.

Fixed enums rather than free text: the UI renders topic_domain and priority as
badges and the API filters on them, so a corpus where one document says
"eng" and the next says "Engineering" produces a broken filter. Edit this file
when the corpus in data/ introduces a genuinely new domain.
"""

TOPIC_DOMAINS: list[str] = [
    "wafer_handling_hardware",  # Helios-3 EFEM robot: arms, end effectors, particles
    "test_cell_handler",  # Kestrel-2 thermal test handler and ATE docking
    "equipment_software",  # Vantage: SECS/GEM, EDA, OEE telemetry
    "quality_certification",  # SEMI S2/S8, CE marking, RCA/8D reports
    "product_roadmap",
    "customer_escalation",
    "sales_pipeline",
    "operations_supply_chain",
    "finance_budget",
    "hiring_people",
    "other",
]

PRIORITIES: list[str] = ["high", "medium", "low", "unspecified"]

QUALITY_FLAGS: list[str] = [
    "stale",  # content is superseded or clearly out of date
    "contradictory",  # disagrees with something it references
    "sparse",  # too little content to answer anything
    "unattributed",  # no author/attendee recorded in the file
    "draft",  # explicitly marked draft/WIP/TBD
]

# Substring cues used only by the heuristic fallback (enrichment/heuristics.py).
DOMAIN_CUES: dict[str, tuple[str, ...]] = {
    "wafer_handling_hardware": (
        "wafer", "end effector", "efem", "foup", "load port", "aligner",
        "edge grip", "particle", "teach", "repeatability", "scara", "cleanroom",
        "servo", "harmonic drive", "encoder", "kinematic", "300mm", "300 mm",
    ),
    "test_cell_handler": (
        "handler", "ate", "tester", "socket", "contactor", "changeover kit",
        "tri-temp", "tri temp", "soak", "uph", "jam rate", "mtbi", "dut",
        "device under test", "plunge", "dry air", "condensation",
    ),
    "equipment_software": (
        "secs", "gem", "eda", "interface a", "e164", "e120", "oee", "telemetry",
        "edge agent", "dashboard", "saas", "api", "release", "deploy", "uptime",
        "latency", "sdk", "alarm flood",
    ),
    "quality_certification": (
        "semi s2", "semi s8", "ce mark", "risk assessment", "8d", "capa",
        "certification", "audit", "nonconformance", "iso 14644", "interlock",
    ),
    "product_roadmap": (
        "roadmap", "milestone", "epic", "backlog", "gtm", "launch", "scope",
        "quarter", "release plan", "prioriti",
    ),
    "customer_escalation": (
        "escalation", "outage", "sev1", "sev-1", "p0", "incident", "churn risk",
        "complaint", "rca", "root cause", "sla breach", "excursion", "tool down",
        "line down", "scrapped wafer",
    ),
    "sales_pipeline": (
        "pipeline", "quota", "deal", "prospect", "renewal", "acv", "arr",
        "discount", "proposal", "win rate",
    ),
    "operations_supply_chain": (
        "supplier", "lead time", "bom", "inventory", "logistics", "shipment",
        "vendor", "procurement", "factory", "yield", "allocation",
        "second source", "single source", "buffer stock",
    ),
    "finance_budget": (
        "budget", "capex", "opex", "forecast", "spend", "cost reduction",
        "margin", "burn", "headcount cost", "invoice",
    ),
    "hiring_people": (
        "hiring", "candidate", "interview", "req", "offer", "onboarding",
        "headcount", "recruit", "attrition", "performance review",
    ),
}

HIGH_PRIORITY_CUES = (
    "urgent", "blocker", "blocking", "critical", "p0", "sev1", "sev-1",
    "escalation", "slipping", "at risk", "immediately", "asap", "outage",
)
LOW_PRIORITY_CUES = ("fyi", "nice to have", "backlog", "someday", "low priority", "no action")
