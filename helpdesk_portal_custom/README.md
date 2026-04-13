# helpdesk_portal_custom

Odoo 19 module — Helpdesk ticket creation portal form with a custom
`location_id` field sourced from `stock.warehouse`.

---

## Features

| Feature | Detail |
|---|---|
| Portal form | `/helpdesk/new` — authenticated portal users can create tickets |
| Custom field | `location_id` (Many2one → `stock.warehouse`) on `helpdesk.ticket` |
| Dynamic ticket types | AJAX reload of ticket types when team is changed |
| Priority picker | Bootstrap radio-button group (Normal / Low / High / Urgent) |
| Validation | Server-side validation with error repopulation |
| Submit guard | Disables button & shows spinner on submit to prevent duplicate tickets |
| Character counter | Live counter on description textarea |

---

## Installation

1. Copy the `helpdesk_portal_custom` folder into your Odoo `addons` path.
2. Restart the Odoo service.
3. Go to **Settings → Apps**, search for **Helpdesk Portal – Custom Location Field**, and install.
4. Make sure at least one helpdesk team has **"Use Website Form"** enabled
   (`Helpdesk → Configuration → Teams → Use Website Form ✓`).

---

## Module structure

```
helpdesk_portal_custom/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── portal.py           ← GET /helpdesk/new, POST /helpdesk/new/submit,
│                              JSON /helpdesk/get_ticket_types
├── models/
│   ├── __init__.py
│   └── helpdesk_ticket.py  ← adds location_id Many2one field
├── security/
│   └── ir.model.access.csv
├── static/src/
│   ├── css/portal_form.css
│   └── js/portal_form.js
└── views/
    └── helpdesk_portal_templates.xml
```

---

## Flow

```
Portal user opens /helpdesk/new
        │
        ▼
Controller fetches:
  • helpdesk.team  (use_website_helpdesk_form = True)
  • stock.warehouse (all active)
  • helpdesk.ticket.type
        │
        ▼
QWeb renders form with:
  Subject | Team | Ticket Type | Warehouse (location_id) | Priority | Description
        │
   [user changes Team]
        │ AJAX JSON-RPC → /helpdesk/get_ticket_types
        ▼ ticket type <select> refreshes dynamically
        │
   [user submits]
        │ POST /helpdesk/new/submit (CSRF protected)
        ▼
Controller validates:
  • name, team_id, description required
  • location_id, ticket_type_id, priority optional
        │
  ┌─────┴─────┐
  │           │
error       success
  │           │
re-render   create helpdesk.ticket
form        subscribe portal user
            redirect /my/tickets/<id>?message=created
```

---

## Key technical notes

### Why `sudo()` in the controller?
Portal users do not have direct model access for reading teams or warehouses.
`sudo()` is used **only for reading lookup data** (teams, warehouses, types).
Ticket creation also uses `sudo()` but the `partner_id` is always forced to
the authenticated user's partner so there is no privilege escalation.

### CSRF
The form posts to `/helpdesk/new/submit` with `csrf=True` on the route and
the `csrf_token` hidden input in the template.  Odoo validates this
automatically.

### location_id field
Defined as `Many2one('stock.warehouse')` on `helpdesk.ticket`.  The portal
only passes its database ID; the controller resolves and validates the record
before writing.
