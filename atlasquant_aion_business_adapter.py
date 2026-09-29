"""Optional Negócios adapter boundary for AION Core memory.

This module is deliberately tiny: it is the only place where the memory layer
resolves the optional Negócios implementation. Importing this adapter does not
import the product domain; resolution happens lazily and falls back to the
fail-closed normalizers supplied by the caller.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


NormalizerBundle = tuple[
    Callable[..., Any],
    Callable[..., Any],
    Callable[..., Any],
    Callable[..., Any],
]


def resolve_business_normalizers(
    fallback_factory: Callable[[], NormalizerBundle],
) -> NormalizerBundle:
    try:
        from atlasquant_aion_business import (
            business_digest,
            business_metrics_digest,
            normalize_business_metrics,
            normalize_products,
        )
    except ImportError:
        return fallback_factory()
    return (
        normalize_products,
        business_digest,
        normalize_business_metrics,
        business_metrics_digest,
    )


__all__ = ["NormalizerBundle", "resolve_business_normalizers"]
