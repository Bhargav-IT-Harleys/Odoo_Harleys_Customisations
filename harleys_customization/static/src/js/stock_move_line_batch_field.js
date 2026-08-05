import { registry } from "@web/core/registry";
import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import {
  Many2XAutocomplete,
  useActiveActions,
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
    this.availabilityByLotId = useState({});

    this.batchPopover = usePopover(StockMoveLineBatchQuickCreate, {
      position: "bottom-start",
      popoverClass: "o_harleys_batch_popover_wrapper",
    });
    this.cellRootRef = useRef("cellRoot");

    this.activeActions = useActiveActions({
      fieldType: "many2many",
      crudOptions: {
        create: this.props.canCreate && this.props.createDomain,
        createEdit: this.props.canCreateEdit,
      },
      getEvalParams: (props) => ({
        evalContext: this.props.record.evalContext,
        readonly: props.readonly,
      }),
    });

    this.update = async (recordlist) => {
      const existingLotIds = this.rows.map((row) => row.lotId);
      recordlist = (recordlist || []).filter(
        (el) => !existingLotIds.includes(el.id),
      );
      for (const rec of recordlist) {
        await this.addPendingBatch(rec.id);
      }
      this.closeAddUI();
    };

    if (this.props.canQuickCreate) {
      this.quickCreate = async (name) => {
        const [newId] = await this.orm.create(
          this.relation,
          [{ name }],
          { context: this.props.context },
        );
        await this.addPendingBatch(newId);
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

  async addPendingBatch(lotId) {
    const move = this.props.record;
    await move.data.move_line_ids.addNewRecord({
      mode: "readonly",
      context: {
        default_product_id: move.data.product_id?.id,
        default_product_uom_id: move.data.product_uom?.id,
        default_location_id: move.data.location_id?.id,
        default_location_dest_id: move.data.location_dest_id?.id,
        default_lot_id: lotId,
        default_quantity: 0,
      },
    });
    this.fetchAvailability(lotId);
  }

  async fetchAvailability(lotId) {
    const locationId = this.props.record.data.location_id?.id;
    if (!locationId) {
      return;
    }
    try {
      const qty = await this.orm.call(
        "stock.lot", "action_get_batch_availability", [lotId],
        { location_id: locationId },
      );
      this.availabilityByLotId[lotId] = qty;
    } catch {
    }
  }

  availabilityHint(row) {
    const qty = this.availabilityByLotId[row.lotId];
    return qty === undefined ? null : `Available: ${qty}`;
  }

  async deleteBatch(row) {
    if (row.line) {
      await this.props.record.data.move_line_ids.delete(row.line);
    }
    if (row.lot) {
      await this.props.record.data[this.props.name].forget(row.lot);
    }
    delete this.availabilityByLotId[row.lotId];
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
    await this.addPendingBatch(newId);
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
