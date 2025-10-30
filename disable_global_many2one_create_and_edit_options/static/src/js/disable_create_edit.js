/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from '@web/views/fields/relational_utils';
import { _t } from "@web/core/l10n/translation";

patch(Many2XAutocomplete.prototype, {
    get actionSuggestions() {
        return [
            {
                // search more
                enabled: this.addSearchMoreSuggestion.bind(this),
                build: this.buildSearchMoreSuggestion.bind(this),
            },
        ];
    },
});

