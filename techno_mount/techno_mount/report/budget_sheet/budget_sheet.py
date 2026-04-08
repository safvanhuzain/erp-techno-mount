# Copyright (c) 2026, safvanph41@gmail.com and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	if not filters.get("company"):
		frappe.throw(_("Company is required"))

	columns = get_columns()
	detail_rows = fetch_detail_rows(filters)
	by_project = group_by_project(detail_rows)
	data = build_tree_rows(filters["company"], by_project)

	return columns, data


def get_columns():
	return [
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 160,
		},
		{
			"label": _("Quotation"),
			"fieldname": "quotation",
			"fieldtype": "Link",
			"options": "Quotation",
			"width": 130,
		},
		{
			"label": _("Item"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Qty (Quotation)"),
			"fieldname": "qty_quotation",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Rate (Quotation)"),
			"fieldname": "rate_quotation",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Amount (Quotation)"),
			"fieldname": "amount_quotation",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Sales Invoice"),
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 140,
		},
		{
			"label": _("Qty (Sales)"),
			"fieldname": "qty_si",
			"fieldtype": "Float",
			"width": 90,
		},
		{
			"label": _("Rate (Sales)"),
			"fieldname": "rate_si",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": _("Amount (Sales)"),
			"fieldname": "amount_si",
			"fieldtype": "Currency",
			"width": 110,
		},
	]


def fetch_detail_rows(filters):
	conditions = ["si.company = %(company)s", "si.docstatus = 1"]
	values = {"company": filters["company"]}

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("project"):
		conditions.append(
			"(NULLIF(TRIM(si.project), '') = %(project)s OR NULLIF(TRIM(so.project), '') = %(project)s)"
		)
		values["project"] = filters["project"]

	where_clause = " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT
			NULLIF(TRIM(COALESCE(si.project, '')), '') AS project_si,
			NULLIF(TRIM(COALESCE(so.project, '')), '') AS project_so,
			soi.prevdoc_docname AS quotation,
			COALESCE(qi.item_code, sii.item_code) AS item_code,
			qi.qty AS qty_quotation,
			qi.rate AS rate_quotation,
			qi.amount AS amount_quotation,
			si.name AS sales_invoice,
			sii.qty AS qty_si,
			sii.rate AS rate_si,
			sii.amount AS amount_si
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN `tabSales Order` so ON so.name = sii.sales_order
		LEFT JOIN `tabSales Order Item` soi ON soi.name = sii.so_detail
		LEFT JOIN `tabQuotation Item` qi ON qi.name = soi.quotation_item
		WHERE {where_clause}
		ORDER BY
			COALESCE(
				NULLIF(TRIM(COALESCE(si.project, '')), ''),
				NULLIF(TRIM(COALESCE(so.project, '')), ''),
				''
			),
			soi.prevdoc_docname,
			si.name,
			sii.idx
		""",
		values,
		as_dict=True,
	)

	out = []
	for r in rows:
		p_si = r.pop("project_si", None)
		p_so = r.pop("project_so", None)
		r["project"] = (p_si or p_so or "").strip()
		out.append(r)
	return out


def group_by_project(detail_rows):
	by_project = defaultdict(list)
	no_project_key = _("No Project")
	for row in detail_rows:
		key = (row.get("project") or "").strip() or no_project_key
		by_project[key].append(row)
	return by_project


def _blank_row():
	return {
		"quotation": None,
		"item_code": None,
		"qty_quotation": None,
		"rate_quotation": None,
		"amount_quotation": None,
		"sales_invoice": None,
		"qty_si": None,
		"rate_si": None,
		"amount_si": None,
	}


def _parent_totals(children):
	tot_q = sum(flt(r.get("amount_quotation")) for r in children)
	tot_s = sum(flt(r.get("amount_si")) for r in children)
	base = _blank_row()
	base["amount_quotation"] = tot_q
	base["amount_si"] = tot_s
	return base


def _child_row(row):
	return {
		"indent": 1,
		"project": None,
		"quotation": row.get("quotation"),
		"item_code": row.get("item_code"),
		"qty_quotation": flt(row.get("qty_quotation")),
		"rate_quotation": flt(row.get("rate_quotation")),
		"amount_quotation": flt(row.get("amount_quotation")),
		"sales_invoice": row.get("sales_invoice"),
		"qty_si": flt(row.get("qty_si")),
		"rate_si": flt(row.get("rate_si")),
		"amount_si": flt(row.get("amount_si")),
	}


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
		data.append({"indent": 0, "project": proj, **_parent_totals(children)})
		for row in children:
			data.append(_child_row(row))

	for key in sorted(by_project.keys()):
		if key in master_projects:
			continue
		children = by_project[key]
		label = key if key != no_project_key else no_project_key
		data.append({"indent": 0, "project": label, **_parent_totals(children)})
		for row in children:
			data.append(_child_row(row))

	return data