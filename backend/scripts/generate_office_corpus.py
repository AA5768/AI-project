"""Authors data/office/* from source text held here.

Office files are binaries, so the corpus is generated rather than hand-committed:
this script is the reviewable form of those documents. Re-running it is
idempotent -- every file is rewritten from scratch.

The content deliberately varies in quality. Some documents are stale (a status
deck still showing a spec that a later meeting changed), some contradict a
transcript (the budget workbook still carries the pre-cut NRE line), one is an
unattributed scrap, one is an explicit draft full of TBDs. Part 2's gap,
correction and routing logic needs a corpus where the sources disagree, and a
corpus where everything agrees would make that logic untestable.

Usage:
    python -m scripts.generate_office_corpus            # from backend/
    python -m scripts.generate_office_corpus --out ../data/office
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from docx import Document as DocxDocument
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Inches

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "office"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _stamp(doc_props, author: str, title: str, when: datetime) -> None:
    doc_props.author = author
    doc_props.last_modified_by = author
    doc_props.title = title
    doc_props.created = when
    doc_props.modified = when


def _docx(path: Path, title: str, author: str, when: datetime, blocks: list) -> None:
    """blocks: ("h1"|"h2"|"p"|"bullet", text) or ("table", [[cells], ...])."""
    document = DocxDocument()
    document.styles["Normal"].font.size = Pt(11)

    for kind, payload in blocks:
        if kind == "h1":
            document.add_heading(payload, level=1)
        elif kind == "h2":
            document.add_heading(payload, level=2)
        elif kind == "bullet":
            document.add_paragraph(payload, style="List Bullet")
        elif kind == "table":
            table = document.add_table(rows=len(payload), cols=len(payload[0]))
            table.style = "Table Grid"
            for r, row in enumerate(payload):
                for c, value in enumerate(row):
                    table.cell(r, c).text = str(value)
        else:
            document.add_paragraph(payload)

    _stamp(document.core_properties, author, title, when)
    document.save(str(path))


def _pptx(path: Path, title: str, author: str, when: datetime, slides: list) -> None:
    """slides: (heading, [body lines], notes or None, table rows or None)."""
    prs = Presentation()
    title_layout = prs.slide_layouts[0]
    bullet_layout = prs.slide_layouts[1]
    blank_layout = prs.slide_layouts[5]

    for index, (heading, body, notes, table_rows) in enumerate(slides):
        layout = title_layout if index == 0 else (blank_layout if table_rows else bullet_layout)
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = heading

        if index == 0:
            slide.placeholders[1].text = "\n".join(body)
        elif table_rows:
            if body:
                box = slide.shapes.add_textbox(Inches(0.6), Inches(1.4), Inches(8.8), Inches(0.9))
                box.text_frame.text = "\n".join(body)
            rows, cols = len(table_rows), len(table_rows[0])
            top = Inches(2.4) if body else Inches(1.6)
            shape = slide.shapes.add_table(rows, cols, Inches(0.6), top, Inches(8.8), Inches(0.8))
            for r, row in enumerate(table_rows):
                for c, value in enumerate(row):
                    shape.table.cell(r, c).text = str(value)
        else:
            slide.placeholders[1].text = "\n".join(body)

        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    _stamp(prs.core_properties, author, title, when)
    prs.save(str(path))


def _xlsx(path: Path, title: str, author: str, when: datetime, sheets: list) -> None:
    """sheets: (sheet name, [[header], [row], ...])."""
    workbook = Workbook()
    workbook.remove(workbook.active)

    for name, rows in sheets:
        sheet = workbook.create_sheet(title=name)
        for row in rows:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for column_cells in sheet.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(max(width + 2, 10), 52)

    props = workbook.properties
    props.creator = author
    props.lastModifiedBy = author
    props.title = title
    props.created = when
    props.modified = when
    workbook.save(str(path))


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------


def helios3_status_deck(out: Path) -> None:
    """STALE ON PURPOSE.

    Issued in May. By August the throughput figure is wrong (412 wph measured on
    2026-06-04), the ship date is wrong (moved to 2026-11-14 on 2026-08-13) and
    slide 5 asserts a Vantage acceptance criterion that the kickoff explicitly
    excluded. Aisha Bello calls this deck out by name in the 13 August review.
    """
    _pptx(
        out / "helios3-program-status-2026-05.pptx",
        "Helios-3 Program Status — May 2026",
        "Marcus Feld",
        datetime(2026, 5, 12, 9, 30),
        [
            (
                "Helios-3 Program Status — May 2026",
                [
                    "Prepared by: Marcus Feld",
                    "Customer-facing status deck, issued 12 May 2026",
                    "Distribution: Northgate Micro equipment engineering",
                ],
                "Customer-facing. Do not include internal cost or supplier names.",
                None,
            ),
            (
                "Program Summary",
                [
                    "300 mm atmospheric wafer handler and EFEM",
                    "Design frozen March 2026; end effector is Cerapoint alumina edge grip",
                    "Production-intent build in cleanroom 30 June 2026",
                    "First customer ship 30 September 2026",
                ],
                None,
                None,
            ),
            (
                "Specification vs Plan of Record",
                [],
                "Throughput figure is the committed number from the January kickoff, not a "
                "measurement. Engineering measurement checkpoint is scheduled for June.",
                [
                    ["Parameter", "Committed", "Status"],
                    ["Throughput", "450 wafers/hour", "On plan"],
                    ["Particle adders (0.05 um, per pass)", "<= 3", "1.8 measured"],
                    ["Teach repeatability", "+/- 25 um", "Met"],
                    ["Mean cycles between interventions", "500,000", "Modelled"],
                    ["SEMI S2 / S8 report", "End August 2026", "On plan"],
                ],
            ),
            (
                "April Particle Excursion — Closed",
                [
                    "Backside particle excursion on the pilot tool, 7-15 April",
                    "Two causes: ceramic blade chamfer out of specification (supplier lot "
                    "CP-220-0413) and an EFEM top plate gasket gap",
                    "Corrective actions: 100% incoming chamfer inspection for three lots, "
                    "top plate fastener change, field rework kit for four machines",
                    "Tool returned to service 15 April at 2.1 backside adders per pass",
                ],
                "8D issued to the customer 30 April. Formal customer closure still pending as "
                "of this deck.",
                None,
            ),
            (
                "Acceptance Criteria",
                [
                    "Site acceptance test: 10 working days after install",
                    "Particle acceptance measured end to end across nine passes",
                    "SEMI S2 report included in the acceptance package",
                    "Vantage connectivity demonstrated as part of acceptance",
                ],
                "The Vantage line was added at the customer's request during the April "
                "escalation call.",
                None,
            ),
            (
                "Risks",
                [
                    "Kaneda harmonic drive reducers on allocation; expedite premium approved",
                    "Cerapoint ceramic blades single source, 13 week lead time",
                    "Certification schedule has no float after the build",
                ],
                None,
                None,
            ),
        ],
    )


def vantage_roadmap_deck(out: Path) -> None:
    """STALE ON PURPOSE: shows on-premises at 4.0 GA, which the 5 Feb scoping
    meeting moved to 4.1. Marcus Feld reissues this on 3 September."""
    _pptx(
        out / "vantage-roadmap-fy26.pptx",
        "Vantage Product Roadmap FY26",
        "Marcus Feld",
        datetime(2026, 3, 18, 14, 5),
        [
            (
                "Vantage Product Roadmap FY26",
                [
                    "Prepared by: Marcus Feld",
                    "Revision 2, 18 March 2026",
                    "For customer and prospect distribution",
                ],
                None,
                None,
            ),
            (
                "Vantage 4.0 — September 2026",
                [
                    "SEMI E164 EDA common metadata conformance",
                    "Alarm deduplication and rate limiting at the edge agent",
                    "SEMI E10 compliant OEE calculation",
                    "On-premises deployment option",
                ],
                "On-premises is shown at 4.0 in this revision. Confirm against the February "
                "scoping decision before the next reissue.",
                None,
            ),
            (
                "Vantage 4.1 — H1 2027",
                [
                    "Federated dashboards across multiple fabs",
                    "SEMI E187 cybersecurity baseline, full scope",
                    "Recipe and parameter drift analytics",
                ],
                None,
                None,
            ),
            (
                "Connectivity Coverage",
                [],
                None,
                [
                    ["Standard", "3.6", "4.0", "4.1"],
                    ["SECS/GEM 300", "Yes", "Yes", "Yes"],
                    ["E120 common equipment model", "Yes", "Yes", "Yes"],
                    ["E125 equipment self description", "Yes", "Yes", "Yes"],
                    ["E134 data collection management", "Partial", "Yes", "Yes"],
                    ["E164 common metadata", "No", "Yes", "Yes"],
                    ["E187 cybersecurity", "No", "Partial", "Yes"],
                ],
            ),
        ],
    )


def northgate_escalation_deck(out: Path) -> None:
    _pptx(
        out / "northgate-escalation-review.pptx",
        "Northgate Micro Escalation Review",
        "Aisha Bello",
        datetime(2026, 4, 24, 16, 45),
        [
            (
                "Northgate Micro Escalation Review",
                [
                    "Prepared by: Aisha Bello",
                    "Internal review, 24 April 2026",
                    "Escalation opened 7 April, tool recovered 15 April",
                ],
                None,
                None,
            ),
            (
                "Impact",
                [
                    "Pilot Helios-3 handler down four days",
                    "Three lots on hold, 75 wafers: 31 scrapped, 44 reworked and passed",
                    "Customer measured 22 backside adders at 0.05 um against a limit of 5",
                    "Production order for eleven EFEMs now contingent on a clean 90 day run",
                ],
                "Ryan Chen's probability on the production order moved from 85% to 60% after "
                "this escalation.",
                None,
            ),
            (
                "Response Timeline",
                [],
                None,
                [
                    ["Date", "Event"],
                    ["7 Apr", "Customer metrology flags excursion; tool down"],
                    ["9 Apr", "Escalation bridge opened; daily cadence agreed"],
                    ["10 Apr", "Contamination control engineer on site"],
                    ["13 Apr", "Blade swap and gasket rework performed on site"],
                    ["15 Apr", "Send-ahead wafers at 2.1 backside adders; tool released"],
                    ["16 Apr", "Root cause review; two causes confirmed"],
                    ["30 Apr", "8D report issued to customer"],
                ],
            ),
            (
                "Commercial Settlement",
                [
                    "USD 60,000 service credit",
                    "Two additional preventive maintenance visits at no charge",
                    "No wafer-value compensation offered; liability capped at tool value",
                ],
                "Authorised by Priya Raman and Yuki Tanaka. Account team instructed not to "
                "move the number.",
                None,
            ),
            (
                "What We Would Do Differently",
                [
                    "Measure incoming chamfer rather than accept a certificate of conformance",
                    "Retained samples per lot made the root cause findable in five days",
                    "Send an engineer on day one; the travel cost was trivial against the risk",
                ],
                None,
                None,
            ),
        ],
    )


def tallgrass_eval_deck(out: Path) -> None:
    _pptx(
        out / "kestrel2-tallgrass-eval-summary.pptx",
        "Kestrel-2 Tallgrass Evaluation Summary",
        "Victor Nwosu",
        datetime(2026, 6, 22, 11, 10),
        [
            (
                "Kestrel-2 Tallgrass Evaluation Summary",
                [
                    "Prepared by: Victor Nwosu",
                    "Two week evaluation, Tallgrass Semiconductor, Penang",
                    "Customer decision expected end of September 2026",
                ],
                None,
                None,
            ),
            (
                "Measured Results",
                [],
                "Throughput measured on the customer's own device, four sites, minus 40 C.",
                [
                    ["Metric", "Requirement", "Measured", "Incumbent"],
                    ["Site-to-site temperature spread", "< 1.5 C", "0.6 C", "2.4 C"],
                    ["Throughput (UPH)", "8,000", "7,850", "6,400"],
                    ["Changeover, trained engineer", "< 25 min (published)", "31 min", "45 min"],
                    ["Changeover, customer operator", "not specified", "52 min", "58 min"],
                    ["Contactor life (insertions)", "500,000", "250,000 qualified", "480,000"],
                ],
            ),
            (
                "Open Items",
                [
                    "Contactor life: customer believes our plunge force overshoots",
                    "Committed to return force data within eight weeks (mid August)",
                    "Published changeover specification to be corrected to under 30 minutes",
                    "Membrane dryer cartridge missing from the preventive maintenance schedule",
                ],
                "The changeover number on the datasheet was a target that became a published "
                "specification. Product owns the correction.",
                None,
            ),
        ],
    )


def end_effector_design_doc(out: Path) -> None:
    _docx(
        out / "helios3-end-effector-design-doc.docx",
        "Helios-3 End Effector Design Document",
        "Tomas Lindqvist",
        datetime(2026, 3, 6, 17, 20),
        [
            ("h1", "Helios-3 End Effector Design Document"),
            ("p", "Author: Tomas Lindqvist"),
            ("p", "Date: 2026-03-06"),
            ("p", "Revision: C — issued following the design review of 4 March 2026"),
            ("h2", "1. Scope"),
            (
                "p",
                "This document specifies the end effector for the Helios-3 300 mm atmospheric "
                "wafer handler, covering the selection rationale, the interface to the arm, and "
                "the incoming inspection requirements that the selection depends on.",
            ),
            ("h2", "2. Candidates evaluated"),
            (
                "table",
                [
                    ["Candidate", "Front adders", "Back adders", "Positional drift", "Relative cost"],
                    ["Vacuum paddle", "2.4", "14.0", "< 20 um", "1.0x"],
                    ["Bernoulli non-contact", "9.1", "1.2", "up to 400 um", "2.1x"],
                    ["Alumina edge grip", "1.9", "1.8", "< 10 um", "3.8x"],
                ],
            ),
            (
                "p",
                "Adders are counted at 0.05 um and above, averaged over 50 passes, measured on "
                "both wafer surfaces. Positional drift is measured at maximum rotational speed "
                "at full arm extension.",
            ),
            ("h2", "3. Selection"),
            (
                "p",
                "The alumina edge grip blade from Cerapoint Ceramics, part CP-220, is selected. "
                "It is the only candidate that meets the three-adder-per-pass specification on "
                "both surfaces, and mechanical capture retains the wafer on loss of power, "
                "which improves the wafer retention case for SEMI S2.",
            ),
            (
                "p",
                "The selection is accepted with two known consequences: the blade costs 3.8 "
                "times the vacuum paddle, and Cerapoint is the only qualified supplier at a "
                "quoted lead time of thirteen weeks.",
            ),
            ("h2", "4. Critical characteristics"),
            (
                "table",
                [
                    ["Characteristic", "Specification", "Verification"],
                    ["Contact pad chamfer", "0.15 mm +/- 0.02", "First article per lot"],
                    ["Chamfer surface finish", "0.4 um Ra maximum", "First article per lot"],
                    ["Blade flatness", "50 um over 300 mm", "First article per lot"],
                    ["Pad coplanarity", "25 um", "100% at assembly"],
                    ["Material", "99.6% alumina", "Supplier certificate"],
                ],
            ),
            (
                "p",
                "The chamfer geometry is the characteristic that produces the particle result. "
                "A blade with an out-of-specification chamfer picks wafers normally and gives "
                "no indication of the defect until adders appear on a customer's metrology.",
            ),
            ("h2", "5. Incoming inspection"),
            (
                "bullet",
                "First article dimensional inspection of the chamfer on every lot, performed by "
                "Meridian and not accepted on the supplier certificate alone.",
            ),
            (
                "bullet",
                "One retained sample per lot, stored for twelve months, so that a field failure "
                "can be traced back to what was actually received.",
            ),
            (
                "bullet",
                "Buffer stock of eight weeks (46 blades) held on site against the thirteen week "
                "lead time.",
            ),
            ("h2", "6. Known limitations"),
            (
                "p",
                "The one kilohertz position loop on the Rev A controller overshoots by "
                "approximately 60 um on handoff settle with this blade. The overshoot is inside "
                "the teach repeatability specification because the motion waits for settle, but "
                "it costs an estimated 20 to 40 wafers per hour of throughput. The four "
                "kilohertz Rev B controller is deferred to a follow-on revision.",
            ),
        ],
    )


def northgate_8d(out: Path) -> None:
    _docx(
        out / "northgate-8d-report.docx",
        "8D Report — Northgate Micro Particle Excursion",
        "Ingrid Lund",
        datetime(2026, 4, 30, 15, 0),
        [
            ("h1", "8D Report — Northgate Micro Particle Excursion"),
            ("p", "Author: Ingrid Lund and Claire Dubois"),
            ("p", "Date: 2026-04-30"),
            ("p", "Nonconformance reference: NCR-2026-014. Customer: Northgate Micro, Chandler."),
            ("h2", "D1 — Team"),
            (
                "p",
                "Ingrid Lund (contamination control, lead), Tomas Lindqvist (mechanical design), "
                "Nadia Haddad (supplier quality), Victor Nwosu (on site), Claire Dubois "
                "(quality, approver).",
            ),
            ("h2", "D2 — Problem description"),
            (
                "p",
                "On 7 April 2026 the customer's surfscan metrology recorded an average of 22 "
                "particle adders at 0.05 um and above on the backside of wafers processed "
                "through the Helios-3 pilot handler, against a customer limit of 5. A send-ahead "
                "wafer passed through the handler with no process step accumulated 19 backside "
                "adders, isolating the handler as the source. The tool was held from 7 April to "
                "15 April. Three lots totalling 75 wafers were placed on hold.",
            ),
            ("h2", "D3 — Containment"),
            (
                "bullet",
                "Tool held from production on 7 April at the customer's decision.",
            ),
            (
                "bullet",
                "End effector replaced on 13 April with a blade from a verified lot; top plate "
                "gasket reworked by hand on site.",
            ),
            (
                "bullet",
                "Send-ahead verification on 15 April measured 2.1 backside and 1.9 front side "
                "adders per pass. Tool released to production.",
            ),
            ("h2", "D4 — Root cause"),
            (
                "p",
                "Two independent causes were confirmed, which is why substituting either fix "
                "alone did not return the tool to baseline.",
            ),
            (
                "p",
                "Cause 1: the ceramic blade installed in the tool came from Cerapoint lot "
                "CP-220-0413. The retained sample from that lot measures a contact pad chamfer "
                "of 0.08 to 0.11 mm against a specified 0.15 mm +/- 0.02, with a surface finish "
                "of approximately 1.6 um Ra against a specified 0.4 um maximum. The sharper, "
                "rougher pad abrades the wafer edge exclusion zone and generates alumina debris "
                "which deposits on the backside. The supplier's certificate of conformance for "
                "this lot records a passing first article inspection.",
            ),
            (
                "p",
                "Cause 2: the gasket between the fan filter unit frame and the EFEM top plate "
                "was unevenly compressed at the rear left corner, leaving a gap of approximately "
                "1.5 mm over 80 mm of length. Unfiltered air was drawn into the box, elevating "
                "front side adders and preventing recovery to baseline. The bolt pattern at the "
                "plate corners is too sparse to hold compression across normal build variation.",
            ),
            ("h2", "D5 — Corrective actions"),
            (
                "table",
                [
                    ["Action", "Owner", "Due", "Status"],
                    ["100% incoming chamfer inspection for the next three lots", "Nadia Haddad", "2026-04-24", "Complete"],
                    ["Supplier corrective action request to Cerapoint", "Nadia Haddad", "2026-05-08", "Open"],
                    ["Retained sample per lot, formalised in the quality system", "Claire Dubois", "2026-05-15", "Open"],
                    ["Two additional fasteners per top plate corner (design change)", "Tomas Lindqvist", "2026-04-24", "Complete"],
                    ["Field rework kit for four built machines", "Tomas Lindqvist", "2026-05-29", "Open"],
                    ["Top plate leak check added as a build step", "Greg Salinas", "2026-05-01", "Complete"],
                ],
            ),
            ("h2", "D6 — Verification"),
            (
                "p",
                "Post-repair send-ahead measurements on the customer tool: 2.1 backside and 1.9 "
                "front side adders per pass, inside both the customer limit of 5 and the Meridian "
                "specification of 3. Box recovery to baseline measured at 74 seconds against a "
                "90 second internal target.",
            ),
            ("h2", "D7 — Prevention"),
            (
                "p",
                "Incoming inspection of supplier-declared critical characteristics is no longer "
                "satisfied by a certificate of conformance alone for any characteristic that is "
                "not detectable in assembly or in functional test. The top plate fastener change "
                "is carried into the production drawing set and into the four machines already "
                "built.",
            ),
            ("h2", "D8 — Closure"),
            (
                "p",
                "Issued to the customer 30 April 2026. Customer formal closure pending as of "
                "issue. Approved by Claire Dubois, QA and Equipment Safety Certification Lead.",
            ),
        ],
    )


def s2_certification_plan(out: Path) -> None:
    _docx(
        out / "semi-s2-certification-plan.docx",
        "Helios-3 SEMI S2/S8 Certification Plan",
        "Claire Dubois",
        datetime(2026, 4, 17, 10, 0),
        [
            ("h1", "Helios-3 SEMI S2/S8 Certification Plan"),
            ("p", "Author: Claire Dubois"),
            ("p", "Date: 2026-04-17"),
            (
                "p",
                "Includes the results of the paper pre-assessment carried out in April 2026 "
                "against the SEMI S2 checklist, ahead of the production-intent build.",
            ),
            ("h2", "1. Scope of certification"),
            (
                "bullet",
                "SEMI S2 environmental, health and safety evaluation of the Helios-3 EFEM.",
            ),
            ("bullet", "SEMI S8 ergonomics, evaluated in the same pass."),
            (
                "bullet",
                "CE marking for European shipments: machinery directive and EMC directive, "
                "reusing the S2 technical file where permitted.",
            ),
            ("h2", "2. Schedule"),
            (
                "table",
                [
                    ["Milestone", "Planned date", "Dependency"],
                    ["Paper pre-assessment complete", "2026-04-17", "Drawing set"],
                    ["Production-intent build in cleanroom", "2026-06-30", "Long lead parts"],
                    ["On-tool evaluation", "July 2026", "Machine availability"],
                    ["Third party assessor on site", "2026-08-10", "Slot held, deposit paid"],
                    ["S2 report signed", "2026-08-28", "No major findings"],
                    ["EMC test at accredited lab", "2026-07-21", "Provisional booking"],
                ],
            ),
            (
                "p",
                "The assessor slot was booked in March at a deposit of USD 4,000, forfeited if "
                "the date moves. Booking eight weeks ahead of a machine that did not yet exist "
                "was a deliberate decision taken on 12 March 2026.",
            ),
            ("h2", "3. Pre-assessment findings"),
            (
                "table",
                [
                    ["Ref", "Section", "Finding", "Severity", "Status"],
                    ["PA-01", "Hazardous energy isolation", "Vacuum generator supply not covered by the main disconnect", "Major", "Closed in Rev D drawings"],
                    ["PA-02", "Safeguarding", "Interlocks fully bypassed in teach mode; arm can move at full speed", "Major", "Closed: reduced speed enforced in firmware plus hold-to-run pendant"],
                    ["PA-03", "Seismic", "Restraint calculation not signed by a structural engineer", "Major", "Open: engineering firm queue is three weeks"],
                    ["PA-04", "Ergonomics (S8)", "Load port teach position requires sustained overhead reach", "Minor", "Closed: service platform added"],
                    ["PA-05", "Documentation", "Material declarations missing for approximately 40 suppliers", "Minor", "Open: supply chain collecting"],
                    ["PA-06", "Emergency off", "EMO does not remove power from the ioniser", "Minor", "Closed in Rev D drawings"],
                ],
            ),
            (
                "p",
                "Fourteen findings were raised in the pre-assessment. Eleven were closed in the "
                "drawing set before the build, which is the entire purpose of running a paper "
                "pass in April rather than discovering the same findings on a built machine in "
                "August.",
            ),
            ("h2", "4. Risk to the programme"),
            (
                "p",
                "The certification schedule has no float. A major finding at the on-tool "
                "assessment implies a design change, a rebuild of the affected subsystem and a "
                "re-evaluation of that section, which adds three to five weeks. The single "
                "production-intent machine is shared between engineering verification and the "
                "S2 evaluation, and approximately three of the eight evaluation weeks require "
                "exclusive access to it.",
            ),
        ],
    )


def kestrel_integration_spec(out: Path) -> None:
    """Deliberately a draft: unresolved TBDs, open questions, no approver."""
    _docx(
        out / "kestrel2-test-cell-integration-spec-DRAFT.docx",
        "Kestrel-2 Test Cell Integration Specification (DRAFT)",
        "Victor Nwosu",
        datetime(2026, 6, 26, 18, 40),
        [
            ("h1", "Kestrel-2 Test Cell Integration Specification (DRAFT)"),
            ("p", "Author: Victor Nwosu"),
            ("p", "Date: 2026-06-26"),
            (
                "p",
                "DRAFT — work in progress, circulated for comment. Do not issue to customers. "
                "Several sections are TBD pending engineering input.",
            ),
            ("h2", "1. Mechanical docking"),
            (
                "p",
                "The handler docks to the tester manipulator on a three-point kinematic "
                "interface. Docking repeatability requirement is TBD pending the plunge force "
                "work; the current working figure of 50 um is inherited from the previous "
                "generation and has not been confirmed for Kestrel-2.",
            ),
            ("h2", "2. Thermal"),
            (
                "table",
                [
                    ["Parameter", "Value", "Confidence"],
                    ["Temperature range at device", "-45 C to +150 C", "Confirmed"],
                    ["Soak to within 2 C", "< 6 minutes", "Confirmed"],
                    ["Site-to-site spread", "0.6 C measured", "Measured at Tallgrass"],
                    ["Purge dew point requirement", "-60 C at the site", "Confirmed"],
                    ["House air requirement", "None; membrane dryer on board", "Confirmed"],
                ],
            ),
            ("h2", "3. Throughput"),
            (
                "p",
                "7,850 UPH measured on a customer device at four sites. The 8,000 UPH figure in "
                "marketing material is a target. TBD: whether the published specification should "
                "be changed to the measured number.",
            ),
            ("h2", "4. Changeover"),
            (
                "p",
                "Measured at 31 minutes by a trained engineer without the auto-teach routine. "
                "With auto-teach the expected figure is approximately 26 minutes. The datasheet "
                "currently claims under 25 minutes, which is not supportable. Placeholder: "
                "under 30 minutes pending a decision by Product.",
            ),
            ("h2", "5. Electrical and safety interfaces"),
            (
                "bullet", "Tester interlock loop: TBD, waiting on the tester vendor's document.",
            ),
            (
                "bullet",
                "Dew point sensor interlock is safety rated with a hard stop, not a software "
                "warning.",
            ),
            ("bullet", "Force sensor failure behaviour: TBD (see plunge force work)."),
            ("h2", "6. Open questions"),
            ("bullet", "Contactor life claim: awaiting the 500,000 insertion life test."),
            ("bullet", "Who owns the preventive maintenance schedule for the membrane dryer?"),
            ("bullet", "Does the customer or Meridian supply the changeover kit storage cart?"),
        ],
    )


def helios_open_items(out: Path) -> None:
    """Deliberately sparse and unattributed: no author line, no core author."""
    document = DocxDocument()
    document.add_heading("Helios-3 open items", level=1)
    document.add_paragraph("Scratch list from the bench. Not maintained.")
    document.add_paragraph("- encoder EOL, check with Nadia")
    document.add_paragraph("- rework kit for 004?")
    document.add_paragraph("- ask about the nine pass number")
    props = document.core_properties
    # python-docx stamps itself as the author by default; blank it so the file is
    # genuinely unattributed and the pipeline flags it as such.
    props.author = ""
    props.last_modified_by = ""
    props.title = "Helios-3 open items"
    props.created = datetime(2026, 7, 6, 8, 15)
    props.modified = datetime(2026, 7, 6, 8, 15)
    document.save(str(out / "helios3-open-items.docx"))


def bridge_minutes(out: Path) -> None:
    _docx(
        out / "2026-04-09-northgate-bridge-minutes.docx",
        "Minutes — Northgate Escalation Bridge, 9 April 2026",
        "Aisha Bello",
        datetime(2026, 4, 9, 19, 30),
        [
            ("h1", "Minutes — Northgate Escalation Bridge, 9 April 2026"),
            ("p", "Author: Aisha Bello"),
            ("p", "Date: 2026-04-09"),
            (
                "p",
                "Present: Aisha Bello, Ingrid Lund, Tomas Lindqvist, Victor Nwosu, Ryan Chen, "
                "Priya Raman, Marcus Feld.",
            ),
            ("h2", "Position"),
            (
                "p",
                "The customer's pilot Helios-3 handler has been down since Tuesday 7 April. "
                "Customer metrology shows 22 backside adders at 0.05 um against a limit of 5. A "
                "send-ahead wafer through the handler alone accumulated 19 adders. Three lots, "
                "75 wafers, on hold.",
            ),
            ("h2", "Agreed position with the customer"),
            (
                "bullet",
                "We accept that the handler is the source on the evidence available.",
            ),
            ("bullet", "Engineer on site by Friday 10 April."),
            ("bullet", "Preliminary root cause within five working days."),
            ("bullet", "8D report within three weeks."),
            (
                "bullet",
                "No statement on compensation until root cause is established. The account team "
                "is instructed not to offer a number.",
            ),
            ("h2", "Investigation plan"),
            (
                "p",
                "Four hypotheses to be separated by staged send-ahead wafers: end effector "
                "blade condition, Z-axis bellows wear debris, EFEM top plate filter bypass, and "
                "the customer's own load port. The build record is to be checked for the "
                "ceramic blade lot in the machine.",
            ),
            ("h2", "Actions"),
            (
                "table",
                [
                    ["Action", "Owner", "Due"],
                    ["Travel to site with a retained blade for swap testing", "Ingrid Lund", "2026-04-10"],
                    ["Meet on site, site access already cleared", "Victor Nwosu", "2026-04-10"],
                    ["Check build record for the installed blade lot", "Tomas Lindqvist", "2026-04-09"],
                    ["Customer written update within the hour", "Aisha Bello", "2026-04-09"],
                    ["Compensation range agreed internally", "Priya Raman", "2026-04-15"],
                    ["Daily bridge at 08:00 Pacific until the tool is up", "Aisha Bello", "Ongoing"],
                ],
            ),
        ],
    )


def fy26_budget(out: Path) -> None:
    """CONTRADICTS the 21 May transcript: the Helios-3 NRE line was cut from
    3.6M to 3.2M in that meeting and this workbook still carries 3,600,000."""
    _xlsx(
        out / "fy26-budget.xlsx",
        "FY26 Budget — Working File",
        "Owen Brady",
        datetime(2026, 5, 6, 12, 0),
        [
            (
                "Revenue Plan",
                [
                    ["Quarter", "Plan (USD)", "Actual (USD)", "Variance", "Note"],
                    ["Q1 FY26", 9800000, 9640000, -160000, "Kestrel units on plan"],
                    ["Q2 FY26", 9300000, 7760000, -1540000, "Two Helios units moved out"],
                    ["Q3 FY26", 13200000, "", "", "Helios FCS assumed 30 Sep"],
                    ["Q4 FY26", 15900000, "", "", "Northgate production order assumed"],
                    ["FY26 total", 48200000, "", "", ""],
                ],
            ),
            (
                "R&D Spend",
                [
                    ["Line", "Budget (USD)", "Forecast (USD)", "Owner", "Note"],
                    ["Helios-3 NRE", 3600000, 3600000, "Priya Raman", "Includes Rev B controller spin"],
                    ["Kestrel-2 development", 2450000, 2545000, "Tomas Lindqvist", "Dry-break and auto-teach added"],
                    ["Vantage 4.0", 2900000, 2900000, "Elena Vasquez", ""],
                    ["Sustaining engineering", 1650000, 1860000, "Priya Raman", "Northgate excursion response 210k"],
                    ["Second source qualification", 0, 140000, "Nadia Haddad", "Halstead, approved 26 Mar"],
                    ["Shared engineering tools and EDA licences", 800000, 860000, "Priya Raman", "Seat count true-up"],
                    ["R&D total", 11400000, 11905000, "", "505k over plan"],
                ],
            ),
            (
                "Capex",
                [
                    ["Item", "Budget (USD)", "Spent (USD)", "Status"],
                    ["ISO Class 5 assembly bay expansion", 2100000, 400000, "Design and permits complete"],
                    ["Metrology: surfscan for incoming inspection", 340000, 340000, "Installed"],
                    ["Kestrel life test rig", 85000, 0, "Not started"],
                    ["Cleanroom gowning expansion", 60000, 0, "Deferred"],
                ],
            ),
            (
                "Working Capital",
                [
                    ["Item", "Value (USD)", "Rationale"],
                    ["Cerapoint blade buffer stock (8 weeks, 46 blades)", 71000, "Approved 26 Mar against 13 week lead time"],
                    ["Kaneda reducer safety stock", 33600, "Four units"],
                    ["Brunnen encoder last-time-buy", "TBD", "Letter received; quantity not yet sized"],
                ],
            ),
        ],
    )


def helios_bom(out: Path) -> None:
    _xlsx(
        out / "helios3-bom-long-lead.xlsx",
        "Helios-3 Long Lead Bill of Materials",
        "Nadia Haddad",
        datetime(2026, 8, 28, 9, 45),
        [
            (
                "Long Lead Items",
                [
                    ["Part", "Supplier", "Qty per machine", "Unit cost (USD)", "Lead time (weeks)", "Source", "Status"],
                    ["Harmonic drive reducer, theta", "Kaneda Precision", 1, 4200, 22, "Single", "On allocation, expedite approved"],
                    ["Harmonic drive reducer, R", "Kaneda Precision", 1, 4200, 22, "Single", "On allocation, expedite approved"],
                    ["Linear encoder head", "Brunnen Motion", 2, 10500, 11, "Single", "End of life, LTB by 2026-11-30"],
                    ["Ceramic edge grip blade CP-220", "Cerapoint Ceramics", 2, 1550, 13, "Single", "Buffer stock 46 units"],
                    ["Fan filter unit, ISO Class 2", "Aldera Air", 6, 5700, 8, "Dual", "Plenum redesign under evaluation"],
                    ["Frame weldment, machined", "Kestone Fabrication", 1, 58000, 9, "Dual", "Three datums removed in cost down"],
                    ["Z axis linear motor", "Brunnen Motion", 1, 7900, 10, "Single", ""],
                    ["Wafer mapping sensor", "Optivia Sensing", 1, 2300, 6, "Dual", ""],
                    ["Ioniser bar", "Aldera Air", 2, 890, 4, "Dual", ""],
                    ["Controller board Rev A", "In house", 1, 3400, 12, "Internal", "Rev B in development"],
                ],
            ),
            (
                "Second Source Status",
                [
                    ["Part", "Alternate supplier", "Qualification cost (USD)", "Duration", "Blocker", "Target complete"],
                    ["Harmonic drive reducer", "Halstead Drive", 140000, "5 months", "Catalogue backlash 1 arc-min vs 0.7 required", "Q1 2027"],
                    ["Ceramic edge grip blade", "None identified", "", "", "Three shops worldwide can hold the chamfer", ""],
                    ["Linear encoder head", "Replacement selected in Rev B", 0, "", "Rev B schedule", "2026-12"],
                    ["Fan filter unit", "Qualified", 0, "", "None", "Complete"],
                ],
            ),
            (
                "Build Rate Constraint",
                [
                    ["Month", "Plan (machines)", "Reducer supply (machines)", "Cleanroom capacity (machines)", "Achievable"],
                    ["2026-09", 5, 3, 4, 3],
                    ["2026-10", 6, 3, 4, 3],
                    ["2026-11", 7, 3, 4, 3],
                    ["2026-12", 7, 3, 4, 3],
                    ["2027-01", 8, 3, 7, 3],
                    ["2027-02", 8, 3, 7, 3],
                ],
            ),
        ],
    )


def vantage_metrics(out: Path) -> None:
    _xlsx(
        out / "vantage-oee-metrics-q2.xlsx",
        "Vantage Q2 Service Metrics",
        "Hassan Idris",
        datetime(2026, 7, 8, 16, 20),
        [
            (
                "Availability by Region",
                [
                    ["Region", "Month", "SLA target", "Measured", "Credit owed (USD)", "Note"],
                    ["North America", "2026-04", "99.5%", "99.94%", 0, ""],
                    ["North America", "2026-05", "99.5%", "99.91%", 0, ""],
                    ["North America", "2026-06", "99.5%", "99.97%", 0, ""],
                    ["EU", "2026-04", "99.5%", "99.88%", 0, ""],
                    ["EU", "2026-05", "99.5%", "99.20%", 3400, "47 minute migration lock incident on 19 May"],
                    ["EU", "2026-06", "99.5%", "99.96%", 0, ""],
                    ["APAC", "2026-04", "99.5%", "99.90%", 0, ""],
                    ["APAC", "2026-05", "99.5%", "99.93%", 0, ""],
                    ["APAC", "2026-06", "99.5%", "99.89%", 0, ""],
                ],
            ),
            (
                "OEE Recalculation Impact",
                [
                    ["Account", "Tools connected", "Availability, old method", "Availability, E10 method", "Delta", "Briefed"],
                    ["Northgate Micro", 3, "94.2%", "92.0%", "-2.2", "Deferred to post 8D"],
                    ["Verdant Power Semi", 11, "91.8%", "88.7%", "-3.1", "Yes, 2026-05-04"],
                    ["Tallgrass Semiconductor", 6, "95.1%", "93.4%", "-1.7", "Yes, 2026-05-11"],
                    ["Cobalt Foundry Group", 0, "", "", "", "Not yet connected"],
                    ["Halden Photonics", 2, "89.9%", "88.8%", "-1.1", "Yes, 2026-06-02"],
                    ["Meadowbrook Devices", 8, "96.4%", "95.2%", "-1.2", "Yes, 2026-05-19"],
                    ["Orlin Analog", 4, "93.0%", "91.5%", "-1.5", "Yes, 2026-06-09"],
                    ["Pashen Micro", 5, "92.6%", "90.4%", "-2.2", "Yes, 2026-06-16"],
                    ["Steinfeld Sensors", 2, "97.1%", "96.6%", "-0.5", "Yes, 2026-08-27"],
                ],
            ),
            (
                "Alarm Volume",
                [
                    ["Account", "Peak alarms per minute", "Duplicate share", "Post dedup peak", "Dashboard impact"],
                    ["Verdant Power Semi", 10400, "94%", 624, "Region-wide timeout, 11 minutes, January"],
                    ["Tallgrass Semiconductor", 1850, "88%", 222, "None"],
                    ["Meadowbrook Devices", 940, "71%", 273, "None"],
                    ["Northgate Micro", 310, "62%", 118, "None"],
                ],
            ),
        ],
    )


def hiring_tracker(out: Path) -> None:
    _xlsx(
        out / "engineering-hiring-tracker.xlsx",
        "Engineering Hiring Tracker",
        "Sofia Marchetti",
        datetime(2026, 7, 10, 11, 5),
        [
            (
                "Open Requisitions",
                [
                    ["Requisition", "Department", "Opened", "Days open", "Band top (USD)", "Stage", "Note"],
                    ["Senior Motion Control Engineer", "Engineering", "2026-01-14", 177, 195000, "Offer out", "Band raised from 165k on 22 May"],
                    ["Contamination Control Engineer", "Engineering", "2026-02-03", 157, 168000, "Sourcing", "Rewritten to hire for aptitude plus consultant"],
                    ["Field Service Engineer, APAC", "Sales and CS", "2026-03-19", 113, 132000, "Verbal accept", "Start 2026-09-01, based Penang"],
                    ["Software Engineer, Vantage (x2)", "Engineering", "2026-02-24", 136, 158000, "Filled", "Both start August"],
                    ["Cleanroom Technician (x2)", "Operations", "2026-07-09", 1, 78000, "Not posted", "Added at the July review"],
                ],
            ),
            (
                "Metrics",
                [
                    ["Metric", "Value", "Benchmark", "Note"],
                    ["Average time to fill, engineering", "94 days", "60 days", ""],
                    ["Voluntary attrition, annualised", "11%", "12%", "Two operations departures cited shift pattern"],
                    ["Offer acceptance rate", "67%", "85%", "Two declines on compensation"],
                    ["Open requisitions", 5, "", ""],
                ],
            ),
            (
                "Compensation Actions",
                [
                    ["Action", "Cost (USD annualised)", "Approved by", "Date"],
                    ["Raise senior motion control band to 195k", 30000, "Yuki Tanaka", "2026-05-21"],
                    ["Level two existing motion control engineers", 40000, "Yuki Tanaka", "2026-05-21"],
                    ["Contamination control consultant, 6 months", 73000, "Pending", "Budget amendment required"],
                ],
            ),
        ],
    )


def cost_reduction_tracker(out: Path) -> None:
    _xlsx(
        out / "efem-cost-reduction-tracker.xlsx",
        "EFEM Cost Reduction Tracker",
        "Owen Brady",
        datetime(2026, 7, 31, 17, 0),
        [
            (
                "Actions",
                [
                    ["Action", "Owner", "Saving per machine (USD)", "Investment (USD)", "Gate", "Status"],
                    ["Remove three machined datums from the frame", "Tomas Lindqvist", 11000, 0, "Alignment requalification", "Approved"],
                    ["Five fan filter units with redesigned plenum", "Ingrid Lund", 5700, 18000, "90 second box recovery measurement", "Approved, gated"],
                    ["Rev B encoder selection", "Nadia Haddad", 6000, 200000, "Rev B schedule", "Approved, funded Aug"],
                    ["Move harness assembly out of the clean bay", "Greg Salinas", 9000, 0, "Bagging procedure", "Approved"],
                    ["Move frame assembly out of the clean bay", "Greg Salinas", "TBD", 0, "Process review with contamination control", "September decision"],
                ],
            ),
            (
                "Cost Bridge",
                [
                    ["Line", "Current (USD)", "Target (USD)", "Note"],
                    ["Standard cost per EFEM", 366000, 334300, "After the four approved actions"],
                    ["List price", 620000, 620000, ""],
                    ["Gross margin", "41%", "46%", "Company target is 52%"],
                    ["Harmonic drive reducers (2)", 8400, 8400, "Includes expedite premium"],
                    ["Linear encoder pair", 21000, 15000, "Rev B"],
                    ["Ceramic blade set", 3100, 3100, "No alternative supplier"],
                    ["Fan filter units (6)", 34200, 28500, "Five units, gated on measurement"],
                    ["Frame weldment and machining", 58000, 47000, "Three datums removed"],
                    ["Labour and cleanroom overhead", 62000, 53000, "Harness relocation"],
                ],
            ),
        ],
    )


BUILDERS = [
    helios3_status_deck,
    vantage_roadmap_deck,
    northgate_escalation_deck,
    tallgrass_eval_deck,
    end_effector_design_doc,
    northgate_8d,
    s2_certification_plan,
    kestrel_integration_spec,
    helios_open_items,
    bridge_minutes,
    fy26_budget,
    helios_bom,
    vantage_metrics,
    hiring_tracker,
    cost_reduction_tracker,
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    for build in BUILDERS:
        build(out)

    files = sorted(p.name for p in out.iterdir() if p.suffix in {".docx", ".pptx", ".xlsx"})
    print(f"wrote {len(files)} files to {out}")
    for name in files:
        print(f"  {name}")


if __name__ == "__main__":
    main()
