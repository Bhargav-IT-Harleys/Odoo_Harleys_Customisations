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
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getMoveLineRows } from "./stock_move_line_rows";

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
    this.ui = useState({
      adding: false,
    });
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
      this.hideAddInput();
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
        this.hideAddInput();
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

  getDomain() {
    return Domain.and([
      getFieldDomain(this.props.record, this.props.name, this.props.domain),
    ]).toList(this.props.context);
  }

  async deleteLot(lot) {
    await this.props.record.data[this.props.name].forget(lot);
  }

  // For rows surfaced only via stock_move_line_rows.js's fallback (a lot
  // that core's own _compute_lot_ids excluded because its line's quantity
  // is 0 - see that file's comment). There's no lot_ids relation entry to
  // forget() here since the lot never made it into lot_ids to begin with;
  // removing the batch means removing the move line itself instead.
  // move_line_ids is a One2many, so this is .delete() (destroys the
  // record), not .forget() (which is Many2many-specific unlink-only
  // semantics, and would be wrong here regardless).
  async deleteLine(line) {
    await this.props.record.data.move_line_ids.delete(line);
  }

  showAddInput() {
    this.ui.adding = true;
  }

  hideAddInput() {
    this.ui.adding = false;
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
