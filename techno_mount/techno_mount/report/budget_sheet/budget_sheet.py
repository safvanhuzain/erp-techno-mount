# Copyright (c) 2026, safvanph41@gmail.com and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

# Must match get_columns() fieldnames and order (used to align row dicts with headers).
REPORT_ROW_KEYS = (
	"project",
	"purchase_invoice",
	"item_code",
	"qty_pi",
	"rate_pi",
	"amount_pi",
	"quotation",
	"qty_quotation",
	"rate_quotation",
	"amount_quotation",
)


def execute(filters=None):
	filters = filters or {}
	if not filters.get("company"):
		frappe.throw(_("Company is required"))

	columns = get_columns()
	detail_rows = [normalize_report_row(r) for r in fetch_detail_rows(filters)]
	by_project = group_by_project(detail_rows)
	data = build_tree_rows(filters["company"], by_project)

	return columns, data


def get_columns():
	def col(idx, d):
		d = dict(d)
		d["idx"] = idx
		return d

	return [
		col(
			1,
			{
				"label": _("Project"),
				"fieldname": "project",
				"fieldtype": "Link",
				"options": "Project",
				"width": 160,
			},
		),
		col(
			2,
			{
				"label": _("Purchase Invoice"),
				"fieldname": "purchase_invoice",
				"fieldtype": "Link",
				"options": "Purchase Invoice",
				"width": 150,
			},
		),
		col(
			3,
			{
				"label": _("Item"),
				"fieldname": "item_code",
				"fieldtype": "Link",
				"options": "Item",
				"width": 120,
			},
		),
		col(
			4,
			{
				"label": _("Qty (Purchase)"),
				"fieldname": "qty_pi",
				"fieldtype": "Float",
				"width": 100,
			},
		),
		col(
			5,
			{
				"label": _("Rate (Purchase)"),
				"fieldname": "rate_pi",
				"fieldtype": "Currency",
				"width": 120,
			},
		),
		col(
			6,
			{
				"label": _("Amount (Purchase)"),
				"fieldname": "amount_pi",
				"fieldtype": "Currency",
				"width": 120,
			},
		),
		col(
			7,
			{
				"label": _("Quotation"),
				"fieldname": "quotation",
				"fieldtype": "Data",
				"width": 220,
			},
		),
		col(
			8,
			{
				"label": _("Qty (Quotation)"),
				"fieldname": "qty_quotation",
				"fieldtype": "Float",
				"width": 100,
			},
		),
		col(
			9,
			{
				"label": _("Rate (Quotation)"),
				"fieldname": "rate_quotation",
				"fieldtype": "Currency",
				"width": 110,
			},
		),
		col(
			10,
			{
				"label": _("Amount (Quotation)"),
				"fieldname": "amount_quotation",
				"fieldtype": "Currency",
				"width": 120,
			},
		),
	]


def normalize_report_row(row):
	"""Exactly one key per report column; drop internal keys (e.g. pi_detail) so cells match headers."""
	out = {k: row.get(k) for k in REPORT_ROW_KEYS}
	if "indent" in row:
		out["indent"] = row["indent"]
	return out


def fetch_detail_rows(filters):
	conditions = ["q.company = %(company)s", "q.docstatus = 1"]
	values = {"company": filters["company"]}

	# Inner ON must not reference outer `q` — MySQL rejects q.company there.
	pi_date_conditions = ["pi.docstatus = 1"]
	if filters.get("from_date"):
		pi_date_conditions.append("pi.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		pi_date_conditions.append("pi.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	pi_inner_on = " AND ".join(pi_date_conditions)

	if filters.get("project"):
		conditions.append("NULLIF(TRIM(COALESCE(q.project, '')), '') = %(project)s")
		values["project"] = filters["project"]

	where_clause = " AND ".join(conditions)

	# Match PI lines to quotation lines by project (Quotation.project vs PI line / PI header)
	# and item code. Date range filters Purchase Invoice posting_date. Join via pii first to
	# avoid a Cartesian product with all company PIs.
	proj_q = "NULLIF(TRIM(COALESCE(q.project, '')), '')"
	proj_pi = (
		"NULLIF(TRIM(COALESCE("
		"NULLIF(TRIM(COALESCE(pii.project, '')), ''), "
		"NULLIF(TRIM(COALESCE(pi.project, '')), ''), "
		"''"
		")), '')"
	)

	# Purchase-only rows: PI lines with no matching submitted quotation line (same company,
	# item, project). Quotation columns stay NULL.
	pi_only_conditions = ["pi.company = %(company)s", pi_inner_on]
	if filters.get("project"):
		pi_only_conditions.append(f"{proj_pi} = %(project)s")
	where_pi_only = " AND ".join(pi_only_conditions)

	rows = frappe.db.sql(
		f"""
		(
			SELECT
				{proj_q} AS project_q,
				pii.name AS pi_detail,
				pi.name AS purchase_invoice,
				qi.item_code AS item_code,
				pii.qty AS qty_pi,
				pii.rate AS rate_pi,
				pii.amount AS amount_pi,
				q.name AS quotation,
				qi.qty AS qty_quotation,
				qi.rate AS rate_quotation,
				qi.amount AS amount_quotation
			FROM `tabQuotation` q
			INNER JOIN `tabQuotation Item` qi ON qi.parent = q.name
			LEFT JOIN (
				`tabPurchase Invoice Item` pii
				INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND {pi_inner_on}
			)
				ON pii.item_code = qi.item_code
				AND pi.company = q.company
				AND {proj_q} <=> {proj_pi}
			WHERE {where_clause}
		)
		UNION ALL
		(
			SELECT
				{proj_pi} AS project_q,
				pii.name AS pi_detail,
				pi.name AS purchase_invoice,
				pii.item_code AS item_code,
				pii.qty AS qty_pi,
				pii.rate AS rate_pi,
				pii.amount AS amount_pi,
				NULL AS quotation,
				NULL AS qty_quotation,
				NULL AS rate_quotation,
				NULL AS amount_quotation
			FROM `tabPurchase Invoice` pi
			INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
			WHERE {where_pi_only}
				AND NOT EXISTS (
					SELECT 1
					FROM `tabQuotation` q
					INNER JOIN `tabQuotation Item` qi ON qi.parent = q.name
					WHERE q.company = pi.company
						AND q.docstatus = 1
						AND qi.item_code = pii.item_code
						AND {proj_q} <=> {proj_pi}
				)
		)
		ORDER BY
			COALESCE(project_q, ''),
			purchase_invoice,
			item_code,
			quotation
		""",
		values,
		as_dict=True,
	)

	out = []
	for r in rows:
		pq = r.pop("project_q", None)
		r["project"] = (pq or "").strip()
		out.append(r)

	out = merge_rows_for_shared_purchase_line(out)
	return out


def merge_rows_for_shared_purchase_line(rows):
	"""One Purchase Invoice Item can match several quotation lines (same item + project).
	Repeat the PI side only once; combine quotation references and roll up qty / amount."""
	by_pi_detail = defaultdict(list)
	no_pi_key = []
	for r in rows:
		pid = r.get("pi_detail")
		if pid:
			by_pi_detail[pid].append(r)
		else:
			no_pi_key.append(r)

	merged = []
	for pid, group in by_pi_detail.items():
		if len(group) == 1:
			r0 = group[0]
			r0.pop("pi_detail", None)
			merged.append(r0)
			continue
		base = dict(group[0])
		quotes = []
		for x in group:
			qn = x.get("quotation")
			if qn and qn not in quotes:
				quotes.append(qn)
		tot_qqty = sum(flt(x.get("qty_quotation")) for x in group)
		tot_qamt = sum(flt(x.get("amount_quotation")) for x in group)
		base["quotation"] = ", ".join(quotes) if quotes else None
		base["qty_quotation"] = tot_qqty
		base["amount_quotation"] = tot_qamt
		base["rate_quotation"] = (tot_qamt / tot_qqty) if tot_qqty else None
		base.pop("pi_detail", None)
		merged.append(base)

	for r in no_pi_key:
		r.pop("pi_detail", None)
	merged.extend(no_pi_key)

	merged.sort(
		key=lambda x: (
			(x.get("project") or "").strip(),
			x.get("purchase_invoice") or "",
			x.get("item_code") or "",
			x.get("quotation") or "",
		)
	)
	return merged


def group_by_project(detail_rows):
	by_project = defaultdict(list)
	no_project_key = _("No Project")
	for row in detail_rows:
		key = (row.get("project") or "").strip() or no_project_key
		by_project[key].append(row)
	return by_project


def _blank_row():
	return {k: None for k in REPORT_ROW_KEYS}


def _parent_totals(children):
	tot_q = sum(flt(r.get("amount_quotation")) for r in children)
	tot_p = sum(flt(r.get("amount_pi")) for r in children)
	base = _blank_row()
	base["amount_quotation"] = tot_q
	base["amount_pi"] = tot_p
	return base


def _child_row(row):
	out = normalize_report_row(row)
	out["indent"] = 1
	out["project"] = None
	out["qty_pi"] = flt(row.get("qty_pi"))
	out["rate_pi"] = flt(row.get("rate_pi"))
	out["amount_pi"] = flt(row.get("amount_pi"))
	out["qty_quotation"] = flt(row.get("qty_quotation"))
	out["rate_quotation"] = flt(row.get("rate_quotation"))
	out["amount_quotation"] = flt(row.get("amount_quotation"))
	return out


def build_tree_rows(company, by_project):
	master_projects = frappe.get_all(
		"Project",
		filters={"company": company},
		pluck="name",
		order_by="name",
	)
	no_project_key = _("No Project")

	data = []

	for proj in master_projects:
		children = by_project.get(proj, [])
		data.append(
			normalize_report_row({"indent": 0, **_parent_totals(children), "project": proj})
		)
		for row in children:
			data.append(_child_row(row))

	for key in sorted(by_project.keys()):
		if key in master_projects:
			continue
		children = by_project[key]
		label = key if key != no_project_key else no_project_key
		data.append(
			normalize_report_row({"indent": 0, **_parent_totals(children), "project": label})
		)
		for row in children:
			data.append(_child_row(row))

	return data