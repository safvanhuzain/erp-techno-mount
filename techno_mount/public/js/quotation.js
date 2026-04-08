frappe.ui.form.on('Quotation', {
    refresh: function(frm) {
        setButtonColor(frm);
    },
    custom_fetch_items_from_costing_sheet: function (frm) {
        let costing_rows = frm.doc.custom_cost_sheet || [];
        if (!costing_rows.length) {
            frappe.msgprint(__("Add lines to the costing sheet first."));
            return;
        }
    
        // Optional: replace all quotation items (remove if you want to append instead)
        frappe.model.clear_table(frm.doc, "items");
    
        let cdt = "Quotation Item";
    
        costing_rows.forEach(function (cr) {
            if (!cr.item) {
                return;
            }
            let pr_item = frappe.model.add_child(frm.doc, "items");
            pr_item.item_code = cr.item;
            pr_item.qty = cr.area || 0;
            pr_item.rate = cr.budget_cost_per_unit + (cr.profit_markup/100 * cr.budget_cost_per_unit);
            pr_item.amount = cr.area * pr_item.rate;
            frappe.db.get_value('Item', cr.item, ['item_name', 'stock_uom'])
                .then((r) => {
                    if (r.message) {
                        pr_item.item_name = r.message.item_name;
                        pr_item.uom = r.message.stock_uom;
                    }

                    // refresh inside async
                    frm.refresh_field("items");
            });
        });
    
        // frm.refresh_field("items");
    
        // Quotation usually recalculates totals/taxes from items; trigger if your version needs it
        // if (frm.cscript && typeof frm.cscript.calculate_taxes_and_totals === "function") {
        //     frm.cscript.calculate_taxes_and_totals();
        // }
    },
});

frappe.ui.form.on('Quotation Costing Sheet', {
    custom_cost_sheet_add: function(frm, cdt, cdn) {
        console.log("lllll");
        setButtonColor(frm);
    }
});

function setButtonColor(frm) {

    setTimeout(function () {

        if (!frm.fields_dict.custom_cost_sheet) return;

        frm.fields_dict.custom_cost_sheet.grid.wrapper
            .find('[data-fieldname="edit_costing"] button')
            .css({
                "background-color": "black",
                "color": "white",
                "border-color": "black"
            });

    }, 300);

}

function get_costing_dialog_fields(row) {
    return [
        {fieldtype:"Section Break", label:"Material & Labor"},
        {fieldname:"item", label:"Item Name", fieldtype:"Link", options:"Item", default:row.item},
        {fieldname:"material_qty", label:"Material Qty", fieldtype:"Float", default:row.material_qty},
        {fieldname:"material_rate", label:"Material Rate", fieldtype:"Currency", default:row.material_rate},
        {fieldname:"material_budget_cost", label:"Material Budget Cost", fieldtype:"Currency", default:row.material_budget_cost},

        {fieldtype:"Column Break"},
        {fieldname:"labor_qty", label:"Labor Qty", fieldtype:"Float", default:row.labor_qty},
        {fieldname:"labor_rate", label:"Labor Rate", fieldtype:"Currency", default:row.labor_rate},
        {fieldname:"labor_budget_cost", label:"Labor Budget Cost", fieldtype:"Currency", default:row.labor_budget_cost},

        {fieldtype:"Section Break", label:"Equipment Rental & Subcontracting"},
        {fieldname:"equipment_qty", label:"Equipment Qty", fieldtype:"Float", default:row.equipment_qty},
        {fieldname:"equipment_rate", label:"Equipment Rate", fieldtype:"Currency", default:row.equipment_rate},
        {fieldname:"equipment_budget_cost", label:"Equipment Budget Cost", fieldtype:"Currency", default:row.equipment_budget_cost},

        {fieldtype:"Column Break"},
        {fieldname:"sub_qty", label:"Subcontracting Qty", fieldtype:"Float", default:row.sub_qty},
        {fieldname:"sub_rate", label:"Subcontracting Rate", fieldtype:"Currency", default:row.sub_rate},
        {fieldname:"sub_budget_cost", label:"Subcontracting Budget Cost", fieldtype:"Currency", default:row.sub_budget_cost},

        {fieldtype:"Section Break", label:"Total Budget Cost"},
        {fieldname:"area", label:"Area", fieldtype:"Float", default:row.area},

        {fieldtype:"Column Break"},
        {fieldname:"profit_markup", label:"Profit Markup", fieldtype:"Percent", default:row.profit_markup},
    ];
}

function apply_costing_dialog_to_row(frm, values, cdt, cdn) {
    let row = locals[cdt][cdn];

    let material_budget = (values.material_qty || 0) * (values.material_rate || 0);
    let labor_budget = (values.labor_qty || 0) * (values.labor_rate || 0);
    let equipment_budget = (values.equipment_qty || 0) * (values.equipment_rate || 0);
    let sub_budget = (values.sub_qty || 0) * (values.sub_rate || 0);
    let area = values.area || 0;

    let total_budget =
        material_budget +
        labor_budget +
        equipment_budget +
        sub_budget;

    if (!area && frm.doc.items && frm.doc.items.length) {
        area = frm.doc.items[0].qty || 0;
    }

    let budget_per_unit = 0;
    if (area > 0) {
        budget_per_unit = total_budget / area;
    }

    frappe.model.set_value(cdt, cdn, "item", values.item);
    frappe.model.set_value(cdt, cdn, "material_qty", values.material_qty);
    frappe.model.set_value(cdt, cdn, "material_rate", values.material_rate);
    frappe.model.set_value(cdt, cdn, "material_budget_cost", material_budget);

    frappe.model.set_value(cdt, cdn, "labor_qty", values.labor_qty);
    frappe.model.set_value(cdt, cdn, "labor_rate", values.labor_rate);
    frappe.model.set_value(cdt, cdn, "labor_budget_cost", labor_budget);

    frappe.model.set_value(cdt, cdn, "equipment_qty", values.equipment_qty);
    frappe.model.set_value(cdt, cdn, "equipment_rate", values.equipment_rate);
    frappe.model.set_value(cdt, cdn, "equipment_budget_cost", equipment_budget);

    frappe.model.set_value(cdt, cdn, "sub_qty", values.sub_qty);
    frappe.model.set_value(cdt, cdn, "sub_rate", values.sub_rate);
    frappe.model.set_value(cdt, cdn, "sub_budget_cost", sub_budget);

    frappe.model.set_value(cdt, cdn, "area", values.area);
    frappe.model.set_value(cdt, cdn, "total_budget_cost", total_budget);
    frappe.model.set_value(cdt, cdn, "budget_cost_per_unit", budget_per_unit);
    frappe.model.set_value(cdt, cdn, "profit_markup", values.profit_markup);
}

function open_edit_costing_dialog(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let dialog = new frappe.ui.Dialog({
        title: "Edit Costing",
        size: "large",
        fields: get_costing_dialog_fields(row),

        primary_action_label: __("Apply"),
        primary_action(values) {
            apply_costing_dialog_to_row(frm, values, cdt, cdn);
            dialog.hide();
        },

        secondary_action_label: __("Next"),
        secondary_action() {
            // Unlike primary_action, the secondary button does not call get_values() for you.
            let values = dialog.get_values();
            if (!values) {
                return;
            }
            apply_costing_dialog_to_row(frm, values, cdt, cdn);

            let parentfield = locals[cdt][cdn].parentfield;
            if (!parentfield) {
                frappe.throw(__("Missing parent field on costing row; cannot add next line."));
            }
            // frm.add_child(fieldname) uses meta lookup which can fail for some custom Table fields
            let new_row = frappe.model.add_child(frm.doc, cdt, parentfield);
            frm.refresh_field(parentfield);

            dialog.hide();

            setTimeout(function () {
                open_edit_costing_dialog(frm, cdt, new_row.name);
            }, 0);
        },
    });

    dialog.show();
}


frappe.ui.form.on('Quotation Costing Sheet', {

    edit_costing: function(frm, cdt, cdn) {
        open_edit_costing_dialog(frm, cdt, cdn);
    }

});
