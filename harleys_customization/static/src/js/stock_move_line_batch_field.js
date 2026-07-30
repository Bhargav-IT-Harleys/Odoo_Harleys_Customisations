import { registry } from "@web/core/registry";
import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import {
  Many2XAutocomplete,
  useActiveActions,
  useX2ManyCrud,
} from "@web/views/fields/relational_utils";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getMoveLineRows } from "./stock_move_line_rows";
import { StockMoveLineBatchQuickCreate } from "./stock_move_line_batch_quickcreate";

export class StockMoveLineBatchField extends Component {
  static template = "harleys_customization.StockMoveLineBatchField";
  static components = { Many2XAutocomplete };
  static props = {
    ...standardFieldProps,
    canCreate: { type: Boolean, optional: true },
    canQuickCreate: { type: Boolean, optional: true },
    canCreateEdit: { type: Boolean, optional: true },
    createDomain: { type: [Array, Boolean], optional: true },
    domain: { type: [Array, Function], optional: true },
    context: { type: Object, optional: true },
    placeholder: { type: String, optional: true },
    nameCreateField: { type: String, optional: true },
    searchThreshold: { type: Number, optional: true },
  };
  static defaultProps = {
    canCreate: true,
    canQuickCreate: true,
    canCreateEdit: true,
    nameCreateField: "name",
    context: {},
    placeholder: "Add batch...",
  };

  setup() {
    this.orm = useService("orm");
    this.ui = useState({
      adding: false,
    });

    // Receipts only: opens StockMoveLineBatchQuickCreate (live batch
    // search + optional expiry date entry).
    this.batchPopover = usePopover(StockMoveLineBatchQuickCreate, {
      position: "bottom-start",
      popoverClass: "o_harleys_batch_popover_wrapper",
    });
    // Anchored to the cell, not the "Add" button: the button is only
    // visible via :hover and collapses to a zero-size rect as soon as the
    // mouse moves toward the popover, which throws position tracking off.
    this.cellRootRef = useRef("cellRoot");

    const { saveRecord, removeRecord } = useX2ManyCrud(
      () => this.props.record.data[this.props.name],
      true,
    );
    this.crudSaveRecord = saveRecord;

    this.activeActions = useActiveActions({
      fieldType: "many2many",
      crudOptions: {
        create: this.props.canCreate && this.props.createDomain,
        createEdit: this.props.canCreateEdit,
        onDelete: removeRecord,
      },
      getEvalParams: (props) => ({
        evalContext: this.props.record.evalContext,
        readonly: props.readonly,
      }),
    });

    this.update = async (recordlist) => {
      const currentIds = this.props.record.data[this.props.name].currentIds;
      recordlist = (recordlist || []).filter(
        (el) => !currentIds.includes(el.id),
      );
      if (!recordlist.length) {
        return;
      }
      await this.crudSaveRecord(recordlist.map((rec) => rec.id));
      await this.props.record.model.root.save();
      this.closeAddUI();
    };

    if (this.props.canQuickCreate) {
      this.quickCreate = async (name) => {
        const created = await this.orm.call(
          this.relation,
          "name_create",
          [name],
          {
            context: this.props.context,
          },
        );
        await this.crudSaveRecord([created[0]]);
        await this.props.record.model.root.save();
        this.closeAddUI();
      };
    }

    this.autocompleteWrapperRef = useRef("autocompleteWrapper");
    useEffect(
      () => {
        if (this.ui.adding) {
          this.autocompleteWrapperRef.el?.querySelector("input")?.click();
        }
      },
      () => [this.ui.adding],
    );
  }

  get relation() {
    return this.props.record.fields[this.props.name].relation;
  }

  get rows() {
    return getMoveLineRows(this.props.record);
  }

  get isLocked() {
    return (
      this.props.record.data.state === "done" &&
      this.props.record.data.is_locked
    );
  }

  // stock.move's own field is picking_code; picking_type_code (used in
  // the view's column_invisible conditions) lives on stock.picking.
  get isReceipt() {
    return this.props.record.data.picking_code === "incoming";
  }

  get showExpiryField() {
    return this.isReceipt && this.props.record.data.use_expiration_date;
  }

  getDomain() {
    return Domain.and([
      getFieldDomain(this.props.record, this.props.name, this.props.domain),
    ]).toList(this.props.context);
  }

  // Same reason update()/quickCreate()/createNewBatch() all save
  // immediately after their write: _set_lot_ids only recomputes real
  // move-line data (quantity, which lines still exist) on an actual
  // server write, never during onchange simulation - confirmed for the
  // add path in stock_move_line_rows.js. Without the save here too, a
  // deletion stays purely client-side: it looks gone until some later,
  // unrelated recompute reloads the real (still-unchanged) server data
  // and the "deleted" batch reappears - which is exactly what looks like
  // "sometimes I can't delete it" from the outside.
  async deleteLot(lot) {
    await this.props.record.data[this.props.name].forget(lot);
    await this.props.record.model.root.save();
  }

  // Fallback rows (see stock_move_line_rows.js) have no lot_ids entry to
  // forget(); move_line_ids is a One2many, so removing the batch means
  // deleting the line itself. Same save requirement as deleteLot() above.
  async deleteLine(line) {
    await this.props.record.data.move_line_ids.delete(line);
    await this.props.record.model.root.save();
  }

  showAddInput() {
    if (this.isReceipt) {
      this.openBatchPopover(this.cellRootRef.el);
    } else {
      this.ui.adding = true;
    }
  }

  hideAddInput() {
    this.ui.adding = false;
  }

  closeAddUI() {
    if (this.batchPopover.isOpen) {
      this.batchPopover.close();
    }
    this.hideAddInput();
  }

  openBatchPopover(anchor) {
    this.batchPopover.open(anchor, {
      showExpiryField: this.showExpiryField,
      productId: this.props.record.data.product_id?.id ?? false,
      onCreate: this.createNewBatch.bind(this),
      onSelectExisting: this.selectExistingBatch.bind(this),
    });
  }

  async selectExistingBatch(lotId) {
    await this.update([{ id: lotId }]);
  }

  async createNewBatch(name, expiryDate) {
    const vals = {
      name,
      product_id: this.props.record.data.product_id?.id,
      company_id: this.props.record.data.company_id?.id,
    };
    if (expiryDate) {
      vals.expiration_date = expiryDate;
    }
    const [newId] = await this.orm.create("stock.lot", [vals], {
      context: this.props.context,
    });
    await this.crudSaveRecord([newId]);
    await this.props.record.model.root.save();
    this.closeAddUI();
  }

  onAutocompleteFocusOut(ev) {
    const wrapper = this.autocompleteWrapperRef.el;
    const target = ev.relatedTarget;
    if (wrapper && target && (wrapper.contains(target) || target.closest(".o_dialog"))) {
      return;
    }
    this.hideAddInput();
  }
}

export const stockMoveLineBatchField = {
  component: StockMoveLineBatchField,
  supportedTypes: ["many2many"],
  extractProps({ attrs, options, placeholder }, dynamicInfo) {
    const hasCreatePermission = attrs.can_create
      ? evaluateBooleanExpr(attrs.can_create)
      : true;
    const noCreate = Boolean(options.no_create);
    const canCreate = noCreate ? false : hasCreatePermission;
    const noQuickCreate = Boolean(options.no_quick_create);
    const noCreateEdit = Boolean(options.no_create_edit);
    return {
      canCreate,
      canQuickCreate: canCreate && !noQuickCreate,
      canCreateEdit: canCreate && !noCreateEdit,
      createDomain: options.create,
      context: dynamicInfo.context,
      domain: dynamicInfo.domain,
      placeholder,
    };
  },
};

registry
  .category("fields")
  .add("stock_move_line_batch", stockMoveLineBatchField);
