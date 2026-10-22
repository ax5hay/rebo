"""Reference data, the organisation, and people (HR, payroll, time, talent)."""
from __future__ import annotations

import datetime as dt
import random

from h import *  # noqa: F403

_r = random.Random(11)
COUNTRIES = [("IN", "India", "INR", "Asia/Kolkata"), ("GB", "United Kingdom", "GBP", "Europe/London"),
             ("US", "United States", "USD", "America/Chicago"), ("DE", "Germany", "EUR", "Europe/Berlin"),
             ("FR", "France", "EUR", "Europe/Paris"), ("NL", "Netherlands", "EUR", "Europe/Amsterdam"),
             ("AU", "Australia", "AUD", "Australia/Sydney"), ("SG", "Singapore", "SGD", "Asia/Singapore"),
             ("AE", "United Arab Emirates", "AED", "Asia/Dubai"), ("JP", "Japan", "JPY", "Asia/Tokyo"),
             ("ES", "Spain", "EUR", "Europe/Madrid"), ("IE", "Ireland", "EUR", "Europe/Dublin")]
CURRENCIES = [("INR", "Indian Rupee", 1.0), ("USD", "US Dollar", 83.2), ("GBP", "Pound Sterling", 105.4),
              ("EUR", "Euro", 90.1), ("SGD", "Singapore Dollar", 61.8), ("AED", "UAE Dirham", 22.6),
              ("AUD", "Australian Dollar", 54.9), ("JPY", "Japanese Yen", 0.56)]


def _fx_rows():
    rows, d = [], START
    level = {c: r for c, _, r in CURRENCIES}
    while d <= END:
        if d.weekday() < 5:
            for c, _, _base in CURRENCIES[1:]:
                level[c] *= 1 + _r.gauss(0.00004, 0.0035)
                rows.append({"currency_code": c, "rate_date": d, "rate_to_inr": round(level[c], 4), "source": "RBI ref"})
        d += dt.timedelta(days=1)
    return rows


def _periods():
    rows = []
    for fy in range(2021, 2027):
        for m in range(12):
            month = (3 + m) % 12 + 1
            year = fy if month >= 4 else fy + 1
            start = dt.date(year, month, 1)
            end = (dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1))
            rows.append({"fiscal_year": f"FY{fy % 100:02d}-{(fy + 1) % 100:02d}", "period_no": m + 1,
                         "start_date": start, "end_date": end, "is_closed": end < dt.date(2026, 9, 1)})
    return rows


def _holidays():
    base = [("Republic Day", 1, 26), ("Holi", 3, 14), ("Independence Day", 8, 15), ("Gandhi Jayanti", 10, 2),
            ("Diwali", 11, 1), ("Christmas", 12, 25), ("May Day", 5, 1), ("Good Friday", 4, 18)]
    return [{"calendar_code": cal, "holiday_name": n, "holiday_date": dt.date(y, m, d)}
            for y in range(2021, 2027) for cal in ("IN-MH", "IN-KA", "UK", "DE", "US")
            for n, m, d in base if (cal.startswith("IN") or n in ("Christmas", "Good Friday", "May Day"))]


_ENTITY_COUNTRY = {1: "IN", 2: "GB", 3: "DE"}


def _on_payroll(e, run):
    """Employed by that entity's country during the run's month."""
    m = run["pay_month"]
    return (e["_c"] == _ENTITY_COUNTRY[run["legal_entity_id"]] and e["hire_date"] <= m
            and (e["exit_date"] is None or e["exit_date"] >= m) and e["employment_type"] in ("Permanent", "Contract"))


def _hire(r, g):
    return g.date(dt.date(2012, 1, 1), dt.date(2026, 9, 30), growth=1.9)


def _exit(r, g):
    h = r["hire_date"]
    if g.chance(0.17):
        return g.after(h, 120, 3000)
    return None


TABLES = [
    Table("country", 0, [col("iso_code", S(2)), col("country_name", S(80)), col("currency_code", S(3)), col("timezone", S(40))],
          fixed=[{"iso_code": c, "country_name": n, "currency_code": cur, "timezone": tz} for c, n, cur, tz in COUNTRIES]),
    Table("currency", 0, [col("currency_code", S(3)), col("currency_name", S(60)), col("decimals", I)],
          fixed=[{"currency_code": c, "currency_name": n, "decimals": 0 if c == "JPY" else 2} for c, n, _ in CURRENCIES]),
    Table("fx_rate", 0, [col("currency_code", S(3), index=True), col("rate_date", D, index=True), col("rate_to_inr", N4), col("source", S(20))],
          fixed=_fx_rows(), comment="Daily reference rate: 1 unit of the currency in INR"),
    Table("state_province", 0, [fk("country_id", "country"), col("state_code", S(5)), col("state_name", S(80))],
          fixed=[{"country_id": 1, "state_code": c, "state_name": n} for c, n in INDIAN_STATES]
          + [{"country_id": 2, "state_code": "ENG", "state_name": "England"}, {"country_id": 2, "state_code": "SCT", "state_name": "Scotland"},
             {"country_id": 3, "state_code": "TX", "state_name": "Texas"}, {"country_id": 3, "state_code": "CA", "state_name": "California"},
             {"country_id": 4, "state_code": "BY", "state_name": "Bavaria"}, {"country_id": 4, "state_code": "BE", "state_name": "Berlin"}]),
    lookup("uom", [("Each", "EA"), ("Kilogram", "KG"), ("Metre", "M"), ("Litre", "L"), ("Box", "BOX"), ("Roll", "ROLL"),
                   ("Hour", "HR"), ("Kilowatt hour", "KWH"), ("Set", "SET"), ("Pallet", "PLT")]),
    Table("fiscal_period", 0, [col("fiscal_year", S(9)), col("period_no", I), col("start_date", D), col("end_date", D), col("is_closed", B)],
          fixed=_periods(), comment="Indian fiscal year April-March; period 1 is April"),
    Table("holiday", 0, [col("calendar_code", S(10)), col("holiday_name", S(60)), col("holiday_date", D)], fixed=_holidays()),
    lookup("tax_code", [("GST 18%", "GST18"), ("GST 12%", "GST12"), ("GST 5%", "GST5"), ("GST 28%", "GST28"), ("IGST 18%", "IGST18"),
                        ("UK VAT 20%", "VAT20"), ("DE MwSt 19%", "MWST19"), ("US Sales tax", "SALESTX"), ("Zero rated export", "ZERO"),
                        ("UAE VAT 5%", "UAEVAT5")], {"rate_pct": [18.0, 12.0, 5.0, 28.0, 18.0, 20.0, 19.0, 7.5, 0.0, 5.0]}),
    lookup("payment_term", [("Immediate", "IMM"), ("Net 15", "N15"), ("Net 30", "N30"), ("Net 45", "N45"), ("Net 60", "N60"),
                            ("Net 90", "N90"), ("50% advance", "ADV50")], {"due_days": [0, 15, 30, 45, 60, 90, 30]}),
    lookup("incoterm", [("Ex Works", "EXW"), ("Free On Board", "FOB"), ("Cost Insurance Freight", "CIF"), ("Delivered Duty Paid", "DDP"),
                        ("Free Carrier", "FCA"), ("Delivered At Place", "DAP")]),
    lookup("industry", ["Electric utility", "Solar developer", "EV charging operator", "Real estate", "Manufacturing",
                        "Telecom towers", "Government", "Data centre", "Retail chain", "Hospital", "Education", "Logistics park",
                        "Oil and gas", "Hospitality"]),
    lookup("document_type", ["Invoice", "Credit note", "Purchase order", "Delivery note", "Contract", "Certificate",
                             "Test report", "Drawing", "Manual", "Policy"]),

    # ---- organisation -------------------------------------------------------------------------
    Table("legal_entity", 0, [col("entity_code", S(10)), col("legal_name", S(120)), fk("country_id", "country"),
                              col("functional_currency", S(3)), col("registration_no", S(40)), col("gstin", S(15)), col("vat_number", S(20)),
                              col("incorporated_on", D)],
          fixed=[{"entity_code": "OES-IN", "legal_name": "Orbitra Energy Systems Pvt Ltd", "country_id": 1, "functional_currency": "INR",
                  "registration_no": "U31904MH2009PTC195512", "gstin": "27AABCO4821K1Z5", "vat_number": None, "incorporated_on": dt.date(2009, 6, 12)},
                 {"entity_code": "OES-UK", "legal_name": "Orbitra Energy UK Ltd", "country_id": 2, "functional_currency": "GBP",
                  "registration_no": "11823044", "gstin": None, "vat_number": "GB318220471", "incorporated_on": dt.date(2017, 2, 3)},
                 {"entity_code": "OES-DE", "legal_name": "Orbitra Energy GmbH", "country_id": 4, "functional_currency": "EUR",
                  "registration_no": "HRB 231877", "gstin": None, "vat_number": "DE329184420", "incorporated_on": dt.date(2019, 9, 20)},
                 {"entity_code": "OES-US", "legal_name": "Orbitra Energy Inc.", "country_id": 3, "functional_currency": "USD",
                  "registration_no": "DE-7712093", "gstin": None, "vat_number": None, "incorporated_on": dt.date(2021, 1, 15)},
                 {"entity_code": "OES-SG", "legal_name": "Orbitra Energy Asia Pte Ltd", "country_id": 8, "functional_currency": "SGD",
                  "registration_no": "202014233K", "gstin": None, "vat_number": None, "incorporated_on": dt.date(2020, 4, 1)},
                 {"entity_code": "OES-AE", "legal_name": "Orbitra Energy Middle East FZE", "country_id": 9, "functional_currency": "AED",
                  "registration_no": "FZE-30188", "gstin": None, "vat_number": "100390211600003", "incorporated_on": dt.date(2022, 7, 7)}]),
    lookup("business_unit", [("Smart Metering", "SMT"), ("Solar Inverters", "SOL"), ("EV Charging", "EVC"), ("Grid Services", "GRD"),
                             ("Energy Cloud (SaaS)", "CLD"), ("Corporate", "CORP")]),
    Table("office_location", 0, [col("site_code", S(10)), col("site_name", S(80)), fk("legal_entity_id", "legal_entity"),
                                 col("city", S(60)), col("site_type", S(20)), col("opened_on", D)],
          fixed=[{"site_code": c, "site_name": n, "legal_entity_id": e, "city": ci, "site_type": t, "opened_on": dt.date(y, 4, 1)}
                 for c, n, e, ci, t, y in [("PUN-HQ", "Pune Headquarters", 1, "Pune", "office", 2009), ("PUN-P1", "Chakan Plant 1", 1, "Pune", "plant", 2012),
                                           ("BLR-RD", "Bengaluru R&D Centre", 1, "Bengaluru", "office", 2015), ("HSR-P2", "Hosur Plant 2", 1, "Hosur", "plant", 2019),
                                           ("DEL-SO", "Gurugram Sales Office", 1, "Gurugram", "office", 2014), ("MUM-WH", "Bhiwandi Warehouse", 1, "Bhiwandi", "warehouse", 2016),
                                           ("CHN-WH", "Chennai Warehouse", 1, "Chennai", "warehouse", 2020), ("HYD-SC", "Hyderabad Service Centre", 1, "Hyderabad", "service", 2018),
                                           ("LON-OF", "London Office", 2, "London", "office", 2017), ("MAN-WH", "Manchester Depot", 2, "Manchester", "warehouse", 2021),
                                           ("BER-OF", "Berlin Office", 3, "Berlin", "office", 2019), ("AUS-OF", "Austin Office", 4, "Austin", "office", 2021),
                                           ("SIN-OF", "Singapore Office", 5, "Singapore", "office", 2020), ("DXB-OF", "Dubai Office", 6, "Dubai", "office", 2022),
                                           ("KOL-SC", "Kolkata Service Centre", 1, "Kolkata", "service", 2022), ("AHM-SC", "Ahmedabad Service Centre", 1, "Ahmedabad", "service", 2023)]]),
    Table("department", 0, [col("dept_code", S(10)), col("dept_name", S(80)), fk("business_unit_id", "business_unit", null=0.3)],
          fixed=[{"dept_code": c, "dept_name": n, "business_unit_id": bu} for c, n, bu in [
              ("SAL", "Sales", None), ("MKT", "Marketing", None), ("FIN", "Finance", 6), ("HR", "Human Resources", 6), ("IT", "Information Technology", 6),
              ("ENG", "Engineering", None), ("RND", "Research and Development", None), ("MFG", "Manufacturing", None), ("QA", "Quality Assurance", None),
              ("SCM", "Supply Chain", None), ("PRC", "Procurement", 6), ("LOG", "Logistics", None), ("FSV", "Field Service", None),
              ("SUP", "Customer Support", None), ("PMO", "Project Management", None), ("LEG", "Legal and Compliance", 6), ("ADM", "Administration", 6),
              ("ESG", "Sustainability", 6), ("CLD", "Cloud Platform", 5), ("DAT", "Data and Analytics", 6)]]),
    Table("cost_center", 0, [col("cc_code", S(12)), col("cc_name", S(80)), fk("department_id", "department"), fk("office_location_id", "office_location"),
                             col("is_active", B)],
          fixed=[{"cc_code": f"CC{d:02d}{s:02d}", "cc_name": f"{dn} - {sn}", "department_id": d, "office_location_id": s, "is_active": (d * s) % 11 != 0}
                 for d, dn in enumerate(["Sales", "Marketing", "Finance", "HR", "IT", "Engineering", "R&D", "Manufacturing", "Quality", "Supply Chain",
                                         "Procurement", "Logistics", "Field Service", "Support", "PMO", "Legal", "Admin", "ESG", "Cloud", "Data"], 1)
                 for s, sn in [(1, "Pune"), (3, "Bengaluru"), (9, "London"), (11, "Berlin")] if (d + s) % 3 != 0 or s == 1]),
    lookup("job_grade", [("G1 Associate", "G1"), ("G2 Senior Associate", "G2"), ("G3 Specialist", "G3"), ("G4 Lead", "G4"), ("G5 Manager", "G5"),
                         ("G6 Senior Manager", "G6"), ("G7 Director", "G7"), ("G8 Vice President", "G8"), ("G9 CXO", "G9")],
           {"min_ctc_inr": [350000, 600000, 900000, 1400000, 2200000, 3200000, 4800000, 7000000, 12000000],
            "max_ctc_inr": [650000, 1000000, 1500000, 2400000, 3500000, 5200000, 7500000, 12000000, 30000000]}),
    Table("position", 160, [col("title", S(80), ch(["Sales Executive", "Key Account Manager", "Inside Sales Rep", "Field Engineer", "Service Technician",
                                                   "Firmware Engineer", "Hardware Engineer", "Data Engineer", "QA Inspector", "Production Supervisor",
                                                   "Machine Operator", "Buyer", "Planner", "Warehouse Associate", "Accountant", "Financial Analyst",
                                                   "HR Business Partner", "Recruiter", "Project Manager", "Support Agent", "Solutions Architect",
                                                   "Marketing Manager", "Content Specialist", "Legal Counsel", "IT Administrator", "DevOps Engineer"])),
                            fk("department_id", "department"), fk("job_grade_id", "job_grade", skew=0.8), col("headcount_budget", I, rng(1, 25)),
                            col("is_open", B, yes(0.22))]),
    Table("employee", 3400, [
        cc(), col("_c", S(2), lambda r, g: g.pick(["IN", "GB", "DE", "US", "SG", "AE"], [82, 6, 4, 4, 2, 2])),
        col("employee_code", S(12), code("ORB", 5), unique=True),
        col("gender", S(12), lambda r, g: g.pick(["Male", "Female", "Non-binary", "Undisclosed"], [57, 40, 1, 2])),
        col("first_name", S(60), lambda r, g: (r.__setitem__("_cc", r["_c"]) or person_name("first")(r, g))),
        col("last_name", S(60), person_name("last")), col("work_email", S(120), email_of("orbitra.energy")),
        col("personal_email", S(120), email_of(), null=0.3), col("mobile", S(30), phone()),
        col("date_of_birth", D, lambda r, g: g.date(dt.date(1965, 1, 1), dt.date(2003, 12, 31), growth=1.0)),
        col("hire_date", D, _hire), col("exit_date", D, _exit),
        col("employment_type", S(20), ch(["Permanent", "Contract", "Intern", "Consultant"], [84, 10, 4, 2])),
        fk("position_id", "position"), fk("department_id", "department"),
        fk("office_location_id", "office_location", where=lambda p, r: (p["legal_entity_id"] == 1) == (r["_c"] == "IN")),
        fk("cost_center_id", "cost_center"), fk("manager_id", "employee", null=0.03, declare=False),
        col("pan_number", S(10), lambda r, g: pan("P")(r, g) if r["_c"] == "IN" else None),
        col("bank_account_no", S(24), lambda r, g: str(g.int(10 ** 11, 10 ** 12 - 1))), col("ifsc_code", S(11), lambda r, g: ifsc()(r, g) if r["_c"] == "IN" else None),
        col("status", S(16), lambda r, g: "Exited" if r["exit_date"] else g.pick(["Active", "On leave", "Notice period"], [93, 4, 3])),
    ], comment="People employed by any Orbitra entity",
       post=["UPDATE employee SET manager_id = (SELECT MIN(m.employee_id) FROM employee m WHERE m.department_id = employee.department_id "
             "AND m.employee_id < employee.employee_id AND m.employee_id % 9 = 1)"]),
    Table("emergency_contact", 0, [fk("employee_id", "employee"), cc("@employee_id._cc"), col("contact_name", S(120), fake("name")),
                                   col("relationship", S(20), ch(["Spouse", "Parent", "Sibling", "Friend"], [50, 35, 10, 5])), col("phone", S(30), phone())],
          per=("employee", 1, 2)),
    Table("employee_address", 0, [fk("employee_id", "employee"), cc("@employee_id._c"), col("address_type", S(12), ch(["Current", "Permanent"])),
                                  col("line1", S(160), street()), col("city", S(80), city()), col("postcode", S(12), postcode()),
                                  col("country_code", S(2), copy("_cc"))], per=("employee", 1, 2)),
    lookup("salary_component", [("Basic", "BASIC"), ("House Rent Allowance", "HRA"), ("Special Allowance", "SPL"), ("Conveyance", "CONV"),
                                ("Provident Fund (employee)", "PF_EE"), ("Professional Tax", "PT"), ("Income Tax (TDS)", "TDS"),
                                ("Performance Bonus", "BONUS"), ("Overtime", "OT"), ("Shift Allowance", "SHIFT")],
           {"is_deduction": [False, False, False, False, True, True, True, False, False, False]}),
    Table("compensation", 0, [fk("employee_id", "employee"), col("effective_from", D, lambda r, g: g.after(r["@employee_id"]["hire_date"], 0, 0) if r["_i"] % 3 else g.after(r["@employee_id"]["hire_date"], 365, 1800)),
                              col("currency", S(3), lambda r, g: CURRENCY.get(r["@employee_id"]["_c"], "INR")),
                              col("annual_ctc", N, lambda r, g: round(local(g.normal(1600000, 900000, 300000, 25000000) * (1 if r["currency"] == "INR" else 3.2), r["currency"]), -2)),
                              col("change_reason", S(30), ch(["Joining", "Annual revision", "Promotion", "Market correction"], [30, 50, 15, 5]))],
          per=("employee", 1, 4)),
    Table("payroll_run", 0, [col("pay_month", D), fk("legal_entity_id", "legal_entity"), col("run_status", S(12)), col("processed_at", TS)],
          fixed=[{"pay_month": dt.date(y, m, 1), "legal_entity_id": e, "run_status": "Locked" if dt.date(y, m, 1) < dt.date(2026, 10, 1) else "Draft",
                  "processed_at": dt.datetime(y, m, 26 if m != 2 else 25, 18, 30)}
                 for e in (1, 2, 3) for y in range(2025, 2027) for m in range(1, 13) if dt.date(2025, 4, 1) <= dt.date(y, m, 1) <= dt.date(2026, 9, 1)]),
    Table("payslip", 0, [fk("payroll_run_id", "payroll_run"),
                         col("employee_id", I, draw("employee", _on_payroll), index=True),
                         col("gross_pay", N, lambda r, g: round(g.normal(120000, 70000, 22000, 1500000), 0) if r["@parent"]["legal_entity_id"] == 1
                             else round(g.normal(4800, 1800, 1900, 25000), 0)),
                         col("deductions", N, lambda r, g: round(r["gross_pay"] * g.normal(0.17, 0.05, 0.04, 0.38), 0)),
                         col("net_pay", N, lambda r, g: r["gross_pay"] - r["deductions"]), col("paid_on", D, lambda r, g: g.after(r["@payroll_run_id"]["pay_month"], 29, 31)),
                         col("payment_mode", S(16), lambda r, g: g.pick(["NEFT", "IMPS", "Cheque"], [92, 7, 1]) if r["@parent"]["legal_entity_id"] == 1 else "Bank transfer")],
          per=("payroll_run", pool_size("employee", _on_payroll)), comment="One payslip per employee on the payroll in that month"),
    Table("payslip_line", 0, [fk("payslip_id", "payslip"), fk("salary_component_id", "salary_component"), col("amount", N, money(500, 90000, 10))],
          per=("payslip", 3, 5)),
    lookup("leave_type", [("Casual leave", "CL"), ("Sick leave", "SL"), ("Earned leave", "EL"), ("Maternity leave", "ML"),
                          ("Paternity leave", "PL"), ("Loss of pay", "LOP"), ("Work from home", "WFH"), ("Comp off", "CO")],
           {"annual_quota": [8, 8, 18, 182, 10, 0, 24, 0]}),
    Table("leave_request", 21000, [fk("employee_id", "employee", skew=0.2), fk("leave_type_id", "leave_type"),
                                   col("from_date", D, when(dt.date(2023, 1, 1))), col("to_date", D, after("from_date", 0, 6)),
                                   col("days", N, lambda r, g: float(((r["to_date"] or r["from_date"]) - r["from_date"]).days + 1)),
                                   col("reason", S(200), words(3, 9), null=0.4), fk("approver_id", "employee", declare=False),
                                   col("status", S(12), age_status("from_date", [(20, ["Approved", "Rejected", "Cancelled"], [88, 6, 6])], "Pending")),
                                   col("applied_at", TS, lambda r, g: g.ts(g.after(r["from_date"], -20, -1) or r["from_date"]))]),
    Table("attendance_record", 60000, [fk("employee_id", "employee", skew=0.1), col("work_date", D, when(dt.date(2025, 4, 1), growth=1.0)),
                                       col("check_in", TS, lambda r, g: dt.datetime.combine(r["work_date"], dt.time(g.int(8, 10), g.int(0, 59)))),
                                       col("check_out", TS, lambda r, g: r["check_in"] + dt.timedelta(minutes=g.int(300, 660)), null=0.03),
                                       col("source", S(12), ch(["Biometric", "Mobile app", "Manual"], [70, 25, 5])),
                                       col("is_wfh", B, yes(0.18))]),
    lookup("shift", [("General 09:00-18:00", "GEN"), ("Morning 06:00-14:00", "A"), ("Evening 14:00-22:00", "B"), ("Night 22:00-06:00", "C")]),
    Table("shift_assignment", 7000, [fk("employee_id", "employee"), fk("shift_id", "shift"), col("valid_from", D, when(dt.date(2024, 1, 1))),
                                     col("valid_to", D, after("valid_from", 30, 180))]),
    Table("performance_cycle", 0, [col("cycle_name", S(30)), col("starts_on", D), col("ends_on", D), col("is_current", B)],
          fixed=[{"cycle_name": f"FY{y % 100:02d}-{(y + 1) % 100:02d} Annual", "starts_on": dt.date(y, 4, 1), "ends_on": dt.date(y + 1, 3, 31),
                  "is_current": y == 2026} for y in range(2021, 2027)]),
    Table("performance_review", 9000, [fk("employee_id", "employee"), fk("performance_cycle_id", "performance_cycle"), fk("reviewer_id", "employee", declare=False),
                                       col("rating", I, lambda r, g: g.pick([1, 2, 3, 4, 5], [3, 12, 50, 28, 7])),
                                       col("rating_label", S(30), lambda r, g: ["Below expectations", "Partially meets", "Meets expectations", "Exceeds expectations", "Outstanding"][r["rating"] - 1]),
                                       col("promotion_recommended", B, lambda r, g: r["rating"] >= 4 and g.chance(0.4)),
                                       col("submitted_on", D, lambda r, g: g.after(r["@performance_cycle_id"]["ends_on"], 10, 60))]),
    Table("goal", 14000, [fk("employee_id", "employee"), fk("performance_cycle_id", "performance_cycle"), col("goal_title", S(160), words(4, 9)),
                          col("weight_pct", I, ch([10, 15, 20, 25, 30])), col("progress_pct", I, rng(0, 100)),
                          col("status", S(12), ch(["On track", "At risk", "Achieved", "Missed", "Dropped"], [35, 15, 35, 10, 5]))]),
    Table("training_course", 140, [col("course_code", S(12), code("TRN", 4)), col("course_title", S(140), lambda r, g: g.pick(
        ["Safety at height", "Electrical safety (LOTO)", "POSH awareness", "Advanced Excel", "Solar inverter commissioning", "EV charger installation",
         "Smart meter firmware basics", "Negotiation skills", "First-time managers", "Information security", "Lean manufacturing", "ISO 9001 internal auditor",
         "Customer empathy", "Power BI for analysts", "Kubernetes fundamentals", "GST for finance teams"]) + f" ({r['_i']})"),
        col("mode", S(12), ch(["Classroom", "Online", "On the job"], [30, 60, 10])), col("duration_hours", N, ch([2.0, 4.0, 8.0, 16.0, 24.0, 40.0])),
        col("is_mandatory", B, yes(0.2)), col("cost_per_seat_inr", N, money(0, 45000, 500))]),
    Table("training_enrollment", 18000, [fk("employee_id", "employee"), fk("training_course_id", "training_course", skew=0.6),
                                         col("enrolled_on", D, when(dt.date(2022, 1, 1))), col("completed_on", D, after("enrolled_on", 1, 90), null=0.22),
                                         col("score_pct", I, lambda r, g: g.int(45, 100) if r["completed_on"] else None),
                                         col("status", S(12), lambda r, g: "Completed" if r["completed_on"] else g.pick(["Enrolled", "In progress", "Dropped"], [40, 45, 15]))]),
    Table("skill", 0, [col("skill_name", S(60)), col("category", S(30))],
          fixed=[{"skill_name": s, "category": c} for c, ss in {
              "Technical": ["PCB design", "Embedded C", "Power electronics", "Python", "SQL", "React", "Kubernetes", "PLC programming", "AutoCAD", "SAP MM"],
              "Field": ["HT panel work", "Meter installation", "Inverter commissioning", "Charger installation", "Fault diagnosis"],
              "Business": ["Negotiation", "Key account management", "Contract drafting", "Budgeting", "GST compliance"],
              "Language": ["Hindi", "Marathi", "Tamil", "German", "Arabic"]}.items() for s in ss]),
    Table("employee_skill", 0, [fk("employee_id", "employee"), fk("skill_id", "skill"), col("level", S(12), ch(["Beginner", "Intermediate", "Advanced", "Expert"], [25, 40, 25, 10]))],
          per=("employee", 0, 4)),
    Table("job_requisition", 900, [fk("position_id", "position"), fk("hiring_manager_id", "employee", declare=False), col("opened_on", D, when(dt.date(2023, 1, 1))),
                                   col("closed_on", D, after("opened_on", 15, 160), null=0.25), col("openings", I, ch([1, 1, 1, 2, 3, 5])),
                                   col("status", S(12), lambda r, g: "Filled" if r["closed_on"] and g.chance(0.85) else "Cancelled" if r["closed_on"] else g.pick(["Open", "On hold"], [85, 15]))]),
    Table("candidate", 9000, [cc(), col("first_name", S(60), person_name("first")), col("last_name", S(60), person_name("last")),
                              col("email", S(120), email_of()), col("phone", S(30), phone()), col("source", S(20), ch(["LinkedIn", "Naukri", "Referral", "Campus", "Agency", "Careers page"], [30, 30, 15, 10, 8, 7])),
                              col("current_ctc", N, money(200000, 6000000, 10000), null=0.2), col("notice_period_days", I, ch([0, 15, 30, 60, 90], [10, 10, 35, 25, 20]))]),
    Table("job_application", 15000, [fk("candidate_id", "candidate"), fk("job_requisition_id", "job_requisition", skew=0.4), col("applied_on", D, lambda r, g: g.after(r["@job_requisition_id"]["opened_on"], 0, 60)),
                                      col("stage", S(16), ch(["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected", "Withdrawn"], [20, 15, 12, 4, 6, 38, 5]))]),
    Table("interview", 12000, [fk("job_application_id", "job_application"), fk("interviewer_id", "employee", declare=False), col("round_no", I, rng(1, 4)),
                               col("scheduled_at", TS, lambda r, g: g.ts(g.after(r["@job_application_id"]["applied_on"], 3, 30))),
                               col("feedback", S(20), ch(["Strong hire", "Hire", "No hire", "Strong no hire", "No show"], [10, 30, 40, 12, 8]))]),
    Table("offer_letter", 1300, [fk("job_application_id", "job_application"), col("offered_ctc", N, money(300000, 9000000, 10000)), col("offered_on", D, lambda r, g: g.after(r["@job_application_id"]["applied_on"], 10, 70)),
                                 col("joining_date", D, after("offered_on", 15, 95)), col("status", S(12), ch(["Accepted", "Declined", "Pending", "Revoked"], [68, 20, 8, 4]))]),
    Table("exit_interview", 500, [fk("employee_id", "employee", where=lambda p, r: p["exit_date"] is not None), col("reason", S(40), ch(
        ["Better compensation", "Career growth", "Relocation", "Higher studies", "Manager", "Work-life balance", "Retirement", "Terminated"], [30, 20, 12, 8, 10, 10, 3, 7])),
        col("would_rejoin", B, yes(0.55)), col("comments", S(300), words(6, 18), null=0.3)]),
    Table("expense_claim", 16000, [fk("employee_id", "employee", skew=0.5), col("claim_date", D, when(dt.date(2022, 4, 1))), col("purpose", S(160), words(3, 8)),
                                   col("currency", S(3), lambda r, g: CURRENCY.get(r["@employee_id"]["_c"], "INR")), col("total_amount", N, const(0)),
                                   col("status", S(14), age_status("claim_date", [(45, ["Reimbursed", "Rejected"], [92, 8]), (10, ["Approved", "Submitted", "Rejected"], [55, 35, 10])], "Draft")),
                                   fk("approver_id", "employee", declare=False)],
          post=["UPDATE expense_claim SET total_amount = COALESCE((SELECT SUM(l.amount) FROM expense_line l WHERE l.expense_claim_id = expense_claim.expense_claim_id), 0)"]),
    Table("expense_line", 0, [fk("expense_claim_id", "expense_claim"), col("category", S(20), ch(["Travel", "Hotel", "Meals", "Local conveyance", "Client entertainment", "Mobile", "Training"], [25, 20, 25, 15, 5, 5, 5])),
                              col("spent_on", D, copy("@expense_claim_id.claim_date")), col("amount", N, money_in("@expense_claim_id.currency", 150, 42000, 10)), col("has_receipt", B, yes(0.9))],
          per=("expense_claim", 1, 6)),
    Table("travel_request", 4200, [fk("employee_id", "employee"), col("from_city", S(60), ch(["Pune", "Bengaluru", "Mumbai", "Delhi", "London", "Berlin"])),
                                   col("to_city", S(60), ch(["Chennai", "Hyderabad", "Dubai", "Singapore", "Frankfurt", "Austin", "Kolkata", "Ahmedabad", "Jaipur"])),
                                   col("depart_on", D, when(dt.date(2022, 4, 1))), col("return_on", D, after("depart_on", 1, 12)),
                                   col("mode", S(10), ch(["Flight", "Train", "Car"], [70, 20, 10])), col("estimated_cost_inr", N, money(3000, 450000, 100)),
                                   col("status", S(12), ch(["Approved", "Rejected", "Pending", "Completed"], [20, 6, 4, 70]))]),
]
