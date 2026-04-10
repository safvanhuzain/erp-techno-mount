// Copyright (c) 2026, safvanph41@gmail.com and contributors
// For license information, please see license.txt

frappe.query_reports["Budget Sheet"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
			get_query: function () {
				let company =
					frappe.query_report.get_filter_value("company") ||
					frappe.defaults.get_user_default("Company");
				return {
					filters: { company: company },
				};
			},
		},
	],

	initial_depth: 0,

	formatter: function (value, row, column, data, default_formatter) {
		// Comma-separated quotation names (merged rows): one Link per name.
		if (
			column.fieldname === "quotation" &&
			data &&
			cint(data.indent) === 1 &&
			data.quotation
		) {
			const names = String(data.quotation)
				.split(",")
				.map((s) => s.trim())
				.filter(Boolean);
			if (names.length) {
				return names
					.map((name) => frappe.utils.get_form_link("Quotation", name, true, name))
					.join(", ");
			}
		}

		value = default_formatter(value, row, column, data);
		// Link fields: default_formatter returns real HTML — never escape_html here.
		if (data && cint(data.indent) === 0 && column.fieldname === "project" && value) {
			let $el = $(value);
			if ($el.is("a")) {
				$el.css("font-weight", "bold");
				value = $el.prop("outerHTML");
			} else {
				$el.find("a").css("font-weight", "bold");
				value = $el.length ? $el.html() : value;
			}
		}
		return value;
	},
};