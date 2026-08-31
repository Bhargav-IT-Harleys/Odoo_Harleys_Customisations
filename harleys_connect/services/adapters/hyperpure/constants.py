class HyperpureConstants:
    VENDOR_NAME = "hyperpure"
    DEFAULT_BASE_URL = "https://devapi.hyperpure.com"

    # Every path is namespaced under the third-party's whitelisted client name
    # (Harleys' is "harleys") - confirmed against Hyperpure's own integration
    # spec, e.g. /api/harleys/v1/send_otp.
    OUTLET_PHONE_NUMBERS_PATH = "/api/{client_name}/outlet_phone_numbers"
    SEND_OTP_PATH = "/api/{client_name}/v1/send_otp"
    VALIDATE_OTP_PATH = "/api/{client_name}/v1/validate_otp"
    SEARCH_PRODUCTS_PATH = "/api/{client_name}/search_products"
    VALIDATE_ORDER_PATH = "/api/{client_name}/validate_order_placement"
    PLACE_ORDER_PATH = "/api/{client_name}/place_order"

    OUTLET_TYPE = "HYPERPURE"
    PRODUCT_TYPE = "HYPERPURE"
