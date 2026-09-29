"""Optional Investimentos adapter boundary for AION specialists.

Importing this module does not import the product-domain implementation.
Resolution happens lazily only when a comparison is explicitly requested.
"""
from __future__ import annotations


def investment_product_comparison(products):
    from atlasquant_investment_ecosystem import (
        investment_product_comparison as _investment_product_comparison,
    )

    return _investment_product_comparison(products)


__all__ = ["investment_product_comparison"]
