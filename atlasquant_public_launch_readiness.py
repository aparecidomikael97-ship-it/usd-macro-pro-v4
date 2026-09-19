"""AtlasQuant public-launch readiness aggregator.

Combines internal repository evidence without converting external dependencies
into completed status. It never publishes, charges, grants data rights, enables
broker execution or changes trading permissions.
"""
from __future__ import annotations

from typing import Any
from atlasquant_platform_center import pwa_asset_audit
from atlasquant_support_center import support_minimum_ready
from atlasquant_academy import academy_minimum_text_ready
from atlasquant_academy_media import academy_video_scripts_ready
from atlasquant_voice_readiness import voice_contract_ready
from atlasquant_brokers_guide import brokers_guide_minimum_ready
from atlasquant_commercial_prep import commercial_prep_audit
from atlasquant_billing_contract import billing_contract_ready
from atlasquant_data_licensing_inventory import data_inventory_ready

SCHEMA="ATLASQUANT_PUBLIC_LAUNCH_READINESS_V1"

def collect_public_launch_readiness()->dict[str,Any]:
    prep=commercial_prep_audit()
    internal={
        "pwa":bool(pwa_asset_audit().get("pwa_ready")),
        "support":bool(support_minimum_ready()),
        "academy_text":bool(academy_minimum_text_ready()),
        "academy_video_scripts":bool(academy_video_scripts_ready()),
        "voice_contract":bool(voice_contract_ready()),
        "brokers_guide":bool(brokers_guide_minimum_ready()),
        "commercial_pack":bool(prep.get("internal_prep_ready")),
        "billing_contract":bool(billing_contract_ready()),
        "data_provider_inventory":bool(data_inventory_ready()),
    }
    external={
        "legal_review":False,
        "commercial_data_licensing":False,
        "payment_provider":False,
        "academy_videos_rendered_and_published":False,
        "tts_provider":False,
        "native_store_publication":False,
    }
    internal_complete=all(internal.values())
    external_complete=all(external.values())
    return {
        "schema":SCHEMA,
        "internal":internal,
        "external":external,
        "internal_preparation_complete":internal_complete,
        "external_dependencies_complete":external_complete,
        "public_launch_ready":bool(internal_complete and external_complete),
        "automatic_launch":False,
        "broker_execution_enabled":False,
        "real_orders_enabled":False,
        "manual_final_review_required":True,
    }

__all__=["SCHEMA","collect_public_launch_readiness"]
