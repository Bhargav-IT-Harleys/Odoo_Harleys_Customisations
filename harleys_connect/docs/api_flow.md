# API flow

1. Odoo creates or updates a purchase order.
2. The manager builds a vendor payload.
3. The selected adapter sends the payload to the vendor API.
4. Responses are logged and stored for auditing.
