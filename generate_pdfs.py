"""Generate four fictional supplier RFP responses (PDF) for the classroom mini project."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUT = Path(__file__).parent / "sample_pdfs"
OUT.mkdir(exist_ok=True)

REQUEST = ("RFP-2026-014: Cloud Contract and Invoice Management Platform for "
           "Meridian Manufacturing Ltd (fictional company)")

SUPPLIERS = {
"Apex_Systems": {
 "name": "Apex Systems",
 "summary": [
  "Meridian Manufacturing needs one platform to manage supplier contracts, purchase-order matching and invoices for about 2,000 users across six plants. Apex Systems proposes a cloud-native, API-first platform built on a microservices architecture and deployed on Kubernetes in two availability zones. We have read the requirement carefully and see three priorities: reliable integration with SAP S/4HANA, strong auditability, and the ability to scale as new plants are added.",
  "Our design has been load tested at 5,000 concurrent users and provides a 99.95% availability SLA. All integrations use documented REST APIs and an event-driven message bus, so Meridian is not locked into point-to-point interfaces."],
 "solution": [
  "Architecture: stateless microservices behind an API gateway, PostgreSQL clusters with automatic failover, and an event bus for asynchronous processing. Horizontal scaling is automatic and has been tested to three times the stated volume.",
  "Integrations: standard connectors for SAP S/4HANA (IDoc and OData), Oracle ERP, and Microsoft Entra ID for single sign-on (SAML 2.0 and OIDC). A published API catalogue and webhooks allow Meridian's own teams to extend the platform. Integration testing is included for every connector.",
  "Implementation approach: discovery, configuration, integration, user acceptance testing, and cutover. Data migration uses automated validation scripts with reconciliation reports."],
 "milestones": [("Discovery and design sign-off", "Month 2"), ("Core platform configured", "Month 4"), ("SAP and SSO integration complete", "Month 6"), ("User acceptance testing", "Month 8"), ("Go-live", "Month 10")],
 "team": "A delivery team of 11: one programme manager, two solution architects, four engineers, two integration specialists, one QA lead and one security engineer. The programme manager will be named at contract signature.",
 "price": [("Platform licence (3 years)", "USD 780,000"), ("Implementation and integration", "USD 520,000"), ("Hosting and operations (3 years)", "USD 180,000"), ("Total 3-year cost", "USD 1,480,000")],
 "assumptions": "Pricing assumes 2,000 named users, two ERP connectors and one data migration. Additional connectors are USD 45,000 each. Standard support is included; 24x7 support is an optional USD 120,000 per year.",
 "security": [
  "Apex holds ISO 27001 and SOC 2 Type II certifications, renewed annually. Data is encrypted at rest (AES-256) and in transit (TLS 1.3). Role-based access control and mandatory MFA apply to all administrator accounts.",
  "Independent penetration tests are carried out twice a year and the executive summary is shared with customers. A full immutable audit log records every user and system action and is retained for seven years. Our GDPR data processing agreement is included in the contract, with EU data residency.",
  "Incident response: a documented plan with a 1-hour notification commitment for confirmed security incidents."],
 "support": [
  "Standard support is available Monday to Friday, 08:00 to 18:00 CET, with a 4-hour response for priority-one issues. 24x7 support is available as an optional extra. A named technical account manager is assigned to Meridian.",
  "Apex has delivered five comparable contract and invoice platforms for manufacturers in the last six years. References: Halden Components (Procurement Director) and Northvale Foods (Head of Finance Systems); contact details are available during due diligence."],
},
"BrightPath_Tech": {
 "name": "BrightPath Tech",
 "summary": [
  "BrightPath Tech offers Meridian a fast, low-cost contract and invoice management solution. Our platform is a modern web application that can be live in four months. We understand that Meridian wants to reduce manual invoice handling and we believe our price is the most competitive you will receive."],
 "solution": [
  "Our solution is a cloud-hosted web application with standard modules for contracts, purchase orders and invoices. It is designed to be simple, quick to deploy and easy to use. Integration with Meridian's ERP will be done through a standard interface and file exchange.",
  "We use a standard configuration approach that keeps customisation to a minimum, which reduces cost and risk. Single sign-on can be configured on request."],
 "milestones": [("Kick-off", "Week 1"), ("Configuration", "Week 8"), ("Testing", "Week 13"), ("Go-live", "Week 16")],
 "team": "A small delivery team of four people led by the founder and managing director.",
 "price": [("Platform subscription (3 years)", "USD 360,000"), ("Implementation", "USD 290,000"), ("Total 3-year cost", "USD 690,000")],
 "assumptions": "Prices are indicative and exclude hosting fees and any additional modules.",
 "security": [
  "Security is taken very seriously at BrightPath. We follow industry-standard security practices and our hosting provider is a leading cloud vendor. Formal certification is on our roadmap.",
  "Data is protected and backed up regularly. Details of our controls can be provided on request."],
 "support": [
  "Support is provided by email during business hours, with a response on the next working day.",
  "BrightPath was founded in 2022. We have delivered one comparable project, for a regional distributor. A reference is available on request."],
},
"NexaWorks": {
 "name": "NexaWorks",
 "summary": [
  "NexaWorks proposes a configurable contract and invoice management platform delivered through a structured, phased implementation. We understand that Meridian's main risks are adoption across six plants, data quality during migration, and keeping the finance team's close calendar unaffected. Our proposal is designed around those risks, with a clear plan, a named team and a strong support model."],
 "solution": [
  "Platform: an API-first application with a standard SAP S/4HANA connector, single sign-on (SAML 2.0), and configurable approval workflows. The platform is hosted in a single EU region with a secondary region for disaster recovery. It meets the stated user volume with headroom; formal load-test results for 5,000 users will be shared at the design stage.",
  "Delivery approach: four phases, namely mobilise, build, pilot at two plants, and roll-out to the remaining four plants. Each phase has entry and exit criteria, and a RACI matrix agreed with Meridian at kick-off."],
 "milestones": [("Mobilisation and RACI agreed", "Month 1"), ("Design sign-off", "Month 2"), ("Build and SAP integration", "Month 4"), ("Pilot at two plants", "Month 5"), ("Roll-out to four plants", "Month 6"), ("Go-live and 6-week hypercare", "Month 7")],
 "team": "A team of eight with named roles: programme manager, solution architect, two engineers, integration lead, QA lead, change manager and a customer success manager. A staffing plan with availability by month is provided in the appendix. Training covers 40 super-users and role-based sessions for all approvers.",
 "price": [("Platform subscription (3 years)", "USD 570,000"), ("Implementation, training and hypercare", "USD 340,000"), ("Hosting, DR and operations (3 years)", "USD 180,000"), ("Total 3-year cost", "USD 1,090,000")],
 "assumptions": "Pricing assumes 2,000 named users, one SAP connector and one data migration. Change requests are charged at a fixed day rate of USD 1,100. 24x7 support is included in the price.",
 "security": [
  "NexaWorks is ISO 27001 certified. A SOC 2 Type II audit is in progress, with the report expected in the next quarter. Data is encrypted at rest and in transit, role-based access control is enforced, and administrator accounts require MFA. EU data residency and a GDPR data processing agreement are standard.",
  "A risk register is maintained for the programme. Top risks include late master-data cleansing (mitigation: early data profiling in month 1), plant resistance to change (mitigation: change manager and super-user network) and ERP release conflicts (mitigation: a frozen-interface window and contingency of three weeks)."],
 "support": [
  "24x7 tier-1 support is included. Priority-one incidents receive a 30-minute response and a 4-hour resolution target, with escalation to a named customer success manager and a monthly service review.",
  "NexaWorks has delivered four similar implementations for mid-sized manufacturers over the past five years. References: Brandt Packaging and Solvik Metals; contact details provided on request."],
},
"Orbit_Digital": {
 "name": "Orbit Digital",
 "summary": [
  "Orbit Digital has delivered contract and invoice platforms for manufacturers for eleven years and brings deep experience in this domain. We understand Meridian's need to consolidate its procurement-to-pay processes and are confident that our proven platform will meet your needs."],
 "solution": [
  "Our platform covers contract repository, purchase-order matching, invoice capture and approval workflows. It is deployed as a managed cloud service.",
  "Integration with existing systems will be agreed during the discovery phase, once we have reviewed Meridian's landscape. We have integrated with many ERP systems in the past and will select the best approach with Meridian's IT team."],
 "milestones": [("Discovery", "Month 2"), ("Build", "Month 5"), ("Testing and go-live", "Month 8")],
 "team": "The team will be confirmed after contract award and typically includes a project manager, consultants and engineers.",
 "price": [("Platform subscription (3 years)", "USD 520,000"), ("Implementation", "USD 430,000"), ("Hosting (3 years)", "USD 230,000"), ("Total 3-year cost", "USD 1,180,000")],
 "assumptions": "Pricing is based on a standard configuration. Integration work beyond the standard scope will be quoted after discovery.",
 "security": [
  "Orbit Digital is ISO 27001 certified and encrypts data in transit and at rest. Access is controlled by user roles. Further detail on controls is available on request."],
 "support": [
  "Support is available 08:00 to 20:00 CET on working days with a 4-hour response for urgent issues, and an account manager is assigned to each customer.",
  "Orbit Digital has been operating for eleven years and has completed fourteen similar implementations for manufacturers. Five references are provided: Halden Components, Marlow Engineering, Tekna Plastics, Voss Automotive and Eastgate Textiles, each with a named contact role (Finance Director or Head of Procurement)."],
},
}

TERMS = [
    "This response is valid for 90 days from the submission date. Prices are quoted in US dollars and exclude applicable taxes. Payment terms are 30 days from invoice, with implementation fees invoiced against agreed milestones.",
    "The supplier confirms that it has read the RFP, accepts the evaluation process described in it, and will treat all Meridian Manufacturing information as confidential. Any exceptions to the draft contract will be listed during clarification."]

styles = getSampleStyleSheet()
body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=8)
h1 = ParagraphStyle("h1", parent=styles["Heading2"], spaceBefore=10, spaceAfter=4)


def table(rows, header=None, widths=(11 * cm, 5 * cm)):
    data = ([header] if header else []) + [list(r) for r in rows]
    t = Table(data, colWidths=widths)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]
    style += [("FONTNAME", (0, len(data) - 1), (-1, len(data) - 1), "Helvetica-Bold")] if rows and "Total" in rows[-1][0] else []
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.2 * cm, "FICTIONAL document created for a classroom exercise. Not a real supplier proposal.")
    canvas.drawRightString(19 * cm, 1.2 * cm, f"Page {doc.page}")


def build(filename, s):
    doc = SimpleDocTemplate(str(OUT / f"{filename}.pdf"), pagesize=A4, leftMargin=2 * cm,
                            rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title=f"{s['name']} - RFP Response", author=s["name"])
    story = [Paragraph(f"{s['name']}: Response to {REQUEST}", styles["Title"]), Spacer(1, 6)]

    def section(title, paras):
        story.append(Paragraph(title, h1))
        story.extend(Paragraph(p, body) for p in paras)

    section("1. Executive Summary and Understanding of the Requirement", s["summary"])
    section("2. Proposed Solution and Implementation Approach", s["solution"])
    story.append(PageBreak())
    story.append(Paragraph("3. Timeline, Team Structure and Milestones", h1))
    story.append(table(s["milestones"], header=["Milestone", "Target"], widths=(11 * cm, 5 * cm)))
    story.append(Spacer(1, 6))
    story.append(Paragraph(s["team"], body))
    story.append(Paragraph("4. Price Table and Assumptions", h1))
    story.append(table(s["price"], header=["Item", "Price"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Assumptions:</b> " + s["assumptions"], body))
    section("5. Security, Compliance and Risk Controls", s["security"])
    section("6. Support Model, Relevant Experience and References", s["support"])
    section("7. Commercial Terms and Validity", TERMS)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    for fname, data in SUPPLIERS.items():
        build(fname, data)
        print("Created", OUT / f"{fname}.pdf")
