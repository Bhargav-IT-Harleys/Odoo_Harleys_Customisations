class VendorProductMapper:
    """Generic vendor product mapping utilities - used by any adapter that
    needs to resolve a product.supplierinfo record for a (product, vendor
    account) pair, not just Hyperpure."""

    @staticmethod
    def find_supplierinfo(product, vendor_account):
        if not product or not vendor_account:
            return None

        partner = vendor_account.vendor_partner_id
        platform = vendor_account.platform_id
        company = vendor_account.company_id

        domain = [("partner_id", "=", partner.id)]
        if platform:
            domain.append(("platform_id", "=", platform.id))
        if company:
            domain.append(("company_id", "in", [False, company.id]))

        supplierinfos = product.seller_ids.filtered_domain(domain)
        if not supplierinfos:
            return None
        return supplierinfos.sorted(key=lambda info: (info.sequence or 999, info.id))[0]

    @staticmethod
    def validate_mapping(supplierinfo, product, vendor_account, required_fields):
        """Return a list of {product_id, product_name, missing_fields, message}
        dicts describing why `product` isn't ready to send to this vendor -
        empty list means it's fully mapped."""
        if not supplierinfo:
            return [{
                "product_id": product.id,
                "product_name": product.display_name or product.name,
                "missing_fields": ["supplierinfo"],
                "message": "No vendor mapping found for product '%s' with vendor '%s'." % (
                    product.display_name or product.name,
                    vendor_account.vendor_partner_id.name,
                ),
            }]

        missing = [field for field in required_fields if not getattr(supplierinfo, field, None)]
        if not missing:
            return []
        return [{
            "product_id": product.id,
            "product_name": product.display_name or product.name,
            "missing_fields": missing,
            "message": "Product '%s' is mapped to vendor '%s' but is missing: %s." % (
                product.display_name or product.name,
                vendor_account.vendor_partner_id.name,
                ", ".join(missing),
            ),
        }]
