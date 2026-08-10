import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))


if "odoo" not in sys.modules:
    odoo = types.ModuleType("odoo")

    class DummyField:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class DummyModel:
        pass

    def _field(*args, **kwargs):
        return DummyField(*args, **kwargs)

    odoo.fields = types.SimpleNamespace(
        Char=_field,
        Many2one=_field,
        Boolean=_field,
        Selection=_field,
        Integer=_field,
        Text=_field,
        Float=_field,
        Date=_field,
        Datetime=_field,
    )
    odoo.models = types.SimpleNamespace(Model=DummyModel, TransientModel=DummyModel)
    odoo.api = types.SimpleNamespace(
        model=lambda *args, **kwargs: (lambda f: f),
        depends=lambda *args, **kwargs: (lambda f: f),
    )
    odoo.exceptions = types.SimpleNamespace(UserError=type("UserError", (Exception,), {}))
    sys.modules["odoo"] = odoo
    sys.modules["odoo.api"] = odoo.api
    sys.modules["odoo.exceptions"] = odoo.exceptions


from b2b_erp_integration.models.vendor_account import VendorAccount
from b2b_erp_integration.models.vendor_outlet import VendorOutlet
from b2b_erp_integration.services.adapters.hyperpure.auth import HyperpureAuthService
from b2b_erp_integration.services.adapters.hyperpure.mapping import HyperpureMappingService
from b2b_erp_integration.services.manager import VendorIntegrationManager
from b2b_erp_integration.services.registry import AdapterRegistry
from b2b_erp_integration.services.adapters.hyperpure.auth import HttpClient


def run_tests():
    test_vendor_account_has_hyperpure_configuration_fields()
    test_vendor_account_unique_constraint()
    test_vendor_outlet_belongs_to_a_vendor_account()
    test_hyperpure_auth_uses_configured_credentials()
    test_hyperpure_mapping_uses_vendor_product_identifier()
    test_manager_uses_platform_code_for_adapter_lookup()
    print('All tests passed.')


def test_vendor_account_has_hyperpure_configuration_fields():
    assert hasattr(VendorAccount, 'vendor_partner_id')
    assert hasattr(VendorAccount, 'account_id')
    assert hasattr(VendorAccount, 'client_name')
    assert hasattr(VendorAccount, 'api_access_key')


def test_vendor_account_unique_constraint():
    assert any(
        constraint[0] == 'unique_account_per_platform_company'
        for constraint in getattr(VendorAccount, '_sql_constraints', [])
    )


def test_vendor_outlet_belongs_to_a_vendor_account():
    assert hasattr(VendorOutlet, 'vendor_account_id')
    assert hasattr(VendorOutlet, 'outlet_id')
    assert hasattr(VendorOutlet, 'warehouse_id')
    assert any(
        constraint[0] == 'unique_outlet_per_account'
        for constraint in getattr(VendorOutlet, '_sql_constraints', [])
    )


def test_hyperpure_auth_uses_configured_credentials():
    captured = {}
    original = HttpClient.post

    def fake_post(url, payload=None, headers=None):
        captured['url'] = url
        captured['payload'] = payload or {}
        captured['headers'] = headers or {}
        return SimpleNamespace(status_code=200, text='{}')

    HttpClient.post = fake_post
    try:
        config = SimpleNamespace(
            mobile_number='9999900004',
            account_id='194841',
            client_name='harleys',
            api_access_key='7e1c690c284e01c02c0af38e426b097b',
            auth_url='https://devapi.hyperpure.com/auth',
        )
        HyperpureAuthService.request_otp(config)
    finally:
        HttpClient.post = original

    assert captured['payload']['account_id'] == '194841'
    assert captured['payload']['client_name'] == 'harleys'
    assert captured['payload']['api_access_key'] == '7e1c690c284e01c02c0af38e426b097b'


def test_hyperpure_mapping_uses_vendor_product_identifier():
    product = SimpleNamespace(display_name='Test Product')
    seller = SimpleNamespace(
        partner_id=SimpleNamespace(),
        vendor_product_code='20021159',
        vendor_product_id='20021159',
        vendor_uom_code='EA',
    )
    purchase_order = SimpleNamespace(
        name='PO-001',
        partner_id=SimpleNamespace(name='Harleys Vendor'),
        order_line=[
            SimpleNamespace(
                product_id=product,
                product_qty=2,
                price_unit=10,
                product_uom_id=SimpleNamespace(name='Unit'),
                order_id=SimpleNamespace(partner_id=SimpleNamespace()),
            )
        ],
    )
    product.seller_ids = [seller]
    payload = HyperpureMappingService.build_order_payload(purchase_order)
    assert payload['lines'][0]['vendor_product_code'] == '20021159'
    assert payload['lines'][0]['vendor_product_id'] == '20021159'


def test_manager_uses_platform_code_for_adapter_lookup():
    config = SimpleNamespace(platform_id=SimpleNamespace(code='hyperpure'))
    manager = VendorIntegrationManager(config)
    adapter = manager._get_adapter()
    assert AdapterRegistry.get('hyperpure') is adapter


if __name__ == '__main__':
    run_tests()
