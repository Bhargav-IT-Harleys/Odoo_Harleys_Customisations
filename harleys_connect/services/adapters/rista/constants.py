class RistaConstants:
    VENDOR_NAME = "rista"
    DEFAULT_BASE_URL = "https://api.ristaapps.com/v1"


# Mirrors rista_api_tester/api_catalog.json's simple GET endpoints - each is directly
# fetchable with a single request. "all_branch_sales_summary" is deliberately excluded:
# it's a multi-step workflow (fetch every branch, then fetch sales per branch, then
# consolidate) rather than a single endpoint, and isn't built yet.
REPORT_CATALOG = (
    {
        "id": "branch_list",
        "name": "Branch List",
        "category": "Business",
        "path": "/branch/list",
        "description": "Get all branch information",
        "parameters": [],
    },
    {
        "id": "sales_summary",
        "name": "Sales Summary",
        "category": "Analytics",
        "path": "/analytics/sales/summary",
        "description": "Get sales summary",
        "parameters": ["branch", "period"],
        "field_mapping": {
            "Date": "request.period",
            "Sale Item Qty": "itemTotalQty",
            "Taxes": "taxTotal",
            "Direct Charge": "channelSummary[].directCharge",
            "Indirect Charge": "channelSummary[].indirectCharge",
            "Channel": "channelSummary[].name",
            "Payment Modes": "payments[].mode",
        },
    },
    {
        "id": "custom_sales_summary",
        "name": "Custom Sales Summary",
        "category": "Analytics",
        "path": "/analytics/custom/sales/summary",
        "description": "Get custom sales summary",
        "parameters": ["branch", "fromDate", "toDate"],
    },
    {
        "id": "tally_sales_summary",
        "name": "Tally Sales Summary",
        "category": "Analytics",
        "path": "/analytics/tally/sales/summary",
        "description": "Get tally sales summary",
        "parameters": ["branch", "fromDate", "toDate"],
    },
    {
        "id": "customer_list",
        "name": "Customer List",
        "category": "Business",
        "path": "/customer/list",
        "description": "Get all customers",
        "parameters": [],
    },
    {
        "id": "item_list",
        "name": "Item List",
        "category": "Inventory",
        "path": "/item/list",
        "description": "Get all items",
        "parameters": [],
    },
    {
        "id": "stock_list",
        "name": "Stock List",
        "category": "Inventory",
        "path": "/stock/list",
        "description": "Get stock details",
        "parameters": ["branch"],
    },
    {
        "id": "grn_list",
        "name": "GRN List",
        "category": "Inventory",
        "path": "/grn/list",
        "description": "Get GRN list",
        "parameters": ["branch", "fromDate", "toDate"],
    },
    {
        "id": "purchase_order_list",
        "name": "Purchase Order List",
        "category": "Inventory",
        "path": "/purchase-order/list",
        "description": "Get purchase orders",
        "parameters": ["branch", "fromDate", "toDate"],
    },
    {
        "id": "discount_transactions",
        "name": "Discount Transactions",
        "category": "Analytics",
        "path": "/analytics/discount/transactions",
        "description": "Get discount transactions",
        "parameters": ["branch", "day", "lastKey"],
        "field_mapping": {
            "Invoice Date": "invoiceDate",
            "Invoice Number": "invoiceNumber",
            "Invoice Type": "invoiceType",
            "Discount Code": "discountCode",
            "Discount Amount": "discountAmount",
            "Discount Percentage": "discountPercentage",
            "Coupon Code": "couponCode",
            "Coupon Provider": "couponProvider",
            "Campaign Name": "campaignName",
            "Bill Net Discount": "billNetDiscount",
            "Bill Gross Amount": "billGrossAmount",
            "Sale Amount": "saleAmount",
            "Applied By": "appliedBy",
            "Reason": "reason",
        },
    },
)

REPORT_CATALOG_BY_ID = {report["id"]: report for report in REPORT_CATALOG}
