"""AtlasQuant AION — official administrator command center.

Presentation/orchestration layer only. All irreversible or external actions are
guarded and feature-flagged. The initial release works in zero-cost local mode
without pretending that external AI/social/marketplace/payment integrations are
already active.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from atlasquant_aion_clock import application_timezone
from atlasquant_aion_core_intelligence.context import Domain
from html import escape
from pathlib import Path
from typing import Any, Mapping
import os

import streamlit as st

from atlasquant_aion_core import (
    AION_VERSION,
    RISKY_EXTERNAL_FEATURES,
    ZERO_COST_RULES,
    TRUTH_RULES,
    feature_flag_snapshot,
    guardian_decision,
    guardian_posture,
    is_admin,
    mission_plan,
    route_context,
)
from atlasquant_aion_gateway import local_answer, provider_status
from atlasquant_aion_command_orchestrator import orchestrate_local_command
from atlasquant_aion_workspaces import (
    AION_PERSONAS,
    admin_brief_lines,
    admin_greeting,
    capability_snapshot,
    developer_trust_policy,
)
from atlasquant_content_pipeline import content_job, provider_readiness
from atlasquant_aion_memory import (
    canonical_memory_summary,
    checkpoint_digest,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    config_from_mapping,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    merged_checkpoint,
    runtime_write_preflight,
    runtime_configuration_status,
    save_runtime_checkpoint,
    search_canonical_memory,
    update_business_checkpoint,
    update_entitlements_checkpoint,
    update_continuity_checkpoint,
    update_learning_checkpoint,
    update_wisdom_checkpoint,
    update_tool_hub_checkpoint,
    update_durable_tasks_checkpoint,
    update_knowledge_graph_checkpoint,
    synchronize_knowledge_graph_checkpoint,
    update_evaluation_lab_checkpoint,
    update_digital_twins_checkpoint,
    update_dev_fusion_checkpoint,
    update_release_confidence_checkpoint,
    update_live_event_journal_checkpoint,
    update_operating_checkpoint,
    update_promotions_checkpoint,
    update_studio_checkpoint,
)
from atlasquant_aion_recovery import (
    list_checkpoint_revisions,
    load_checkpoint_revision,
    recovery_preflight,
    restore_checkpoint_revision,
)
from atlasquant_aion_continuity import (
    MISSION_STATUSES,
    append_handoff,
    build_session_handoff,
    continuity_briefing,
    continuity_summary,
    new_mission,
    prepare_mission_transition,
    transition_mission,
    upsert_mission,
)
from atlasquant_aion_operations import (
    ACTIONS,
    PRIORITIES,
    STATUSES,
    approve_task,
    approval_requirement,
    new_task,
    queue_summary,
    transition_task,
    upsert_task,
)
from atlasquant_aion_observability import (
    append_event,
    new_event,
    observability_summary,
)
from atlasquant_aion_secretary import executive_briefing
from atlasquant_aion_model_router import (
    normalize_budget,
    record_model_spend_estimate,
    route_intelligence,
    set_budget_policy,
)
from atlasquant_aion_provider import (
    build_provider_prompt,
    estimate_request_cost,
    execute_openai_answer,
    provider_config,
)
from atlasquant_aion_studio import (
    FORMATS as STUDIO_FORMATS,
    PLATFORMS as STUDIO_PLATFORMS,
    approve_project,
    new_content_project,
    publication_preflight,
    script_blueprint,
    studio_summary,
    upsert_project,
)
from atlasquant_aion_business import (
    CHANNELS as BUSINESS_CHANNELS,
    TRUTH_STATES as BUSINESS_TRUTH_STATES,
    approve_product,
    business_metrics_views,
    business_summary,
    coverage_snapshot,
    customer_economics,
    funnel_snapshot,
    new_business_metrics,
    normalize_business_metrics,
    marketplace_preflight,
    new_product_candidate,
    trend_assessment,
    upsert_product,
)
from atlasquant_aion_business_demo import (
    business_demo_html,
    business_demo_snapshot,
)
from atlasquant_aion_business_training import (
    delivery_walkthrough as business_delivery_walkthrough,
    diagnostic_brief as business_diagnostic_brief,
    objection_answer as business_objection_answer,
    objection_catalog as business_objection_catalog,
    package_fit as business_package_fit,
    scenario_catalog as business_scenario_catalog,
    simulated_sales_conversation as business_simulated_sales_conversation,
    training_scorecard as business_training_scorecard,
    training_session as business_training_session,
)
from atlasquant_aion_business_proposal_simulator import (
    build_proposal_draft as business_build_proposal_draft,
    client_radar as business_client_radar,
    diagnose_business as business_diagnose_company,
    proposal_text as business_proposal_text,
    recommend_package as business_recommend_package,
)
from atlasquant_aion_business_client_portal_demo import (
    SECTIONS as BUSINESS_CLIENT_PORTAL_SECTIONS,
    build_client_portal_demo as business_build_client_portal_demo,
    portal_attention_summary as business_portal_attention_summary,
    portal_section as business_portal_section,
)
from atlasquant_aion_business_onboarding_demo import (
    ACCESS_CATEGORIES as BUSINESS_ONBOARDING_ACCESS_CATEGORIES,
    PHASES as BUSINESS_ONBOARDING_PHASES,
    build_implementation_plan as business_build_implementation_plan,
    go_live_review_packet as business_go_live_review_packet,
    minimum_access_plan as business_minimum_access_plan,
    onboarding_intake as business_onboarding_intake,
    onboarding_status as business_onboarding_status,
)
from atlasquant_aion_business_customer_success_demo import (
    customer_health as business_customer_health,
    expansion_opportunity as business_expansion_opportunity,
    renewal_readiness as business_renewal_readiness,
    sla_ticket as business_sla_ticket,
    success_plan as business_success_plan,
)
from atlasquant_aion_business_client_finance_demo import (
    client_economics as business_client_economics,
    portfolio_summary as business_finance_portfolio_summary,
    pricing_review as business_pricing_review,
)
from atlasquant_aion_business_trend_intelligence import (
    evaluate_opportunity as business_evaluate_opportunity,
    improvement_review as business_improvement_review,
    rank_opportunities as business_rank_opportunities,
    trend_watch_posture as business_trend_watch_posture,
)
from atlasquant_aion_business_commercial_acquisition_demo import (
    build_channel_plan as business_build_channel_plan,
    build_content_plan as business_build_content_plan,
    build_contract_handoff as business_build_contract_handoff,
    build_landing_page_brief as business_build_landing_page_brief,
    commercial_funnel_snapshot as business_commercial_funnel_snapshot,
    outreach_draft as business_outreach_draft,
    qualify_prospect as business_qualify_prospect,
)
from atlasquant_aion_business_integration_hub import (
    INTEGRATIONS as BUSINESS_INTEGRATIONS,
    connection_review_packet as business_integration_connection_review,
    hub_snapshot as business_integration_hub_snapshot,
    integration_health as business_integration_health,
    integration_record as business_integration_record,
    minimum_scope_plan as business_integration_scope_plan,
    secret_handling_policy as business_integration_secret_policy,
)
from atlasquant_aion_business_privacy_audit import (
    access_decision as business_privacy_access_decision,
    audit_event as business_privacy_audit_event,
    automation_version as business_privacy_automation_version,
    consent_record as business_privacy_consent_record,
    data_subject_request as business_privacy_subject_request,
    governance_snapshot as business_privacy_governance_snapshot,
    privacy_profile as business_privacy_profile,
    retention_review as business_privacy_retention_review,
    role_access_matrix as business_privacy_role_access_matrix,
    rollback_plan as business_privacy_rollback_plan,
)
from atlasquant_aion_business_master_readiness import (
    default_demo_evidence as business_default_demo_evidence,
    master_readiness_snapshot as business_master_readiness_snapshot,
    pilot_review_packet as business_pilot_review_packet,
    status_rows as business_master_status_rows,
)
from atlasquant_aion_business_pilot_governance import (
    STOP_REASONS as BUSINESS_PILOT_STOP_REASONS,
    build_pilot_charter as business_build_pilot_charter,
    define_stop_conditions as business_define_pilot_stop_conditions,
    define_success_criteria as business_define_pilot_success_criteria,
    pilot_gate_review as business_pilot_gate_review,
    pilot_posture as business_pilot_posture,
    pilot_review_packet as business_bounded_pilot_review_packet,
)
from atlasquant_aion_business_stack_consolidation_v2 import (
    administrative_options as business_stack_admin_options,
    consolidation_preview as business_stack_consolidation_preview,
    frozen_green_evidence as business_stack_frozen_green_evidence,
    release_bundle_manifest as business_stack_release_bundle,
    rollback_integration_plan as business_stack_rollback_plan,
    validate_stack as business_stack_validate,
)
from atlasquant_aion_business_consolidation_dry_run_v2 import (
    build_consolidation_runbook as business_build_consolidation_dry_run_v2,
    live_revalidation_snapshot as business_live_revalidation_snapshot_v2,
)
from atlasquant_aion_business_consolidation_decision_request import (
    decision_request_template as business_consolidation_decision_request_template,
)
from atlasquant_aion_business_consolidation_authorization_record import (
    authorization_record_requirements as business_consolidation_authorization_requirements,
)
from atlasquant_aion_business_consolidation_execution_preflight import (
    execution_preflight_template as business_consolidation_execution_preflight_template,
)
from atlasquant_aion_business_consolidation_execution_review_packet import (
    review_packet_template as business_execution_review_packet_template,
)
from atlasquant_aion_business_consolidation_post_merge_verification import (
    post_merge_verification_template as business_post_merge_verification_template,
)
from atlasquant_aion_business_consolidation_progress_ledger import (
    progress_ledger_template as business_consolidation_progress_ledger_template,
)
from atlasquant_aion_business_consolidation_completion_review import (
    completion_review_template as business_consolidation_completion_review_template,
    final_admin_decision_request as business_final_admin_decision_request,
)
from atlasquant_aion_business_release_boundary_handoff import (
    deploy_decision_request as business_deploy_decision_request,
    release_handoff_template as business_release_handoff_template,
)
from atlasquant_aion_business_deploy_verification_runtime_boundary import (
    deploy_authorization_requirements as business_deploy_authorization_requirements,
    deployment_verification_template as business_deployment_verification_template,
)
from atlasquant_aion_business_runtime_activation_readiness import (
    activation_authorization_requirements as business_runtime_activation_requirements,
    post_activation_verification_template as business_post_activation_verification_template,
)
from atlasquant_aion_business_post_activation_expansion_boundary import (
    EXPANSION_ACKNOWLEDGEMENTS as BUSINESS_EXPANSION_ACKNOWLEDGEMENTS,
    REQUIRED_EXPANSION_DECISION_TOKEN as BUSINESS_EXPANSION_DECISION_TOKEN,
    post_activation_verification_requirements as business_post_activation_boundary_requirements,
)
from atlasquant_aion_business_expansion_readiness import (
    expansion_authorization_requirements as business_expansion_authorization_requirements,
)
from atlasquant_aion_business_post_expansion_cycle_freeze import (
    post_expansion_verification_requirements as business_post_expansion_verification_requirements,
)
from atlasquant_aion_business_expansion_cycle_audit_ledger import (
    audit_expansion_cycle_ledger as business_audit_expansion_cycle_ledger,
    expansion_cycle_ledger_template as business_expansion_cycle_ledger_template,
)
from atlasquant_aion_business_capacity_quota_guardrail import (
    capacity_policy_requirements as business_capacity_policy_requirements,
)
from atlasquant_aion_business_quota_application_authorization import (
    quota_application_authorization_requirements as business_quota_application_authorization_requirements,
)
from atlasquant_aion_business_team_access_rbac import (
    TEAM_PROFILES as business_team_access_profiles,
)
from atlasquant_aion_business_capacity_scale_manager import (
    capacity_scale_policy as business_capacity_scale_policy,
)
from atlasquant_aion_finops_budget_governor import (
    finops_policy as business_finops_policy,
    revenue_routing_policy as business_revenue_routing_policy,
)
from atlasquant_aion_eight_role_router import (
    role_registry as aion_eight_role_registry,
)
from atlasquant_aion_core_master_checkpoint_bootstrap import (
    master_checkpoint_bootstrap_snapshot as aion_master_checkpoint_bootstrap_snapshot,
)
from atlasquant_aion_business_b2b_revenue_offer import (
    priority_offer_template as business_priority_offer_template,
    revenue_priority_snapshot as business_revenue_priority_snapshot,
)
from atlasquant_aion_business_first_pilot_pricing_review import (
    first_pilot_policy as business_first_pilot_policy,
)
from atlasquant_aion_backup_recovery_policy import (
    backup_recovery_policy as aion_backup_recovery_policy,
    audit_repository_backup_readiness as aion_audit_repository_backup_readiness,
)
from atlasquant_aion_independence_index import (
    independence_policy as aion_independence_policy,
)
from atlasquant_aion_business_commercial_live_data_binding import (
    live_binding_policy as business_live_binding_policy,
)
from atlasquant_aion_promotions import (
    BENEFIT_TYPES as PROMO_BENEFIT_TYPES,
    activation_preflight,
    approve_campaign,
    new_campaign,
    promotions_summary,
    upsert_campaign,
)
from atlasquant_aion_entitlements import (
    SOURCE_KINDS as ENTITLEMENT_SOURCE_KINDS,
    approve_entitlement_request,
    entitlement_activation_preflight,
    entitlement_summary,
    new_entitlement_request,
    upsert_entitlement,
)
from atlasquant_access_panel import configured_users
from atlasquant_entitlement_account_audit import (
    audit_account_entitlements,
    audit_requires_review,
)
from atlasquant_aion_status_board import (
    build_master_status_board,
    status_rows,
)
from atlasquant_aion_approval_inbox import (
    collect_approval_inbox,
    approval_rows,
)
from atlasquant_aion_tenant import (
    tenant_policy_snapshot,
    tenant_readiness_summary,
)
from atlasquant_aion_tenant_privacy import (
    tenant_privacy_policy_snapshot,
    tenant_privacy_readiness,
)
from atlasquant_aion_incident_center import (
    collect_incidents,
    incident_center_rows,
    incident_response_plan,
)
from atlasquant_aion_executive_pulse import (
    compact_attention_rows,
    executive_pulse,
)
from atlasquant_aion_admin_guidance import (
    EXPERIENCE_MODES as ADMIN_ONBOARDING_MODES,
    build_admin_copilot_snapshot,
    build_admin_onboarding_snapshot,
    complete_admin_onboarding_step,
)
from atlasquant_aion_replay_panel import render_replay_lab_panel
from atlasquant_navigation_bridge import request_surface_revalidation
from atlasquant_aion_validation_center import (
    validation_center_rows,
    validation_center_snapshot,
)
from atlasquant_interface_validation import interface_validation_mission
from atlasquant_release_gate import release_gate, release_gate_rows
from atlasquant_aion_intelligence import (
    commander_briefing,
    evidence_audit,
    evidence_confidence,
    scenario_events,
    simulate_macro_scenario,
)
from atlasquant_aion_reliability import reliability_snapshot
from atlasquant_aion_fortress import (
    cyber_immune_plan,
    emergency_cutoff_posture,
    instruction_boundary,
    proof_of_safety,
    source_authority,
)
from atlasquant_aion_resilience import (
    agent_firewall,
    circuit_breaker,
    resilience_summary,
    resource_governor,
    safe_mode_posture,
    watchdog,
)
from atlasquant_aion_memory_reliability import memory_reliability_summary
from atlasquant_aion_data_decision_fabric import data_decision_fabric_summary, derive_checkpoint_fabric_events
from atlasquant_aion_portable import (
    central_entry_contract,
    portable_core_summary,
)
from atlasquant_aion_vault import vault_summary
from atlasquant_aion_tool_hub import (
    default_tool_hub,
    normalize_tool_hub,
    plan_tool_call,
    tool_hub_summary,
)
from atlasquant_aion_local_executor import local_allowlist
from atlasquant_aion_local_traceability import SOURCE_CATALOG, local_contract_fingerprint
from atlasquant_aion_durable_tasks import (
    durable_tasks_summary,
    new_durable_task,
    prepare_resume,
    record_resume,
    upsert_durable_task,
)
from atlasquant_aion_knowledge_graph import (
    graph_neighborhood,
    knowledge_graph_summary,
)
from atlasquant_aion_evaluation_lab import (
    evaluate_run,
    evaluation_lab_summary,
    new_eval_run,
    upsert_run,
)
from atlasquant_aion_digital_twin import (
    digital_twin_summary,
    new_digital_twin,
    record_twin_observation,
    upsert_digital_twin,
)
from atlasquant_aion_dev_fusion import (
    STAGES as DEV_FUSION_STAGES,
    dev_fusion_summary,
    new_dev_fusion_pipeline,
    record_stage as record_dev_fusion_stage,
    upsert_pipeline,
)
from atlasquant_aion_developer_intelligence import (
    build_development_plan as build_developer_intelligence_plan,
    scan_repository as scan_developer_repository,
)
from atlasquant_aion_developer_package import build_developer_package
from atlasquant_aion_developer_diagnostics import (
    diagnose_failure as diagnose_developer_failure,
    record_failure_attempt as record_developer_failure_attempt,
)
from atlasquant_aion_developer_correction import build_correction_plan as build_developer_correction_plan
from atlasquant_aion_developer_evidence_gate import (
    confirm_root_cause_human_review as confirm_developer_root_cause,
    evaluate_evidence_promotion as evaluate_developer_evidence_promotion,
)
from atlasquant_aion_developer_implementation import (
    approve_implementation_session as approve_developer_implementation,
    build_implementation_envelope as build_developer_implementation_envelope,
    prepare_implementation_readiness as prepare_developer_implementation_readiness,
)
from atlasquant_aion_developer_builder_sandbox import build_builder_sandbox_request as build_developer_builder_sandbox_request
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY as DEVELOPER_SANDBOX_COMMAND_POLICY,
    build_sandbox_preflight as build_developer_sandbox_preflight,
)
from atlasquant_aion_developer_patch_validation import validate_patch as validate_developer_patch
from atlasquant_aion_developer_runner_contract import build_runner_contract as build_developer_runner_contract
from atlasquant_aion_developer_command_policy import build_command_policy_contract as build_developer_command_policy_contract
from atlasquant_aion_release_confidence import (
    DIMENSIONS as RELEASE_CONFIDENCE_DIMENSIONS,
    evidence_dimension,
    release_confidence,
    release_confidence_summary,
)
from atlasquant_aion_cognitive_orchestrator import orchestrator_snapshot
from atlasquant_aion_capability_planner import plan_agentic_mission
from atlasquant_aion_orchestrator import (
    build_aion_result,
    orchestrate as orchestrate_aion_core,
    present_validated_answer,
)
from atlasquant_aion_specialists import plan_specialist_dispatch
from atlasquant_aion_specialist_evidence import read_specialist_evidence
from atlasquant_aion_specialist_session import loaded_session_from_checkpoint
from atlasquant_aion_session_memory import evidence_scope_label
from atlasquant_aion_memory_layers import memory_layer_summary
from atlasquant_aion_event_journal import (
    continuity_summary as live_event_continuity_summary,
    merge_events as merge_live_event_journal_events,
    normalize_heartbeats as normalize_live_event_heartbeats,
)
from atlasquant_aion_learning import (
    CAUSE_TAGS as LEARNING_CAUSE_TAGS,
    FORECAST_TYPES as LEARNING_FORECAST_TYPES,
    RESEARCH_KINDS as LEARNING_RESEARCH_KINDS,
    confidence_calibration,
    error_pattern_summary,
    evaluate_learning_experiment,
    learning_summary,
    new_learning_episode,
    new_learning_experiment,
    new_research_reference,
    settle_learning_episode,
    upsert_learning_episode,
    upsert_learning_experiment,
)
from atlasquant_aion_wisdom import (
    TRUTH_STATES as WISDOM_TRUTH_STATES,
    candidate_from_learning_episode,
    new_wisdom_entry,
    upsert_wisdom_entry,
    wisdom_evidence_hits,
    wisdom_review_state,
    wisdom_summary,
)

try:
    from atlasquant_neural_voice_ui import (
        neural_voice_status,
        render_neural_voice_player,
    )
except Exception:
    neural_voice_status = None
    render_neural_voice_player = None

try:
    from atlasquant_aion_core_runtime_bridge import (
        authenticated_context,
        handle_runtime_intent,
    )
except Exception:
    authenticated_context = None
    handle_runtime_intent = None

try:
    from atlasquant_aion_core_checkpoint_bridge import (
        checkpoint_memory_snapshot,
        stage_user_approved_memory,
    )
except Exception:
    checkpoint_memory_snapshot = None
    stage_user_approved_memory = None

try:
    from atlasquant_aion_core_voice_automation import (
        CADENCES as CORE_AUTOMATION_CADENCES,
        SCHEDULE_CAPABILITIES as CORE_AUTOMATION_CAPABILITIES,
        AtlasQuantVoiceAdapter,
        CheckpointAutomationAdapter,
        stage_schedule,
    )
except Exception:
    CORE_AUTOMATION_CADENCES = ("ONCE", "HOURLY", "DAILY", "WEEKLY")
    CORE_AUTOMATION_CAPABILITIES = (
        "ADMINISTRATION",
        "MEMORY",
        "RESEARCH",
        "VOICE",
        "CONTENT",
        "OBSERVABILITY",
    )
    AtlasQuantVoiceAdapter = None
    CheckpointAutomationAdapter = None
    stage_schedule = None

try:
    from atlasquant_aion_background_executor import (
        execute_due_local_work,
        executor_snapshot,
    )
except Exception:
    execute_due_local_work = None
    executor_snapshot = None

try:
    from atlasquant_aion_worker_runtime import (
        arm_worker,
        kill_worker,
        pause_worker,
        worker_snapshot,
        worker_tick,
    )
except Exception:
    arm_worker = None
    kill_worker = None
    pause_worker = None
    worker_snapshot = None
    worker_tick = None

try:
    from atlasquant_aion_global_worker import (
        global_worker_snapshot,
        stage_arm_global_worker,
        stage_kill_global_worker,
        stage_pause_global_worker,
    )
except Exception:
    global_worker_snapshot = None
    stage_arm_global_worker = None
    stage_kill_global_worker = None
    stage_pause_global_worker = None

try:
    from atlasquant_aion_global_worker_arming import (
        CONFIRMATION_PHRASE,
        approve_global_worker_arming_plan,
        prepare_global_worker_arming_plan,
    )
except Exception:
    CONFIRMATION_PHRASE = "ARMAR WORKER GLOBAL"
    approve_global_worker_arming_plan = None
    prepare_global_worker_arming_plan = None

try:
    from atlasquant_aion_global_worker_persisted_arming import (
        CONFIRMATION_PHRASE as PERSIST_ARMING_CONFIRMATION_PHRASE,
        approve_persisted_arming_plan,
        persist_staged_global_arming,
        persisted_arming_transition_required,
        prepare_persisted_arming_plan,
        read_repository_feature_flag,
        validate_persisted_arming_approval,
    )
except Exception:
    PERSIST_ARMING_CONFIRMATION_PHRASE = "PERSISTIR WORKER GLOBAL ARMADO"
    approve_persisted_arming_plan = None
    persist_staged_global_arming = None
    persisted_arming_transition_required = None
    prepare_persisted_arming_plan = None
    read_repository_feature_flag = None
    validate_persisted_arming_approval = None

try:
    from atlasquant_aion_global_worker_activation import (
        CONFIRMATION_PHRASE as GLOBAL_ACTIVATION_CONFIRMATION_PHRASE,
        DEACTIVATION_PHRASE as GLOBAL_DEACTIVATION_CONFIRMATION_PHRASE,
        activate_global_worker_feature_flag,
        approve_global_worker_activation_plan,
        collect_activation_readiness_evidence,
        deactivate_global_worker_feature_flag,
        prepare_global_worker_activation_plan,
        validate_global_worker_activation_approval,
    )
except Exception:
    GLOBAL_ACTIVATION_CONFIRMATION_PHRASE = "ATIVAR WORKER GLOBAL"
    GLOBAL_DEACTIVATION_CONFIRMATION_PHRASE = "DESATIVAR WORKER GLOBAL"
    activate_global_worker_feature_flag = None
    approve_global_worker_activation_plan = None
    collect_activation_readiness_evidence = None
    deactivate_global_worker_feature_flag = None
    prepare_global_worker_activation_plan = None
    validate_global_worker_activation_approval = None

try:
    from atlasquant_aion_global_worker_live_verification import (
        verify_global_worker_live_activation,
    )
except Exception:
    verify_global_worker_live_activation = None

try:
    from atlasquant_aion_global_worker_supervision import (
        append_supervision_history,
        operational_incident as global_worker_operational_incident,
        supervise_global_worker,
        supervision_history_summary,
    )
except Exception:
    append_supervision_history = None
    global_worker_operational_incident = None
    supervise_global_worker = None
    supervision_history_summary = None

try:
    from atlasquant_aion_global_worker_recovery_drill import (
        CONFIRMATION_PHRASE as GLOBAL_RECOVERY_DRILL_CONFIRMATION_PHRASE,
        prepare_global_worker_recovery_drill,
        recovery_drill_summary,
        simulate_global_worker_recovery_drill,
    )
except Exception:
    GLOBAL_RECOVERY_DRILL_CONFIRMATION_PHRASE = (
        "SIMULAR RECUPERACAO WORKER GLOBAL"
    )
    prepare_global_worker_recovery_drill = None
    recovery_drill_summary = None
    simulate_global_worker_recovery_drill = None

try:
    from atlasquant_aion_global_worker_recovery_closure import (
        CONFIRMATION_PHRASE as GLOBAL_REMEDIATION_CONFIRMATION_PHRASE,
        assess_incident_closure_readiness,
        closure_review_record,
        prepare_remediation_evidence,
    )
except Exception:
    GLOBAL_REMEDIATION_CONFIRMATION_PHRASE = (
        "CONFIRMAR EVIDENCIA DE REMEDIACAO WORKER GLOBAL"
    )
    assess_incident_closure_readiness = None
    closure_review_record = None
    prepare_remediation_evidence = None

try:
    from atlasquant_aion_global_worker_human_incident_closure import (
        CONFIRMATION_PHRASE as GLOBAL_HUMAN_CLOSURE_CONFIRMATION_PHRASE,
        human_closure_summary,
        prepare_human_incident_closure,
        record_human_incident_closure,
    )
except Exception:
    GLOBAL_HUMAN_CLOSURE_CONFIRMATION_PHRASE = (
        "ENCERRAR INCIDENTE WORKER GLOBAL"
    )
    human_closure_summary = None
    prepare_human_incident_closure = None
    record_human_incident_closure = None

try:
    from atlasquant_aion_global_worker_durable_incident_closure import (
        CONFIRMATION_PHRASE as GLOBAL_DURABLE_CLOSURE_CONFIRMATION_PHRASE,
        approve_durable_closure_plan,
        persist_human_incident_closure_record,
        prepare_durable_closure_plan,
        validate_durable_closure_approval,
    )
except Exception:
    GLOBAL_DURABLE_CLOSURE_CONFIRMATION_PHRASE = (
        "PERSISTIR FECHAMENTO INCIDENTE WORKER GLOBAL"
    )
    approve_durable_closure_plan = None
    persist_human_incident_closure_record = None
    prepare_durable_closure_plan = None
    validate_durable_closure_approval = None

try:
    from atlasquant_aion_global_worker_incident_reconciliation import (
        closed_incident_rows as global_worker_closed_incident_rows,
        reconcile_global_worker_incident_center,
    )
except Exception:
    global_worker_closed_incident_rows = None
    reconcile_global_worker_incident_center = None

try:
    from atlasquant_aion_global_worker_reactivation_gate import (
        assess_post_incident_reactivation_gate,
        reactivation_gate_requirement,
    )
except Exception:
    assess_post_incident_reactivation_gate = None
    reactivation_gate_requirement = None

SCHEMA = "ATLASQUANT_AION_ADMIN_V1"
AION_WORKSPACES = (
    "🧠 Central",
    "🗂️ Secretaria",
    "📈 Trading",
    "🎬 Studio",
    "💼 Negócios",
    "🧪 Laboratório",
    "🛠️ Desenvolvimento",
    "🔐 Assinaturas",
    "🎟️ Promoções",
)
_WORKING_CHECKPOINT_KEY = "aion_working_checkpoint_v2"
_WORKING_SOURCE_KEY = "aion_working_checkpoint_source_digest"
_WORKING_DIRTY_KEY = "aion_working_checkpoint_dirty"
_WORKING_CONFLICT_KEY = "aion_working_checkpoint_conflict"
_AION_WORKSPACE_JUMP_KEY = "aion_admin_workspace_jump"
_AION_ADMIN_ONBOARDING_PROGRESS_KEY = "aion_admin_onboarding_progress_v1"
_AION_ADMIN_ONBOARDING_STARTED_KEY = "aion_admin_onboarding_started_v1"
_AION_ADMIN_ONBOARDING_MODE_KEY = "aion_admin_onboarding_mode_v1"
_AION_WORKER_RUNTIME_ID_KEY = "aion_worker_runtime_id_v1"
_AION_GLOBAL_ARMING_PLAN_KEY = "aion_global_arming_plan_v1"
_AION_GLOBAL_ARMING_APPROVAL_KEY = "aion_global_arming_approval_v1"
_AION_GLOBAL_PERSIST_FLAG_EVIDENCE_KEY = "aion_global_persist_flag_evidence_v1"
_AION_GLOBAL_PERSIST_PLAN_KEY = "aion_global_persist_plan_v1"
_AION_GLOBAL_PERSIST_APPROVAL_KEY = "aion_global_persist_approval_v1"
_AION_GLOBAL_ACTIVATION_READINESS_KEY = "aion_global_activation_readiness_v1"
_AION_GLOBAL_ACTIVATION_PLAN_KEY = "aion_global_activation_plan_v1"
_AION_GLOBAL_ACTIVATION_APPROVAL_KEY = "aion_global_activation_approval_v1"
_AION_GLOBAL_ACTIVATION_RESULT_KEY = "aion_global_activation_result_v1"
_AION_GLOBAL_REACTIVATION_GATE_KEY = "aion_global_reactivation_gate_v1"
_AION_GLOBAL_LIVE_VERIFICATION_KEY = "aion_global_live_verification_v1"
_AION_GLOBAL_SUPERVISION_KEY = "aion_global_supervision_v1"
_AION_GLOBAL_SUPERVISION_HISTORY_KEY = "aion_global_supervision_history_v1"
_AION_GLOBAL_RECOVERY_DRILL_KEY = "aion_global_recovery_drill_v1"
_AION_GLOBAL_REMEDIATION_EVIDENCE_KEY = "aion_global_remediation_evidence_v1"
_AION_GLOBAL_CLOSURE_ASSESSMENT_KEY = "aion_global_closure_assessment_v1"
_AION_GLOBAL_HUMAN_CLOSURE_RECORD_KEY = "aion_global_human_closure_record_v1"
_AION_GLOBAL_DURABLE_CLOSURE_FLAG_EVIDENCE_KEY = (
    "aion_global_durable_closure_flag_evidence_v1"
)
_AION_GLOBAL_DURABLE_CLOSURE_PLAN_KEY = "aion_global_durable_closure_plan_v1"
_AION_GLOBAL_DURABLE_CLOSURE_APPROVAL_KEY = (
    "aion_global_durable_closure_approval_v1"
)
_AION_GLOBAL_DURABLE_CLOSURE_RESULT_KEY = "aion_global_durable_closure_result_v1"

AION_ADMIN_CSS = r"""
<style>
.aion-shell{
  position:relative;overflow:hidden;border:1px solid rgba(111,220,255,.28);
  border-radius:24px;padding:24px 26px;margin:4px 0 16px;
  background:
    radial-gradient(circle at 86% 8%,rgba(91,119,255,.22),transparent 30%),
    radial-gradient(circle at 8% 95%,rgba(45,225,198,.12),transparent 34%),
    linear-gradient(135deg,rgba(7,16,32,.98),rgba(10,30,50,.96) 58%,rgba(8,20,39,.98));
  box-shadow:0 24px 70px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.05);
  isolation:isolate;
}
.aion-shell:before{
  content:"";position:absolute;inset:-40%;z-index:-2;opacity:.16;
  background-image:linear-gradient(rgba(89,188,255,.18) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(89,188,255,.18) 1px,transparent 1px);
  background-size:34px 34px;transform:perspective(480px) rotateX(58deg) translateY(34%);
  transform-origin:center bottom;
}
.aion-orb{
  position:absolute;right:34px;top:28px;width:92px;height:92px;border-radius:50%;
  background:radial-gradient(circle at 35% 32%,#dffcff 0 7%,#7fe8ff 13%,#5574ff 38%,rgba(28,32,80,.2) 68%,transparent 72%);
  box-shadow:0 0 22px rgba(94,222,255,.58),0 0 70px rgba(81,99,255,.25);
  animation:aionPulse 4.2s ease-in-out infinite;
}
@keyframes aionPulse{0%,100%{transform:scale(.96);filter:brightness(.94)}50%{transform:scale(1.04);filter:brightness(1.12)}}
.aion-kicker{color:#73f1da;font-size:.72rem;font-weight:900;letter-spacing:.2em;text-transform:uppercase}
.aion-title{color:#fff;font-size:clamp(1.8rem,4vw,3rem);font-weight:950;letter-spacing:-.045em;line-height:1;margin-top:4px}
.aion-sub{color:#d9e8fa;max-width:820px;font-size:.9rem;line-height:1.5;margin-top:8px;padding-right:112px}
.aion-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}
.aion-chip{border:1px solid rgba(133,196,235,.28);background:rgba(9,24,45,.58);color:#eef8ff;border-radius:999px;padding:5px 10px;font-size:.7rem;font-weight:800}
.aion-chip.ok{color:#73f1da}.aion-chip.warn{color:#ffd56b}.aion-chip.off{color:#c7d2e3}
.aion-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 16px}
.aion-card{position:relative;border:1px solid rgba(126,177,218,.22);border-radius:16px;padding:13px 14px;background:linear-gradient(160deg,rgba(18,42,70,.86),rgba(8,23,42,.88));box-shadow:0 10px 30px rgba(0,0,0,.15)}
.aion-card small{display:block;color:#bcd0e8;font-size:.66rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
.aion-card strong{display:block;color:#fff;font-size:.94rem;margin-top:4px;overflow-wrap:anywhere}
.aion-card span{display:block;color:#d3deec;font-size:.72rem;line-height:1.35;margin-top:3px}
.aion-truth{border-left:3px solid #73f1da;border-radius:10px;padding:10px 12px;background:rgba(27,69,73,.28);color:#e9fffb;font-size:.78rem;margin:8px 0 14px}
.aion-panel{border:1px solid rgba(126,177,218,.18);border-radius:16px;padding:14px 15px;background:rgba(9,24,43,.62);margin:8px 0 12px}
.aion-panel h4{color:#fff;margin:.1rem 0 .5rem}.aion-panel p{color:#dce7f5;margin:.2rem 0;font-size:.82rem}
.aion-workspace-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:9px 0 16px}
.aion-workspace-card{border:1px solid rgba(126,177,218,.2);border-radius:15px;padding:12px 13px;background:rgba(8,24,43,.72);min-height:104px}
.aion-workspace-card .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.aion-workspace-card strong{color:#fff;font-size:.88rem;line-height:1.2}
.aion-workspace-card p{color:#cbd9e9;font-size:.72rem;line-height:1.38;margin:7px 0 0}
.aion-state{border-radius:999px;padding:3px 7px;font-size:.61rem;font-weight:900;letter-spacing:.05em;white-space:nowrap}
.aion-state.ok{color:#73f1da;background:rgba(34,112,99,.25);border:1px solid rgba(115,241,218,.26)}
.aion-state.info{color:#b9d8ff;background:rgba(52,92,145,.25);border:1px solid rgba(137,190,255,.24)}
.aion-state.warn{color:#ffd56b;background:rgba(132,91,20,.24);border:1px solid rgba(255,213,107,.26)}
.aion-state.blocked{color:#ffc2c2;background:rgba(120,45,55,.24);border:1px solid rgba(255,160,170,.24)}
.aion-pulse{border:1px solid rgba(132,207,255,.28);border-radius:18px;padding:15px 16px;margin:8px 0 14px;background:linear-gradient(145deg,rgba(10,28,50,.96),rgba(8,20,37,.97));box-shadow:0 12px 34px rgba(0,0,0,.16)}
.aion-pulse-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.aion-pulse-kicker{color:#9fb8d7;font-size:.68rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
.aion-pulse-title{color:#fff;font-size:1rem;font-weight:950;line-height:1.25;margin-top:3px;overflow-wrap:anywhere}
.aion-pulse-detail{color:#e2edf9;font-size:.78rem;line-height:1.45;margin-top:7px}
.aion-pulse-next{color:#dffbf5;font-size:.78rem;line-height:1.45;margin-top:8px}
.aion-pulse-badge{border-radius:999px;padding:5px 9px;font-size:.66rem;font-weight:950;letter-spacing:.06em;white-space:nowrap;border:1px solid rgba(255,255,255,.16)}
.aion-pulse-badge.critical{color:#ffd6d6;background:rgba(132,38,52,.34)}
.aion-pulse-badge.attention{color:#ffe7a3;background:rgba(130,89,18,.32)}
.aion-pulse-badge.review{color:#cde7ff;background:rgba(45,87,133,.33)}
.aion-pulse-badge.controlled{color:#bff8e9;background:rgba(32,111,94,.3)}
.aion-pulse-badge.unknown{color:#e6eaf0;background:rgba(83,92,108,.32)}
.aion-pulse-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px}
.aion-pulse-stat{border:1px solid rgba(137,187,225,.18);border-radius:12px;padding:9px 10px;background:rgba(13,34,58,.72);min-width:0}
.aion-pulse-stat small{display:block;color:#c3d5e9;font-size:.63rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.aion-pulse-stat strong{display:block;color:#fff;font-size:.86rem;margin-top:3px;overflow-wrap:anywhere}
.aion-card small,.aion-workspace-card p{color:#d8e6f5}
.aion-card span{color:#e2ebf6;font-size:.76rem}
.aion-workspace-card p{font-size:.76rem}
@media (prefers-reduced-motion:reduce){.aion-orb{animation:none!important}}
@media(max-width:760px){
 .aion-shell{padding:18px 16px;border-radius:18px}.aion-orb{width:58px;height:58px;right:16px;top:20px}
 .aion-sub{padding-right:64px;font-size:.8rem}.aion-grid{grid-template-columns:1fr 1fr}.aion-card{padding:11px 12px}
 .aion-workspace-grid{grid-template-columns:1fr 1fr}.aion-workspace-card{min-height:98px;padding:10px 11px}
 .aion-pulse-grid{grid-template-columns:1fr 1fr}.aion-pulse{padding:13px 12px}.aion-pulse-top{gap:8px}
}
@media(max-width:430px){
 .aion-workspace-grid{grid-template-columns:1fr}
 .aion-pulse-grid{grid-template-columns:1fr}
 .aion-pulse-top{display:block}.aion-pulse-badge{display:inline-block;margin-top:8px}
}

</style>
"""


def _secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except Exception:
        value = os.getenv(name, default)
    return str(value or default).strip()


def _provider_env() -> dict[str, str]:
    names = (
        "AION_MODEL_PROVIDER",
        "OPENAI_API_KEY",
        "AION_OPENAI_FAST_MODEL",
        "AION_OPENAI_REASONING_MODEL",
        "AION_OPENAI_INPUT_USD_PER_MTOK",
        "AION_OPENAI_OUTPUT_USD_PER_MTOK",
        "AION_OPENAI_MAX_OUTPUT_TOKENS",
        "AION_OPENAI_TIMEOUT_SECONDS",
    )
    return {name: _secret(name) for name in names}


def _context_voice(area: str, transcript: str, *, key: str) -> None:
    if render_neural_voice_player is None:
        return
    with st.expander(f"🔊 Assistente de voz · {area}", expanded=False):
        st.caption(
            "A voz é opcional e nunca toca sozinha. Se houver provedor de voz pago configurado, "
            "o clique para gerar áudio pode consumir esse serviço."
        )
        render_neural_voice_player(
            transcript,
            key=key,
            button_label=f"🔊 Ouvir AION · {area}",
        )


def _runtime_config():
    values = {
        "GITHUB_TOKEN_HISTORICO": _secret("GITHUB_TOKEN_HISTORICO"),
        "GITHUB_REPO_HISTORICO": _secret("GITHUB_REPO_HISTORICO"),
        "GITHUB_DATA_BRANCH": _secret("GITHUB_DATA_BRANCH"),
        "GITHUB_BRANCH_HISTORICO": _secret("GITHUB_BRANCH_HISTORICO"),
    }
    return config_from_mapping(values)


def _display_name(access: Mapping[str, Any]) -> str:
    configured = _secret("AION_ADMIN_DISPLAY_NAME")
    if configured:
        return configured[:64]
    session = access.get("session") if isinstance(access.get("session"), Mapping) else {}
    username = str(access.get("username") or session.get("username") or "").strip()
    return username[:64] if username else "Administrador"


def _flag_overrides() -> dict[str, bool]:
    out: dict[str, bool] = {}
    for key in RISKY_EXTERNAL_FEATURES:
        raw = _secret(f"AION_FF_{key.upper()}")
        if raw:
            out[key] = raw.casefold() in {"1", "true", "yes", "on", "sim"}
    return out


def _status_chip(runtime_status: str, provider_state: str) -> str:
    runtime_ok = runtime_status == "CONFIRMED"
    provider_local = provider_state == "ZERO_COST_LOCAL"
    return (
        f'<span class="aion-chip {"ok" if runtime_ok else "warn"}">MEMÓRIA {runtime_status}</span>'
        f'<span class="aion-chip {"ok" if provider_local else "warn"}">IA {provider_state}</span>'
        '<span class="aion-chip ok">GUARDIAN ATIVO</span>'
        '<span class="aion-chip ok">CUSTO ZERO PADRÃO</span>'
    )


def _render_header(
    access: Mapping[str, Any],
    runtime_status: str,
    provider_state: str,
    system_context: Mapping[str, Any],
) -> None:
    name = escape(_display_name(access))
    build = escape(str(system_context.get("source_build") or "não confirmado"))
    env = escape(str(system_context.get("environment") or "LOCAL"))
    st.markdown(AION_ADMIN_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="aion-shell">
  <div class="aion-orb" aria-hidden="true"></div>
  <div class="aion-kicker">Administrator Intelligence Operating Network</div>
  <div class="aion-title">AION // COMMAND CENTER</div>
  <div class="aion-sub">
    {name}, esta é a central administrativa do AtlasQuant. O AION organiza contexto,
    memória, desenvolvimento, Studio, Negócios e Laboratório sem ultrapassar o Guardian.
    Build informado pelo app: <strong>{build}</strong> · ambiente <strong>{env}</strong>.
  </div>
  <div class="aion-chips">{_status_chip(runtime_status, provider_state)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aion-truth"><strong>Regra da Verdade:</strong> '
        'se a fonte não estiver confirmada, o AION declara que não sabe ou que precisa verificar. '
        'Nenhum estado externo é inventado.</div>',
        unsafe_allow_html=True,
    )


def _render_admin_brief(access: Mapping[str, Any], executive_snapshot: Mapping[str, Any]) -> None:
    greeting = admin_greeting(access, _display_name(access))
    if not greeting:
        return
    items = "".join(f"<li>{escape(line)}</li>" for line in admin_brief_lines(executive_snapshot))
    st.markdown(
        f'<div class="aion-truth" id="aion-admin-brief"><strong>{escape(greeting)}</strong>'
        f'<ul style="margin:6px 0 0 18px;padding:0">{items}</ul></div>',
        unsafe_allow_html=True,
    )


def _render_persona_capabilities(persona_id: str, availability: Mapping[str, Any]) -> None:
    snapshot = capability_snapshot(persona_id, availability)
    connected = [row["capability"] for row in snapshot["capabilities"] if row["state"] == "CONNECTED"]
    unavailable = [row["capability"] for row in snapshot["capabilities"] if row["state"] != "CONNECTED"]
    st.caption(
        f"Capacidades conectadas: {snapshot.get('connected', 0)}/{snapshot.get('total', 0)} · "
        + (", ".join(connected) if connected else "nenhuma fonte confirmada")
    )
    if unavailable:
        st.caption("Não configurado/indisponível nesta execução: " + ", ".join(unavailable) + ".")


def _working_checkpoint(source: Mapping[str, Any]) -> dict[str, Any]:
    seed = ensure_operating_checkpoint(source)
    source_digest = checkpoint_source_digest(seed)
    current = st.session_state.get(_WORKING_CHECKPOINT_KEY)
    dirty = bool(st.session_state.get(_WORKING_DIRTY_KEY, False))
    known_source = str(st.session_state.get(_WORKING_SOURCE_KEY) or "")
    if not isinstance(current, Mapping) or (known_source != source_digest and not dirty):
        st.session_state[_WORKING_CHECKPOINT_KEY] = deepcopy(seed)
        st.session_state[_WORKING_SOURCE_KEY] = source_digest
        st.session_state[_WORKING_DIRTY_KEY] = False
        st.session_state[_WORKING_CONFLICT_KEY] = False
    else:
        st.session_state[_WORKING_CONFLICT_KEY] = bool(
            dirty and known_source and known_source != source_digest
        )
    return ensure_operating_checkpoint(st.session_state[_WORKING_CHECKPOINT_KEY])


def _set_working_checkpoint(checkpoint: Mapping[str, Any], *, dirty: bool = True) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    payload["operating"]["dirty"] = bool(dirty)
    st.session_state[_WORKING_CHECKPOINT_KEY] = payload
    st.session_state[_WORKING_DIRTY_KEY] = bool(dirty)
    return payload


def _record_working_event(
    checkpoint: Mapping[str, Any],
    event_type: str,
    message: str,
    *,
    severity: str = "INFO",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    operating = payload["operating"]
    events = append_event(
        operating.get("events", []),
        new_event(
            event_type,
            message,
            severity=severity,
            source="AION_ADMIN",
            truth_state="CONFIRMED",
            evidence=evidence or {},
        ),
    )
    return update_operating_checkpoint(payload, events=events, dirty=True)


def _safe_market_state(market_context: Mapping[str, Any]) -> tuple[str, str]:
    fresh = bool(market_context.get("fresh_confirmed", False))
    summary = str(market_context.get("summary") or "").strip()
    if fresh and summary:
        return summary, "CONFIRMADO"
    return "Sem leitura fresca confirmada nesta tela.", "NÃO CONFIRMADO"


def _unknown_account_entitlement_audit(error_type: str) -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
        "truth_state": "UNKNOWN",
        "reason": str(error_type or "UNKNOWN")[:120],
        "scope": "APP_ACCESS",
        "accounts_total": 0,
        "active_user_accounts": 0,
        "effective_user_accounts": 0,
        "user_accounts_without_effective_entitlement": 0,
        "duplicate_effective_user_accounts": 0,
        "orphan_effective_entitlements": 0,
        "account_rows": [],
        "orphan_rows": [],
        "enforcement_enabled": False,
        "authentication_changed": False,
        "automatic_provisioning": False,
        "automatic_revocation": False,
        "real_trading_changed": False,
    }


def _unknown_status_board(error_type: str) -> dict[str, Any]:
    item = {
        "id": "aion_foundation_degraded",
        "label": "Painel Mestre de Estado",
        "area": "central",
        "state": "UNKNOWN",
        "detail": "Painel Mestre indisponível nesta execução; nenhum estado positivo foi inferido.",
        "source": f"AION safe fallback · {str(error_type or 'UNKNOWN')[:120]}",
        "next_action": "Recarregar a área e revisar a camada auxiliar antes de qualquer ação sensível.",
        "executes_action": False,
    }
    return {
        "schema": "ATLASQUANT_AION_MASTER_STATUS_V1",
        "states": ["CONFIRMED", "BLOCKED", "EXTERNAL_DEPENDENCY", "UNKNOWN"],
        "items": [item],
        "counts": {
            "CONFIRMED": 0,
            "BLOCKED": 0,
            "EXTERNAL_DEPENDENCY": 0,
            "UNKNOWN": 1,
        },
        "attention": [item],
        "has_unresolved": True,
        "real_orders_enabled": False,
        "automatic_external_actions": False,
    }


def _unknown_approval_inbox(error_type: str) -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_APPROVAL_INBOX_V1",
        "status": "UNKNOWN",
        "reason": str(error_type or "UNKNOWN")[:120],
        "items": [],
        "total": 0,
        "by_kind": {},
        "by_priority": {},
        "has_pending": False,
        "next_items": [],
        "automatic_approval": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def _render_executive_grid(
    memory_summary: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    provider: Mapping[str, Any],
    market_context: Mapping[str, Any],
) -> None:
    market_text, market_truth = _safe_market_state(market_context)
    docs = int(memory_summary.get("document_count") or 0)
    runtime_status = str(runtime_result.get("status") or "UNKNOWN")
    st.markdown(
        f"""
<div class="aion-grid">
 <div class="aion-card"><small>Memória canônica</small><strong>{docs} fontes</strong><span>Documentos versionados do projeto + fundação AION.</span></div>
 <div class="aion-card"><small>Checkpoint runtime</small><strong>{runtime_status}</strong><span>Persistência mutável só é afirmada quando confirmada.</span></div>
 <div class="aion-card"><small>Modelo</small><strong>{provider.get("state","UNKNOWN")}</strong><span>Sem cobrança automática; modelo externo desligado por padrão.</span></div>
 <div class="aion-card"><small>Mercado</small><strong>{market_truth}</strong><span>{market_text}</span></div>
</div>
        """,
        unsafe_allow_html=True,
    )



def _workspace_overview_items(
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
) -> list[dict[str, str]]:
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = list(operating.get("tasks", []) or [])
    task_summary = queue_summary(tasks)

    studio = checkpoint.get("studio") if isinstance(checkpoint.get("studio"), Mapping) else {}
    business = checkpoint.get("business") if isinstance(checkpoint.get("business"), Mapping) else {}
    promotions = checkpoint.get("promotions") if isinstance(checkpoint.get("promotions"), Mapping) else {}
    entitlements = checkpoint.get("entitlements") if isinstance(checkpoint.get("entitlements"), Mapping) else {}

    projects = list(studio.get("projects", []) or [])
    products = list(business.get("products", []) or [])
    campaigns = list(promotions.get("campaigns", []) or [])
    records = list(entitlements.get("records", []) or [])
    runtime_status = str(runtime_result.get("status") or "UNKNOWN").upper()

    runtime_tone = "ok" if runtime_status == "CONFIRMED" else "warn"
    return [
        {
            "name": "🧠 Central",
            "state": "ATIVA",
            "tone": "ok",
            "detail": "Comando, memória, estado mestre e perguntas ao AION.",
        },
        {
            "name": "🗂️ Secretaria",
            "state": f"{int(task_summary.get('active') or 0)} ATIVAS",
            "tone": "info",
            "detail": "Tarefas, pendências, aprovações e briefing executivo.",
        },
        {
            "name": "📈 Trading",
            "state": "REAL BLOQUEADO",
            "tone": "blocked",
            "detail": "Leitura e contexto podem existir; ordens reais continuam bloqueadas.",
        },
        {
            "name": "🎬 Studio",
            "state": f"{len(projects)} PROJETOS",
            "tone": "info",
            "detail": "Conteúdo, roteiros e preparação de publicação com aprovação.",
        },
        {
            "name": "💼 Negócios",
            "state": f"{len(products)} CANDIDATOS",
            "tone": "info",
            "detail": "Produtos, margem, fornecedores e evidências de tendência.",
        },
        {
            "name": "🧪 Laboratório",
            "state": "GUARDIAN ATIVO",
            "tone": "ok",
            "detail": "Sandbox, feature flags, orçamento e testes antes de promoção.",
        },
        {
            "name": "🛠️ Desenvolvimento",
            "state": runtime_status,
            "tone": runtime_tone,
            "detail": "Missões de código e Checkpoint Mestre com persistência verificada.",
        },
        {
            "name": "🔐 Assinaturas",
            "state": f"{len(records)} REGISTROS",
            "tone": "info",
            "detail": "Entitlements, auditoria de acesso e isolamento por assinante.",
        },
        {
            "name": "🎟️ Promoções",
            "state": f"{len(campaigns)} CAMPANHAS",
            "tone": "info",
            "detail": "Cupons, trials e descontos separados do direito de acesso.",
        },
    ]


def _render_workspace_overview(
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
) -> None:
    st.markdown("#### Mapa Operacional AION")
    st.caption(
        "Visão rápida das 9 áreas administrativas. O mapa é somente leitura: "
        "não aprova, publica, cobra, provisiona acesso nem envia ordens."
    )
    cards = []
    for item in _workspace_overview_items(checkpoint, runtime_result):
        cards.append(
            '<div class="aion-workspace-card">'
            '<div class="top">'
            f'<strong>{escape(item["name"])}</strong>'
            f'<span class="aion-state {escape(item["tone"])}">{escape(item["state"])}</span>'
            '</div>'
            f'<p>{escape(item["detail"])}</p>'
            '</div>'
        )
    st.markdown(
        '<div class="aion-workspace-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Abrir área · navegação stateful na mesma sessão ADMIN; nenhum card executa "
        "ação externa por conta própria."
    )
    buttons = st.columns(3)
    for index, workspace in enumerate(AION_WORKSPACES):
        with buttons[index % 3]:
            if st.button(
                "Abrir " + workspace,
                key=f"aion_workspace_overview_open_{index}",
                width="stretch",
            ):
                st.session_state[_AION_WORKSPACE_JUMP_KEY] = workspace
                st.rerun()



def _local_contract_snapshot() -> dict[str, Any]:
    """Cheap/passive contract posture. It does not run handlers or the full auditor."""
    allow = [dict(item) for item in local_allowlist() if isinstance(item, Mapping)]
    hub = default_tool_hub()
    tools = [
        dict(item)
        for item in list((hub.get("tools") if isinstance(hub, Mapping) else []) or [])
        if isinstance(item, Mapping)
    ]
    local_ids = [str(item.get("tool_id") or "") for item in allow if str(item.get("tool_id") or "")]
    trace_ids = set(str(item) for item in SOURCE_CATALOG)
    write_id = "aion.checkpoint.prepare_save"
    safe_kinds = {"READ", "SEARCH", "DRAFT"}
    issues = []

    if len(local_ids) != 11 or len(set(local_ids)) != 11:
        issues.append("LOCAL_ALLOWLIST_COUNT")
    if write_id in local_ids:
        issues.append("WRITE_IN_LOCAL_ALLOWLIST")
    if any(str(item.get("kind") or "") not in safe_kinds for item in allow):
        issues.append("FORBIDDEN_KIND_IN_ALLOWLIST")
    if set(local_ids) != trace_ids:
        issues.append("TRACEABILITY_COVERAGE_MISMATCH")

    hub_index = {str(item.get("tool_id") or ""): item for item in tools}
    for tool_id in local_ids:
        item = hub_index.get(tool_id)
        if not item:
            issues.append("LOCAL_TOOL_MISSING_FROM_HUB")
            break
        if (
            str(item.get("state") or "") != "LOCAL_READY"
            or bool(item.get("connector_id"))
            or bool(item.get("external_side_effects"))
        ):
            issues.append("LOCAL_TOOL_HUB_FLAGS")
            break

    write = hub_index.get(write_id) or {}
    if str(write.get("kind") or "") != "WRITE":
        issues.append("WRITE_CONTRACT_MISSING")

    kind_counts = {"READ": 0, "SEARCH": 0, "DRAFT": 0}
    for item in allow:
        kind = str(item.get("kind") or "")
        if kind in kind_counts:
            kind_counts[kind] += 1

    return {
        "schema": "ATLASQUANT_AION_LOCAL_CONTRACT_SNAPSHOT_V1",
        "state": "FAIL" if issues else "PASS",
        "issues": sorted(set(issues)),
        "registry_tools": len(tools),
        "local_tools": len(local_ids),
        "trace_sources": len(trace_ids),
        "contract_fingerprint": local_contract_fingerprint(hub),
        "kind_counts": kind_counts,
        "write_in_allowlist": write_id in local_ids,
        "full_audit_executed": False,
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }


def _render_local_contract_health() -> None:
    snapshot = _local_contract_snapshot()
    st.markdown("#### Saúde dos contratos locais")
    st.caption(
        "Postura passiva e auditoria offline do caminho local do AION. "
        "Abrir este painel não executa handler, não chama rede, não publica, não faz deploy "
        "e não envia ordens."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contrato estático", str(snapshot.get("state") or "UNKNOWN"))
    c2.metric("Tools locais", int(snapshot.get("local_tools") or 0))
    c3.metric("Fontes rastreáveis", int(snapshot.get("trace_sources") or 0))
    c4.metric("WRITE na allowlist", "NÃO" if not snapshot.get("write_in_allowlist") else "SIM")

    kinds = snapshot.get("kind_counts") if isinstance(snapshot.get("kind_counts"), Mapping) else {}
    st.caption(
        "Allowlist: "
        f"READ {int(kinds.get('READ') or 0)} · "
        f"SEARCH {int(kinds.get('SEARCH') or 0)} · "
        f"DRAFT {int(kinds.get('DRAFT') or 0)} · "
        f"registry total {int(snapshot.get('registry_tools') or 0)}. "
        f"Selo: {str(snapshot.get('contract_fingerprint') or 'UNKNOWN')}."
    )
    if snapshot.get("state") == "PASS":
        st.success(
            "Contrato estático local coerente nesta renderização. "
            "Isso não substitui a auditoria completa nem autoriza ação."
        )
    else:
        st.error(
            "Drift detectado no contrato estático local: "
            + " · ".join(str(x) for x in list(snapshot.get("issues") or []))
        )

    report = (
        st.session_state.get("aion_contract_audit_report")
        if isinstance(st.session_state.get("aion_contract_audit_report"), Mapping)
        else None
    )
    if st.button(
        "Rodar auditor local",
        key="aion_run_contract_audit",
        help=(
            "Executa somente o auditor offline/local. "
            "Não usa rede, connector, deploy, publicação, pagamento ou trading real."
        ),
    ):
        try:
            from atlasquant_aion_contract_auditor import audit_aion_local_contracts

            report = audit_aion_local_contracts()
        except Exception as exc:
            report = {
                "schema": "ATLASQUANT_AION_CONTRACT_AUDIT_V1",
                "state": "ERROR",
                "checks_total": 0,
                "passed": 0,
                "failed": 1,
                "warnings": [],
                "findings": [{
                    "invariant_id": "audit.runtime",
                    "module": "atlasquant_aion_contract_auditor",
                    "description": "Falha isolada do auditor: " + type(exc).__name__,
                    "severity": "FAIL",
                }],
                "executes_action": False,
                "external_action_executed": False,
                "real_orders_enabled": False,
                "tool_output_is_authority": False,
            }
        st.session_state["aion_contract_audit_report"] = report

    if not isinstance(report, Mapping):
        st.info(
            "Auditoria completa ainda não foi rodada nesta sessão. "
            "Clique no botão apenas quando quiser executar os checks offline."
        )
        return

    state = str(report.get("state") or "UNKNOWN").upper()
    warnings = [
        item for item in list(report.get("warnings") or [])
        if isinstance(item, Mapping)
    ]
    findings = [
        item for item in list(report.get("findings") or [])
        if isinstance(item, Mapping)
    ]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Auditoria completa", state)
    a2.metric("Checks", int(report.get("checks_total") or 0))
    a3.metric("Falhas", int(report.get("failed") or 0))
    a4.metric("Avisos", len(warnings))

    if state == "PASS" and not findings:
        st.success(
            f"Auditor local PASS · {int(report.get('passed') or 0)}/"
            f"{int(report.get('checks_total') or 0)} grupos sem drift confirmado."
        )
    else:
        st.error(
            "Auditoria local encontrou falha ou não pôde confirmar o contrato. "
            "Nenhuma correção é executada automaticamente."
        )

    rows = []
    for item in (findings + warnings)[:20]:
        rows.append({
            "Tipo": str(item.get("severity") or "FAIL"),
            "Invariante": str(item.get("invariant_id") or ""),
            "Módulo": str(item.get("module") or ""),
            "Descrição": str(item.get("description") or ""),
        })
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)

    st.caption(
        "Resultado diagnóstico somente leitura. PASS não concede autoridade; "
        "FAIL não dispara reparo, merge, deploy, publicação, cobrança ou trading."
    )



_AION_AREA_LABELS = {
    "central": "🧠 Central",
    "secretary": "🗂️ Secretaria",
    "trading": "📈 Trading",
    "studio": "🎬 Studio",
    "business": "💼 Negócios",
    "laboratory": "🧪 Laboratório",
    "development": "🛠️ Desenvolvimento",
    "subscriptions": "🔐 Assinaturas",
    "promotions": "🎟️ Promoções",
    "memory": "🛠️ Desenvolvimento",
    "system": "🛠️ Desenvolvimento",
}


def _aion_area_label(area: Any) -> str:
    raw = str(area or "central").strip().casefold()
    return _AION_AREA_LABELS.get(raw, str(area or "🧠 Central"))


def _attention_queue(
    status_board: Mapping[str, Any] | None,
    approval_inbox: Mapping[str, Any] | None,
    critical_surfaces: Mapping[str, Any] | None = None,
    release_gate_snapshot: Mapping[str, Any] | None = None,
    *,
    limit: int = 8,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    inbox = dict(approval_inbox or {})
    if str(inbox.get("status") or "CONFIRMED").upper() != "UNKNOWN":
        for item in list(inbox.get("next_items", []) or []):
            if not isinstance(item, Mapping):
                continue
            rows.append({
                "priority": str(item.get("priority") or "P2"),
                "source": "APROVAÇÃO",
                "area": _aion_area_label(item.get("area")),
                "item": str(item.get("title") or item.get("item_id") or "Item sem título"),
                "state": str(item.get("status") or "WAITING_APPROVAL"),
                "next_action": "Revisar na área indicada; nenhuma aprovação é automática.",
            })

    gate = dict(release_gate_snapshot or {})
    gate_state = str(gate.get("state") or "").upper()
    gate_available = bool(gate_state)
    if gate_available and gate_state != "COMPLETE":
        rows.append({
            "priority": "P1" if gate_state == "BLOCKED" else "P2",
            "source": "RELEASE GATE",
            "area": "🛠️ Desenvolvimento",
            "item": str(
                gate.get("next_label")
                or "Gate de liberação AION"
            ),
            "state": gate_state,
            "next_action": str(
                gate.get("next_action")
                or "Revisar a próxima etapa do Gate de liberação AION."
            ),
        })

    # Compatibility fallback for callers that still provide only surface health.
    # When the unified release gate exists, individual surface alerts remain in
    # the diagnostic panel instead of duplicating the administrative queue.
    if not gate_available:
        surface_snapshot = dict(critical_surfaces or {})
        for item in list(surface_snapshot.get("items", []) or []):
            if not isinstance(item, Mapping):
                continue
            state = str(item.get("state") or "UNKNOWN").upper()
            if state == "OK":
                continue
            priority = "P1" if state in {"DEGRADED", "UNAVAILABLE"} else "P2"
            rows.append({
                "priority": priority,
                "source": "TELA",
                "area": "🛠️ Desenvolvimento",
                "item": str(item.get("label") or item.get("id") or "Tela crítica"),
                "state": state,
                "next_action": str(
                    item.get("next_action")
                    or "Revalidar a tela no build atual antes de concluir que está saudável."
                ),
            })

    board = dict(status_board or {})
    for item in list(board.get("attention", []) or []):
        if not isinstance(item, Mapping):
            continue
        next_action = str(item.get("next_action") or "").strip()
        if not next_action:
            continue
        state = str(item.get("state") or "UNKNOWN").upper()
        priority = "P1" if state == "UNKNOWN" else ("P2" if state == "EXTERNAL_DEPENDENCY" else "P3")
        rows.append({
            "priority": priority,
            "source": "ESTADO",
            "area": _aion_area_label(item.get("area")),
            "item": str(item.get("label") or item.get("id") or "Estado sem rótulo"),
            "state": state,
            "next_action": next_action,
        })

    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    rows.sort(key=lambda row: (
        rank.get(str(row.get("priority") or "P3"), 9),
        0 if row.get("source") == "APROVAÇÃO" else 1,
        str(row.get("area") or ""),
        str(row.get("item") or ""),
    ))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("source") or ""),
            str(row.get("area") or ""),
            str(row.get("item") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= max(1, int(limit)):
            break
    return deduped


def _render_attention_queue(
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
    critical_surfaces: Mapping[str, Any] | None = None,
    release_gate_snapshot: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("#### Próxima Ação AION")
    st.caption(
        "Fila consolidada de atenção. Ela orienta o administrador, mas não aprova, "
        "não publica, não cobra, não provisiona acesso e não executa trading."
    )
    rows = _attention_queue(
        status_board,
        approval_inbox,
        critical_surfaces,
        release_gate_snapshot,
    )
    if not rows:
        st.success(
            "Nenhuma ação administrativa imediata foi identificada nas evidências atuais. "
            "Isso não substitui validação externa de produção."
        )
        return

    first = rows[0]
    st.info(
        f"**{first['priority']} · {first['area']} · {first['item']}** — "
        f"{first['next_action']}"
    )
    st.dataframe(
        [{
            "Prioridade": row["priority"],
            "Origem": row["source"],
            "Área": row["area"],
            "Item": row["item"],
            "Estado": row["state"],
            "Próxima ação segura": row["next_action"],
        } for row in rows],
        width="stretch",
        hide_index=True,
    )


def _render_memory_security_posture(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("#### Memória & Guardian")
    st.caption(
        "Auditoria somente leitura da integridade do Checkpoint e da postura de segurança. "
        "Este painel não serve como aprovação para nenhuma ação sensível."
    )

    persisted = (
        runtime_result.get("integrity")
        if isinstance(runtime_result.get("integrity"), Mapping)
        else {"state": "UNKNOWN", "matched": 0, "total": 0}
    )
    working = checkpoint_integrity_report(checkpoint)
    preflight = runtime_write_preflight(runtime_result)
    posture = guardian_posture(access, feature_flags=flags)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Integridade runtime", str(persisted.get("state") or "UNKNOWN"))
    c2.metric(
        "Memória de trabalho",
        str(working.get("state") or "UNKNOWN"),
        delta=f"V{int(working.get('checkpoint_version') or 0)}",
    )
    c3.metric("Guardian bloqueando agora", int(posture.get("blocked_now") or 0))
    c4.metric("Escrita runtime", "ELEGÍVEL" if preflight.get("allowed") else "BLOQUEADA")

    portable = portable_core_summary(
        checkpoint.get("portable_core")
        if isinstance(checkpoint.get("portable_core"), Mapping)
        else {}
    )
    vault = vault_summary(
        checkpoint.get("vault")
        if isinstance(checkpoint.get("vault"), Mapping)
        else {}
    )
    entry = central_entry_contract(authenticated_admin=is_admin(access))
    p1,p2,p3,p4 = st.columns(4)
    p1.metric("AION Portable", f"{int(portable.get('workspaces') or 0)} workspaces")
    p2.metric("Conectores prontos", int(portable.get("ready_connectors") or 0))
    p3.metric("Vault", "SEGURO" if vault.get("policy_ok") else "BLOQUEADO")
    p4.metric("Entrada única", "PRONTA" if entry.get("allowed") else "BLOQUEADA")
    st.caption(
        "AtlasQuant é um workspace do AION. O Vault armazena referências e integridade, "
        "não senha/token em texto puro. Entrada única exige sessão ADMIN."
    )

    persisted_state = str(persisted.get("state") or "UNKNOWN").upper()
    if persisted_state == "MISMATCH":
        st.error(
            "Divergência de digest detectada no Checkpoint persistido. "
            "A escrita fica bloqueada até revisão; o AION não sobrescreve esse estado automaticamente."
        )
    elif persisted_state == "MIGRATION_REQUIRED":
        st.warning(
            "Checkpoint persistido requer migração estrutural para a versão canônica atual. "
            "A migração só poderá ser salva por escrita condicional e aprovação explícita."
        )
    elif persisted_state == "CONFIRMED":
        st.success(
            f"Integridade persistida confirmada em "
            f"{int(persisted.get('matched') or 0)}/{int(persisted.get('total') or 0)} componentes."
        )
    else:
        st.info(
            "Integridade persistida ainda não está confirmada nesta execução. "
            "A memória local não será tratada como prova de persistência."
        )

    rows = []
    for item in list(posture.get("actions", []) or []):
        if not isinstance(item, Mapping):
            continue
        rows.append({
            "Ação sensível": item.get("action"),
            "Risco": item.get("risk"),
            "Estado agora": "PERMITIDA" if item.get("allowed_now") else "BLOQUEADA",
            "Flag": item.get("feature_flag") or "—",
            "Motivo": item.get("reason"),
        })
    if rows:
        with st.expander("Matriz Guardian · ações sensíveis", expanded=False):
            st.dataframe(rows, width="stretch", hide_index=True)
            st.caption(
                "A matriz é calculada com approved=False. Ela nunca reutiliza esta visualização "
                "como autorização para publicar, cobrar, fazer deploy, gravar segredo ou operar."
            )

    with st.expander("AION Portable Core & Vault", expanded=False):
        st.markdown("**Workspaces registrados:**")
        for item in list(
            ((checkpoint.get("portable_core") or {}) if isinstance(checkpoint.get("portable_core"), Mapping) else {}).get("workspaces", [])
            or []
        )[:20]:
            if isinstance(item, Mapping):
                st.caption(
                    f"{item.get('label')} · {item.get('kind')} · {item.get('state')} · "
                    f"contexto isolado: {'SIM' if item.get('isolated_context') else 'NÃO'}"
                )
        st.markdown("**Política do Vault:**")
        st.caption(
            f"Entradas: {int(vault.get('entries') or 0)} · "
            f"backend: {vault.get('backend_state','NOT_CONFIGURED')} · "
            f"segredo em texto puro: {'SIM — BLOQUEAR' if vault.get('plaintext_secrets_present') else 'NÃO'}."
        )
        st.caption(
            "O próprio AION não pode apagar o Vault, ampliar permissão ou transformar referência "
            "de segredo em valor exportável."
        )


def _render_security_incident_center(
    snapshot: Mapping[str, Any],
) -> None:
    st.markdown("#### 🛡️ Centro de Segurança & Incidentes")
    st.caption(
        "Consolida somente sinais explícitos desta execução e eventos do Checkpoint. "
        "O painel não faz contenção, rollback, rotação de segredo, alteração de conta ou trading."
    )
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Incidentes ativos", int(snapshot.get("total") or 0))
    c2.metric("Críticos", int(counts.get("CRITICAL") or 0))
    c3.metric("Altos", int(counts.get("HIGH") or 0))
    c4.metric(
        "Rollback",
        "REVISAR" if snapshot.get("rollback_review_recommended") else "SEM SINAL CONFIRMADO",
    )

    gw_reconciliation = (
        snapshot.get("global_worker_reconciliation")
        if isinstance(snapshot.get("global_worker_reconciliation"), Mapping)
        else {}
    )
    closed_rows = (
        global_worker_closed_incident_rows(snapshot)
        if global_worker_closed_incident_rows is not None
        else []
    )
    if gw_reconciliation:
        st.caption(
            "Reconciliação Worker Global: "
            + str(gw_reconciliation.get("state") or "UNKNOWN")
            + " · fechamentos duráveis: "
            + str(gw_reconciliation.get("durable_closure_records") or 0)
            + " · reativação autorizada: NÃO."
        )
        if gw_reconciliation.get("state") == "REOPENED":
            st.error(
                "REOPENED: surgiu novamente evidência do mesmo incidente após "
                "o fechamento durável. O incidente permanece ativo."
            )
        elif gw_reconciliation.get("state") == "NEW_INCIDENT_AFTER_CLOSURE":
            st.warning(
                "Há um novo incidente do Worker Global após fechamento anterior. "
                "O fechamento histórico não esconde a nova evidência."
            )
        elif gw_reconciliation.get("fail_open"):
            st.warning(
                "Reconciliação de fechamento indisponível/inválida; modo fail-open: "
                "incidentes atuais permanecem abertos."
            )

    rows = incident_center_rows(snapshot)
    if not rows:
        st.success(
            "Nenhum incidente ativo foi consolidado nesta execução. "
            "Isso não prova que produção/infraestrutura externa estejam saudáveis."
        )
        if closed_rows:
            with st.expander("Histórico de incidentes fechados", expanded=False):
                st.dataframe(closed_rows, width="stretch", hide_index=True)
                st.caption(
                    "Fechamento histórico não autoriza reativação do Worker e "
                    "não suprime evidência nova ou recorrente."
                )
        return

    st.dataframe(rows,width="stretch",hide_index=True)

    incidents=[
        dict(item)
        for item in list(snapshot.get("incidents",[]) or [])
        if isinstance(item,Mapping)
    ]
    incident_ids=[str(item.get("incident_id") or "") for item in incidents]
    labels={
        str(item.get("incident_id") or ""):
        f"{item.get('severity')} · {item.get('title')} · {str(item.get('incident_id') or '')[:10]}"
        for item in incidents
    }
    selected_id=st.selectbox(
        "Incidente para revisar",
        incident_ids,
        format_func=lambda value: labels.get(value,value),
        key="aion_incident_review_selected",
    )
    selected=next(
        (item for item in incidents if str(item.get("incident_id") or "")==selected_id),
        None,
    )
    if isinstance(selected,Mapping):
        st.write(f"**Origem:** {selected.get('source')} · **Evidência:** {selected.get('evidence_state')}")
        st.caption(str(selected.get("detail") or ""))
        plan=incident_response_plan(selected)
        with st.expander("Plano de resposta seguro",expanded=False):
            for idx,step in enumerate(plan.get("steps",[]),start=1):
                st.markdown(f"{idx}. {step}")
            st.caption(
                "Plano somente leitura · revisão humana obrigatória · rollback automático: NÃO · "
                "rotação automática de segredo: NÃO · trading real: BLOQUEADO."
            )

    if closed_rows:
        with st.expander("Histórico de incidentes fechados", expanded=False):
            st.dataframe(closed_rows, width="stretch", hide_index=True)
            st.caption(
                "Histórico durável somente leitura · novos sinais permanecem ativos · "
                "reativação autorizada: NÃO."
            )

    if snapshot.get("rollback_review_recommended"):
        reasons=list(snapshot.get("rollback_reasons",[]) or [])
        st.warning(
            "Há sinal confirmado para **revisão humana de rollback**. "
            "Isso não dispara rollback automaticamente."
        )
        for reason in reasons[:8]:
            st.markdown(f"- {reason}")


def _render_continuity_center(
    checkpoint: Mapping[str, Any],
) -> None:
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    briefing = continuity_briefing(
        missions,
        handoffs,
        tasks=list(operating.get("tasks", []) or []),
        events=list(operating.get("events", []) or []),
        checkpoint_digest=checkpoint_digest(checkpoint),
    )
    summary = briefing.get("mission_summary") if isinstance(briefing.get("mission_summary"), Mapping) else {}

    st.markdown("#### 🧭 Continuidade & Handoff")
    st.caption(
        "Visão derivada do Checkpoint Mestre carregado nesta sessão. "
        "Handoff persistido tem prioridade; na ausência dele, o AION sintetiza somente a partir de missões/tarefas registradas."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Missões ativas", int(summary.get("active_missions") or 0))
    c2.metric("Concluídas", int(summary.get("done_missions") or 0))
    c3.metric("Bloqueadas", int(summary.get("blocked_missions") or 0))
    c4.metric("Handoffs", int(summary.get("handoff_count") or 0))

    source = str(briefing.get("source") or "UNKNOWN")
    if source == "PERSISTED_HANDOFF":
        st.success("Continuidade baseada no último handoff registrado no Checkpoint.")
    else:
        st.info(
            "Ainda não há handoff persistido; a visão abaixo foi sintetizada do estado estruturado atual. "
            "Ela não inventa etapas concluídas."
        )

    focus = str(briefing.get("current_focus") or "").strip()
    if focus:
        st.write(f"**Onde paramos:** {focus}")
    else:
        st.write("**Onde paramos:** nenhuma missão ativa registrada no Checkpoint.")

    completed = list(briefing.get("recent_completed") or [])
    blockers = list(briefing.get("blockers") or [])
    next_steps = list(briefing.get("next_steps") or [])
    if completed:
        with st.expander("Últimas conclusões", expanded=False):
            for item in completed[:8]:
                st.markdown(f"- {item}")
    if blockers:
        with st.expander("Bloqueios registrados", expanded=False):
            for item in blockers[:8]:
                st.markdown(f"- {item}")
    if next_steps:
        st.markdown("**Próximos passos registrados:**")
        for item in next_steps[:8]:
            st.markdown(f"- {item}")


def _render_executive_pulse(snapshot: Mapping[str, Any]) -> None:
    posture = str(snapshot.get("posture") or "UNKNOWN").upper()
    primary = snapshot.get("primary") if isinstance(snapshot.get("primary"), Mapping) else {}
    badge_class = posture.casefold() if posture.casefold() in {"critical","attention","review","controlled","unknown"} else "unknown"
    title = escape(str(primary.get("title") or "Sem prioridade definida"))
    detail = escape(str(primary.get("detail") or ""))
    next_action = escape(str(primary.get("next_action") or ""))
    area = escape(str(primary.get("area") or "🧠 Central"))
    st.markdown(
        f"""
<div class="aion-pulse">
  <div class="aion-pulse-top">
    <div>
      <div class="aion-pulse-kicker">Pulso Executivo AION · {area}</div>
      <div class="aion-pulse-title">{title}</div>
      <div class="aion-pulse-detail">{detail}</div>
      <div class="aion-pulse-next"><strong>Próxima ação segura:</strong> {next_action}</div>
    </div>
    <span class="aion-pulse-badge {badge_class}">{escape(posture)}</span>
  </div>
  <div class="aion-pulse-grid">
    <div class="aion-pulse-stat"><small>Runtime</small><strong>{escape(str(snapshot.get("runtime_status") or "UNKNOWN"))}</strong></div>
    <div class="aion-pulse-stat"><small>Integridade</small><strong>{escape(str(snapshot.get("integrity_state") or "UNKNOWN"))}</strong></div>
    <div class="aion-pulse-stat"><small>Aprovações</small><strong>{int(snapshot.get("approval_count") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Incidentes</small><strong>{int(snapshot.get("incident_count") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Missões ativas</small><strong>{int(snapshot.get("active_missions") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Telas do build</small><strong>{int(snapshot.get("interface_validation_confirmed") or 0)}/{int(snapshot.get("interface_validation_total") or 3)}</strong></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    recommended = str(snapshot.get("recommended_workspace") or "")
    if recommended in AION_WORKSPACES and recommended != "🧠 Central":
        if st.button(
            f"↗️ Abrir área recomendada · {recommended}",
            key="aion_open_recommended_workspace",
            width="stretch",
        ):
            st.session_state[_AION_WORKSPACE_JUMP_KEY] = recommended
            st.rerun()
    rows = compact_attention_rows(snapshot)
    if len(rows) > 1:
        with st.expander("Outros itens priorizados", expanded=False):
            st.dataframe(rows, width="stretch", hide_index=True)


def _render_commander_intelligence(
    checkpoint: Mapping[str, Any],
    system_context: Mapping[str, Any],
    executive_snapshot: Mapping[str, Any],
) -> None:
    snapshot = (
        system_context.get("commander_snapshot")
        if isinstance(system_context.get("commander_snapshot"), Mapping)
        else commander_briefing(
            checkpoint=checkpoint,
            system_context=system_context,
            executive_snapshot=executive_snapshot,
        )
    )
    audit = snapshot.get("audit") if isinstance(snapshot.get("audit"), Mapping) else {}
    confidence = (
        snapshot.get("evidence_confidence")
        if isinstance(snapshot.get("evidence_confidence"), Mapping)
        else {}
    )

    st.markdown("#### 🧭 Modo Comandante")
    st.caption(
        "Organiza missão, bloqueios e próxima ação usando somente evidência disponível. "
        "Não executa reparo, deploy, publicação nem trading."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Postura", str(snapshot.get("posture") or "UNKNOWN"))
    c2.metric("Missões ativas", int(snapshot.get("active_missions") or 0))
    c3.metric("Gate", str(snapshot.get("release_gate_state") or "UNKNOWN"))
    c4.metric(
        "Confiança da evidência",
        f"{int(confidence.get('score') or 0)}/100",
        delta=str(confidence.get("label") or "SEM_EVIDENCIA"),
    )
    st.info(
        f"**Objetivo atual:** {snapshot.get('objective') or 'não confirmado'}\n\n"
        f"**Próxima ação:** {snapshot.get('next_action') or 'não confirmada'}"
    )
    blockers = list(snapshot.get("blockers") or [])
    if blockers:
        st.warning("Bloqueios confirmados: " + " · ".join(str(x) for x in blockers[:4]))

    with st.expander("🔎 AION Auditor · Evidências", expanded=False):
        counts = audit.get("counts") if isinstance(audit.get("counts"), Mapping) else {}
        a1,a2,a3,a4 = st.columns(4)
        a1.metric("Confirmadas", int(counts.get("CONFIRMED") or 0))
        a2.metric("Inferências", int(counts.get("INFERENCE") or 0))
        a3.metric("Hipóteses", int(counts.get("HYPOTHESIS") or 0))
        a4.metric("Desconhecidas", int(counts.get("UNKNOWN") or 0))
        st.caption(
            f"Fontes independentes: {int(audit.get('independent_sources') or 0)} · "
            f"conflitos: {int(audit.get('conflict_count') or 0)} · "
            "o score acima mede qualidade da evidência, não probabilidade de lucro."
        )
        rows = []
        for row in list(audit.get("rows", []) or []):
            if not isinstance(row, Mapping):
                continue
            rows.append({
                "Afirmação": str(row.get("claim") or ""),
                "Estado": str(row.get("kind") or "UNKNOWN"),
                "Fonte": str(row.get("source") or "unknown"),
                "Valor": str(row.get("value") or ""),
            })
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        if int(audit.get("conflict_count") or 0):
            st.error(
                "O Auditor encontrou evidências confirmadas conflitantes. "
                "A confiança é automaticamente limitada e o AION não escolhe um lado escondido."
            )


def _render_reliability_governance(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    reliability = (
        system.get("reliability")
        if isinstance(system.get("reliability"), Mapping)
        else {}
    )
    st.markdown("#### 🛡️ Reliability & Governance")
    st.caption(
        "Data Guardian + Source Mesh + reconciliação de fontes + Cost Guardian + proteção da memória + "
        "modo degradado + rollback consultivo. Nenhuma correção, compra, deploy ou rollback é automático."
    )
    source_mesh = (
        system.get("source_mesh")
        if isinstance(system.get("source_mesh"), Mapping)
        else {}
    )
    if source_mesh:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Source Mesh", str(source_mesh.get("market_state") or "UNKNOWN"))
        m2.metric("Observações", int(source_mesh.get("observation_count") or 0))
        m3.metric("Confirmadas", int(source_mesh.get("confirmed_observations") or 0))
        m4.metric("Fallback/indisp.", int(source_mesh.get("fallback_or_unavailable") or 0))
        families = (
            source_mesh.get("families")
            if isinstance(source_mesh.get("families"), Mapping)
            else {}
        )
        if families:
            st.caption(
                "Famílias observadas: "
                + " · ".join(f"{name}: {count}" for name,count in sorted(families.items()))
            )
        if bool(source_mesh.get("market_live_confirmed", False)):
            st.success(
                "Mercado ao vivo confirmado pelo Source Mesh: Matriz ao vivo + Autopilot + "
                "scanner/mapa + Twelve Data passaram juntos."
            )
        else:
            st.info(
                "Mercado ao vivo NÃO foi confirmado pelo Source Mesh nesta execução. "
                "Snapshot/fallback pode manter contexto, mas não vira evidência ao vivo."
            )
    if not reliability:
        st.warning("Camada de confiabilidade não confirmada nesta execução.")
        return

    data = (
        reliability.get("data_guardian")
        if isinstance(reliability.get("data_guardian"), Mapping)
        else {}
    )
    cost = (
        reliability.get("cost_guardian")
        if isinstance(reliability.get("cost_guardian"), Mapping)
        else {}
    )
    memory = (
        reliability.get("memory_protection")
        if isinstance(reliability.get("memory_protection"), Mapping)
        else {}
    )
    degraded = (
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"), Mapping)
        else {}
    )
    rollback = (
        reliability.get("rollback_governance")
        if isinstance(reliability.get("rollback_governance"), Mapping)
        else {}
    )
    reconciliation = (
        data.get("reconciliation")
        if isinstance(data.get("reconciliation"), Mapping)
        else {}
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Postura", str(reliability.get("posture") or "UNKNOWN"))
    c2.metric("Modo", str(degraded.get("state") or "UNKNOWN"))
    c3.metric("Memória", str(memory.get("state") or "UNKNOWN"))
    c4.metric("Custo", str(cost.get("state") or "UNKNOWN"))

    conflicts = int(reconciliation.get("conflict_count") or 0)
    critical_conflicts = int(reconciliation.get("critical_conflict_count") or 0)
    advisory_bad = int(data.get("advisory_bad_sources") or 0)
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("Conflitos de fonte", conflicts)
    r2.metric("Conflitos críticos", critical_conflicts)
    r3.metric("Rollback", str(rollback.get("state") or "STANDBY"))
    r4.metric("Ordens reais", "BLOQUEADAS")
    if advisory_bad:
        st.caption(
            f"{advisory_bad} fonte(s) LOW/MEDIUM estão em aviso. "
            "Elas continuam visíveis, mas não derrubam sozinhas a postura crítica do sistema."
        )

    if str(degraded.get("state") or "").upper()=="FAIL_CLOSED":
        st.error(
            "Reliability Guardian em FAIL-CLOSED: capacidades sensíveis permanecem bloqueadas "
            "até que a evidência crítica seja reconciliada."
        )
    elif str(degraded.get("state") or "").upper()=="DEGRADED_SAFE":
        st.warning(
            "Modo degradado seguro ativo. O AION pode explicar e organizar evidências, "
            "mas não deve promover estados não confirmados."
        )
    else:
        st.success(
            "Nenhum bloqueio crítico foi consolidado por esta camada. "
            "Isso não substitui validação externa nem autorização operacional."
        )

    if conflicts:
        st.warning(
            "Há fontes confirmadas divergentes. O AION não escolhe uma delas silenciosamente; "
            "a afirmação permanece em CONFLICT até reconciliação verificável."
        )

    observations = [
        row for row in list(reconciliation.get("observations") or [])
        if isinstance(row, Mapping)
    ]
    if observations:
        with st.expander("Fontes e evidências observadas", expanded=False):
            st.dataframe([
                {
                    "Família":row.get("family"),
                    "Fonte":row.get("source"),
                    "Afirmação":row.get("claim"),
                    "Estado":row.get("state"),
                    "Verdade":row.get("truth_state"),
                    "Criticidade":row.get("criticality"),
                    "Idade min":row.get("age_minutes"),
                    "Máx. min":row.get("max_age_minutes"),
                    "Quota %":row.get("quota_remaining_pct"),
                }
                for row in observations
            ], width="stretch", hide_index=True)

    actions = [str(x) for x in list(reliability.get("next_actions") or []) if str(x).strip()]
    if actions:
        st.markdown("**Próximas ações seguras:**")
        for action in actions[:8]:
            st.markdown(f"- {action}")

    st.caption(
        "Failover automático: NÃO · reparo automático: NÃO · rollback automático: NÃO · "
        "fallback pago automático: NÃO."
    )


def _render_live_event_intelligence(
    checkpoint: Mapping[str, Any],
    system_context: Mapping[str, Any] | None,
    *,
    allow_memory_sync: bool = True,
) -> None:
    system = dict(system_context or {})
    live = (
        system.get("live_event_intelligence")
        if isinstance(system.get("live_event_intelligence"), Mapping)
        else {}
    )
    st.markdown("#### 🌐 AION Live Event Intelligence")
    st.caption(
        "Radar de eventos macro/notícias/geopolítica a partir das fontes já disponíveis no AtlasQuant. "
        "Manchete observada não vira fato confirmado automaticamente; impacto de mercado é sempre hipótese."
    )
    if not live:
        st.warning("Live Event Intelligence não foi confirmado nesta execução.")
        return

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estado", str(live.get("state") or "UNKNOWN"))
    c2.metric("Eventos", int(live.get("event_count") or 0))
    c3.metric("Alertas", int(live.get("alert_count") or 0))
    c4.metric("Urgentes p/ revisão", int(live.get("urgent_review_count") or 0))

    background_state = str(live.get("background_watch_state") or "NOT_STARTED")
    heartbeat_count = int(live.get("background_heartbeat_count") or 0)
    coverage = live.get("background_coverage_minutes")
    max_gap = live.get("background_max_gap_minutes")
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("Watch background", background_state)
    b2.metric("Heartbeats", heartbeat_count)
    b3.metric(
        "Cobertura",
        "—" if coverage is None else f"{float(coverage)/60.0:.1f} h",
    )
    b4.metric(
        "Maior lacuna",
        "—" if max_gap is None else f"{float(max_gap):.0f} min",
    )
    source_state = str(live.get("news_source_state") or "UNKNOWN")
    age = live.get("news_payload_age_minutes")
    age_text = "—" if age is None else f"{float(age):.0f} min"
    st.caption(
        f"Fonte de notícias: {source_state} · idade do snapshot: {age_text} · "
        f"notícias frescas classificadas: {int(live.get('fresh_news_events') or 0)}."
    )

    if bool(live.get("continuous_runtime_confirmed", False)):
        st.success(
            "Continuidade de background por ~24h confirmada pelos heartbeats persistidos do runtime. "
            "Isso confirma o ciclo observado, não garante disponibilidade futura."
        )
    else:
        st.info(
            "Motor de alerta preparado, mas monitoramento 24/7 contínuo ainda NÃO está confirmado. "
            "A prova exige aproximadamente 24h de heartbeats persistidos, densidade mínima e sem lacunas excessivas."
        )

    top = [
        item for item in list(live.get("top_alerts", []) or [])
        if isinstance(item, Mapping)
    ]
    if not top:
        st.caption(
            "Nenhum evento fresco atingiu o limiar de alerta nesta leitura. "
            "Fonte stale ou indisponível não gera breaking alert."
        )

    for idx,item in enumerate(top[:5]):
        level = str(item.get("alert_level") or "WATCH")
        headline = str(item.get("headline") or "Evento sem título")
        truth = str(item.get("truth_state") or "UNKNOWN")
        urgency = int(item.get("urgency_score") or 0)
        category = str(item.get("category") or "OTHER")
        if level == "URGENT_REVIEW":
            st.warning(f"**{level} · {urgency}/100 · {category}** — {headline}")
        else:
            st.info(f"**{level} · {urgency}/100 · {category}** — {headline}")
        st.caption(
            f"Verdade do evento: {truth} · fontes: {int(item.get('source_count') or 0)} · "
            f"moedas relacionadas: {', '.join(item.get('currencies') or []) or 'não mapeadas'}."
        )
        with st.expander(f"Impacto hipotético · evento {idx+1}", expanded=False):
            channels = [
                row for row in list(item.get("impact_channels", []) or [])
                if isinstance(row, Mapping)
            ]
            if channels:
                st.dataframe([
                    {
                        "Ativo/canal":row.get("asset"),
                        "Possível reação":row.get("direction"),
                        "Mecanismo":row.get("mechanism"),
                        "Estado":row.get("truth_state"),
                    }
                    for row in channels
                ], width="stretch", hide_index=True)
            st.caption(
                "Isto é hipótese de transmissão de mercado, não previsão garantida nem sinal de trade. "
                "Preço, contexto e fontes adicionais precisam confirmar a leitura."
            )

    journal_count = int(live.get("journal_event_count") or 0)
    delivery_count = int(live.get("delivery_candidate_count") or 0)
    st.caption(
        f"Histórico runtime deduplicado: {journal_count} evento(s) · "
        f"fila interna de entrega futura: {delivery_count} candidato(s). "
        "Canal externo conectado: NÃO."
    )

    memory = (
        checkpoint.get("live_event_journal")
        if isinstance(checkpoint.get("live_event_journal"), Mapping)
        else {}
    )
    memory_events = list(memory.get("events", []) or [])
    memory_heartbeats = list(memory.get("heartbeats", []) or [])
    memory_watch = live_event_continuity_summary(memory_heartbeats)
    st.caption(
        f"Checkpoint Mestre: {len(memory_events)} evento(s) · "
        f"{len(memory_heartbeats)} heartbeat(s) · estado {memory_watch.get('state','NOT_STARTED')}."
    )

    if allow_memory_sync and st.button(
        "Sincronizar histórico de eventos com o Checkpoint Mestre",
        key="aion_live_event_journal_sync",
        width="stretch",
    ):
        runtime_events = [
            dict(x) for x in list(live.get("journal_events", []) or [])
            if isinstance(x, Mapping)
        ]
        runtime_heartbeats = [
            dict(x) for x in list(live.get("journal_heartbeats", []) or [])
            if isinstance(x, Mapping)
        ]
        merged_events = merge_live_event_journal_events(
            memory_events,
            runtime_events,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        heartbeat_rows = normalize_live_event_heartbeats(
            memory_heartbeats + runtime_heartbeats
        )
        updated = update_live_event_journal_checkpoint(
            checkpoint,
            events=merged_events,
            heartbeats=heartbeat_rows,
            dirty=True,
        )
        updated = _record_working_event(
            updated,
            "live_event_journal_synced",
            "Histórico Live Event sincronizado com o Checkpoint Mestre.",
            evidence={
                "events":len(merged_events),
                "heartbeats":len(heartbeat_rows),
                "external_delivery_allowed":False,
                "real_orders_enabled":False,
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success(
            "Histórico sincronizado na memória de trabalho. "
            "Salve o Checkpoint Mestre para persistir."
        )
        st.rerun()

    st.caption(
        "Fila externa: DESLIGADA · notificação automática: NÃO · "
        "autorização de trade: NÃO · ordens reais: BLOQUEADAS."
    )


def _aion_memory_hits(
    question: Any,
    checkpoint: Mapping[str, Any] | None,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Combine canonical project memory with reviewed Wisdom Journal evidence."""
    q = str(question or "").strip()
    if not q:
        return []
    canonical = [
        dict(x) for x in search_canonical_memory(q, limit=max(1, min(limit, 5)))
        if isinstance(x, Mapping)
    ]
    cp = dict(checkpoint or {})
    wisdom = cp.get("wisdom") if isinstance(cp.get("wisdom"), Mapping) else {}
    knowledge = wisdom_evidence_hits(
        q,
        list(wisdom.get("entries", []) or []),
        limit=max(1, min(limit, 4)),
    )
    combined = canonical + knowledge
    return combined[: max(1, min(int(limit or 8), 12))]


def _render_learning_pulse(checkpoint: Mapping[str, Any]) -> None:
    learning = checkpoint.get("learning") if isinstance(checkpoint.get("learning"), Mapping) else {}
    episodes = list(learning.get("episodes", []) or [])
    experiments = list(learning.get("experiments", []) or [])
    research_refs = list(learning.get("research_refs", []) or [])
    summary = learning_summary(episodes, experiments, research_refs)
    wisdom = checkpoint.get("wisdom") if isinstance(checkpoint.get("wisdom"), Mapping) else {}
    wisdom_state = wisdom_summary(list(wisdom.get("entries", []) or []))
    st.markdown("#### 🧠 Evolução Controlada")
    st.caption(
        "O AION melhora medindo previsões e resultados, não mudando regras sozinho. "
        "Toda promoção continua dependente de evidência e revisão humana."
    )
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Aprendizados", int(summary.get("episodes") or 0))
    c2.metric("Resultados fechados", int(summary.get("settled_episodes") or 0))
    c3.metric("Pesquisa vinculada", int(summary.get("research_references") or 0))
    c4.metric("Sabedoria ativa", int(wisdom_state.get("active") or 0))
    c5.metric("Challengers p/ revisão", int(summary.get("human_review_candidates") or 0))
    match_rate = summary.get("observed_match_rate_pct")
    gap = summary.get("calibration_gap_pct")
    st.caption(
        "Acerto observado: "
        + ("—" if match_rate is None else f"{float(match_rate):.1f}%")
        + " · gap de calibração: "
        + ("—" if gap is None else f"{float(gap):.1f}%")
        + f" · estado: {summary.get('calibration_state','INSUFFICIENT')}."
    )
    if int(summary.get("errors_without_confirmed_cause") or 0):
        st.info(
            f"{int(summary.get('errors_without_confirmed_cause') or 0)} erro(s) ainda sem causa confirmada. "
            "Eles permanecem como lacuna de conhecimento, não como explicação inventada."
        )
    st.caption(
        "Autoajuste de pesos: DESATIVADO · promoção automática: DESATIVADA · trading real: BLOQUEADO."
    )


def _render_master_status_summary(board: Mapping[str, Any]) -> None:
    """Compact Master Panel that remains visible in Essential mode."""
    counts = board.get("counts") if isinstance(board.get("counts"), Mapping) else {}
    attention = (
        list(board.get("attention") or [])
        if isinstance(board.get("attention"), list)
        else []
    )
    st.markdown("#### Painel Mestre · resumo essencial")
    st.caption(
        "Estado mestre sempre visível. O modo Completo acrescenta a tabela técnica "
        "sem esconder este resumo."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Confirmados", int(counts.get("CONFIRMED") or 0))
    c2.metric("Bloqueados", int(counts.get("BLOCKED") or 0))
    c3.metric(
        "Dependência externa",
        int(counts.get("EXTERNAL_DEPENDENCY") or 0),
    )
    c4.metric("Desconhecidos", int(counts.get("UNKNOWN") or 0))
    if attention:
        st.warning(
            f"{len(attention)} item(ns) do Painel Mestre exigem atenção. "
            "Os primeiros itens aparecem abaixo."
        )
        for item in attention[:3]:
            if not isinstance(item, Mapping):
                continue
            st.markdown(
                "- **"
                + str(item.get("state") or "UNKNOWN")
                + " · "
                + str(item.get("label") or item.get("id") or "Item")
                + "** — "
                + str(item.get("detail") or "")
            )
    else:
        st.success(
            "Nenhuma pendência do Painel Mestre foi registrada nesta execução."
        )


def _render_master_status(board: Mapping[str, Any]) -> None:
    counts = board.get("counts") if isinstance(board.get("counts"), Mapping) else {}
    st.markdown("#### Painel Mestre de Estado")
    st.caption(
        "CONFIRMADO exige evidência desta execução. BLOQUEADO é uma proteção/flag. "
        "DEPENDÊNCIA EXTERNA exige conector/prova. DESCONHECIDO não é tratado como pronto."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Confirmados", int(counts.get("CONFIRMED") or 0))
    c2.metric("Bloqueados", int(counts.get("BLOCKED") or 0))
    c3.metric("Dependência externa", int(counts.get("EXTERNAL_DEPENDENCY") or 0))
    c4.metric("Desconhecidos", int(counts.get("UNKNOWN") or 0))
    rows = status_rows(board)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_approval_inbox(inbox: Mapping[str, Any]) -> None:
    st.markdown("#### Central de Aprovações")
    st.caption(
        "Somente itens que realmente chegaram a um estágio de decisão aparecem aqui. "
        "Esta visão não aprova nem executa ações; a decisão continua explícita na área de origem."
    )
    if str(inbox.get("status") or "CONFIRMED").upper() == "UNKNOWN":
        st.warning(
            "A Central de Aprovações não pôde ser confirmada nesta execução. "
            "Nenhuma ausência de item será tratada como prova de que não há aprovações pendentes."
        )
        return
    by_kind = inbox.get("by_kind") if isinstance(inbox.get("by_kind"), Mapping) else {}
    by_priority = inbox.get("by_priority") if isinstance(inbox.get("by_priority"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Pendentes", int(inbox.get("total") or 0))
    c2.metric("P0", int(by_priority.get("P0") or 0))
    c3.metric("P1", int(by_priority.get("P1") or 0))
    c4.metric("Tarefas", int(by_kind.get("TASK") or 0))
    rows = approval_rows(inbox)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
        st.info(
            "Para aprovar, abra a área indicada no item. "
            "A Central não transforma visibilidade em autorização automática."
        )
    else:
        st.success("Nenhum item chegou a um estágio que exija aprovação administrativa nesta memória.")



def _critical_surface_rows(system_context: Mapping[str, Any] | None) -> list[dict[str, str]]:
    system = dict(system_context or {})
    snapshot = (
        system.get("critical_surfaces")
        if isinstance(system.get("critical_surfaces"), Mapping)
        else {}
    )
    rows: list[dict[str, str]] = []
    for item in list(snapshot.get("items", []) or []):
        if not isinstance(item, Mapping):
            continue
        state = str(item.get("state") or "UNKNOWN").upper()
        if state not in {"OK", "DEGRADED", "UNAVAILABLE", "STALE_BUILD", "UNKNOWN"}:
            state = "UNKNOWN"
        rows.append({
            "Tela": str(item.get("label") or item.get("id") or "Tela não identificada"),
            "Estado": state,
            "Build observado": str(item.get("build_id") or "—"),
            "Build atual": str(item.get("current_build") or "—"),
            "Diagnóstico": str(item.get("error_type") or "—"),
            "Próxima ação": str(item.get("next_action") or "Revalidar a tela."),
        })
    return rows


def _short_commit(value: Any) -> str:
    raw = str(value or "").strip()
    return raw[:8] if raw else "—"


def _render_release_gate(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    gate = (
        system.get("release_gate")
        if isinstance(system.get("release_gate"), Mapping)
        else release_gate(
            publication_truth=(
                system.get("publication_truth")
                if isinstance(system.get("publication_truth"), Mapping)
                else {}
            ),
            interface_validation=(
                system.get("interface_validation")
                if isinstance(system.get("interface_validation"), Mapping)
                else {}
            ),
        )
    )

    st.markdown("#### Gate de liberação AION")
    st.caption(
        "Quatro provas independentes: código/bundle, telas críticas, runtime × main e produção. "
        "Uma etapa não confirma a seguinte e este painel não executa deploy."
    )
    c1,c2,c3 = st.columns(3)
    c1.metric("Gate", str(gate.get("state") or "UNKNOWN"))
    c2.metric(
        "Etapas confirmadas",
        f"{int(gate.get('confirmed_stages') or 0)}/{int(gate.get('total_stages') or 4)}",
    )
    c3.metric("Liberação", "CONFIRMADA" if gate.get("release_claim_allowed") else "PENDENTE")

    st.progress(
        min(1.0, max(0.0, float(gate.get("progress_pct") or 0.0) / 100.0)),
        text=f"Progresso do gate · {float(gate.get('progress_pct') or 0.0):.1f}%",
    )

    rows = release_gate_rows(gate)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)

    gate_state = str(gate.get("state") or "UNKNOWN").upper()
    if gate_state == "COMPLETE" and gate.get("release_claim_allowed"):
        st.success(
            "As quatro etapas possuem evidência suficiente para a afirmação de liberação. "
            "Isso não dispara nenhuma ação externa."
        )
    elif gate_state == "BLOCKED":
        st.error(
            f"Gate bloqueado em **{gate.get('next_label') or 'etapa não identificada'}**. "
            f"{gate.get('next_action') or ''}"
        )
    else:
        st.warning(
            f"Gate ainda não concluído. Próxima etapa: **{gate.get('next_label') or 'não confirmada'}**. "
            f"{gate.get('next_action') or ''}"
        )
    st.caption(
        "Deploy automático: BLOQUEADO · ordens reais: BLOQUEADAS · "
        "qualquer ação no Render continua exigindo fluxo separado."
    )


def _render_publication_truth(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    publication = (
        system.get("publication_truth")
        if isinstance(system.get("publication_truth"), Mapping)
        else {}
    )
    st.markdown("#### Estado de publicação")
    st.caption(
        "Separa código em execução, identidade da main e validação de produção. "
        "Merge no GitHub não é tratado como prova de que o Render já está atualizado."
    )
    if not publication:
        st.warning(
            "Não há evidência de publicação disponível nesta execução. "
            "O AION mantém produção como não confirmada."
        )
        return

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estado", str(publication.get("state") or "UNKNOWN"))
    c2.metric("Runtime", _short_commit(publication.get("runtime_commit")))
    c3.metric("Main esperada", _short_commit(publication.get("expected_main_commit")))
    c4.metric("Produção", str(publication.get("production_verification") or "UNKNOWN"))

    main_match = str(publication.get("main_match") or "UNKNOWN")
    can_claim_live = bool(publication.get("can_claim_latest_main_live", False))
    if can_claim_live:
        st.success(
            "Há identidade suficiente para afirmar que o runtime corresponde à main esperada "
            "e que a produção foi explicitamente validada."
        )
    elif main_match == "MISMATCH":
        st.error(
            "O commit em execução diverge da main esperada. "
            "AION não considera esta versão atualizada."
        )
    else:
        st.warning(
            "A versão em execução ainda não tem prova suficiente para ser chamada de "
            "última main validada em produção."
        )
    st.caption(str(publication.get("next_action") or ""))


def _render_validation_center(
    system_context: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict(runtime_result or {})
    snapshot = validation_center_snapshot(
        system_context,
        runtime_status=runtime.get("status"),
    )
    st.markdown("#### Centro de Validação")
    st.caption(
        "Este quadro separa evidência do build atual, validação local da sessão e produção. "
        "Validação local nunca é tratada como prova de que o deploy publicado está saudável."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Build atual", str(snapshot.get("current_build") or "NÃO CONFIRMADO"))
    c2.metric(
        "Telas críticas",
        f"{int(snapshot.get('critical_confirmed') or 0)}/{int(snapshot.get('critical_total') or 3)}",
    )
    c3.metric(
        "Sessão local",
        "VALIDADA" if snapshot.get("local_session_validated") else "PENDENTE",
    )
    c4.metric(
        "Produção",
        "CONFIRMADA" if snapshot.get("production_confirmed") else "NÃO CONFIRMADA",
    )

    if snapshot.get("local_session_validated"):
        st.success(
            "Build e três telas críticas têm evidência desta sessão no mesmo build. "
            "Isso confirma somente a sessão local observada."
        )
    else:
        st.warning(
            "A sessão local ainda não possui evidência completa no build atual. "
            "O AION mantém a validação pendente."
        )

    if snapshot.get("production_confirmed"):
        st.success("Há evidência explícita de produção para este mesmo build.")
    else:
        st.info(
            "Produção continua NÃO CONFIRMADA. O AION não promove automaticamente "
            "evidência local para estado de produção."
        )

    with st.expander("Ver checklist de evidências", expanded=False):
        rows = validation_center_rows(snapshot)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        if snapshot.get("next_actions"):
            st.markdown("**Próximas validações:**")
            for action in list(snapshot.get("next_actions") or [])[:8]:
                st.markdown(f"- {action}")
        st.caption(
            "Este centro é somente leitura. Deploy, rollback, mudança de permissão e ordens reais "
            "não são executados por este quadro."
        )
    return snapshot


def _render_critical_surface_health(system_context: Mapping[str, Any] | None) -> None:
    st.markdown("#### Saúde das telas críticas")
    st.caption(
        "Estado observado nesta sessão para Radar principal, Radar avançado/Central Institucional "
        "e Painel Mestre. É diagnóstico de interface, não sinal de trade nem autorização operacional."
    )
    system = dict(system_context or {})
    snapshot = (
        system.get("critical_surfaces")
        if isinstance(system.get("critical_surfaces"), Mapping)
        else {}
    )
    mission = interface_validation_mission(snapshot)
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("OK", int(counts.get("OK") or 0))
    c2.metric(
        "Com problema",
        int(counts.get("DEGRADED") or 0) + int(counts.get("UNAVAILABLE") or 0),
    )
    c3.metric("Build antigo", int(counts.get("STALE_BUILD") or 0))
    c4.metric("Não observadas", int(counts.get("UNKNOWN") or 0))

    st.caption(
        f"Missão de validação deste build: {int(mission.get('confirmed') or 0)}/"
        f"{int(mission.get('total') or 3)} telas confirmadas · "
        f"estado {str(mission.get('state') or 'UNKNOWN')}."
    )
    st.progress(
        min(1.0, max(0.0, float(mission.get("progress_pct") or 0.0) / 100.0)),
        text=(
            "Validação da interface no build atual · "
            f"{float(mission.get('progress_pct') or 0.0):.1f}%"
        ),
    )
    if mission.get("next_label") and not mission.get("all_confirmed_current_build"):
        st.info(
            f"Próxima tela da missão: **{mission.get('next_label')}** — "
            f"{mission.get('next_action') or 'revalidar no build atual.'}"
        )

    rows = _critical_surface_rows(system)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.warning(
            "A saúde das telas críticas ainda não foi informada por esta execução. "
            "O AION não assume que as telas estão saudáveis."
        )
        return

    if bool(snapshot.get("all_ok", False)):
        st.success(
            "As três telas críticas foram observadas como OK nesta sessão. "
            "Isso não substitui a validação do deploy de produção."
        )
    else:
        st.warning(
            "Existe tela degradada, indisponível, ligada a build antigo ou ainda não observada. "
            "O AION mantém o estado como pendente até nova evidência no build atual."
        )

    unresolved = [
        item for item in list(snapshot.get("items", []) or [])
        if isinstance(item, Mapping)
        and str(item.get("state") or "UNKNOWN").upper() != "OK"
    ]
    if unresolved:
        st.markdown("**Revalidação guiada**")
        st.caption(
            "Cada botão apenas registra um pedido de navegação. A tela é aberta no próximo ciclo "
            "e precisa renderizar no build atual para virar evidência nova."
        )
        build_id = str(system.get("source_build") or snapshot.get("current_build") or "")
        for item in unresolved:
            surface = str(item.get("id") or "")
            label = str(item.get("label") or surface or "Tela crítica")
            state = str(item.get("state") or "UNKNOWN").upper()
            if st.button(
                f"🧪 Revalidar · {label} · {state}",
                key=f"aion_revalidate_surface_{surface}",
                width="stretch",
            ):
                try:
                    request_surface_revalidation(
                        st.session_state,
                        surface,
                        build_id=build_id,
                    )
                    st.rerun()
                except Exception as exc:
                    st.warning(
                        "Não foi possível registrar a navegação de revalidação. "
                        f"Diagnóstico: {type(exc).__name__}."
                    )

    last_result = (
        system.get("guided_revalidation")
        if isinstance(system.get("guided_revalidation"), Mapping)
        else {}
    )
    if last_result:
        result_state = str(last_result.get("state") or "UNKNOWN")
        label = str(last_result.get("label") or last_result.get("surface") or "tela")
        if result_state == "CONFIRMED_OK":
            st.success(
                f"Última revalidação guiada: {label} confirmado no build atual."
            )
        elif result_state in {"CONFIRMED_ERROR", "BUILD_CHANGED", "NAVIGATION_BLOCKED"}:
            st.warning(
                f"Última revalidação guiada: {label} terminou em {result_state}. "
                "O AION não trata esse resultado como saudável."
            )


def _render_admin_guidance(
    access: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    copilot_snapshot: Mapping[str, Any],
) -> None:
    """Compact progressive-disclosure guidance; onboarding stays session-local."""
    copilot = dict(copilot_snapshot or {})
    primary = (
        copilot.get("primary")
        if isinstance(copilot.get("primary"), Mapping)
        else {}
    )
    st.markdown("#### AION · próximo passo")
    if primary:
        st.info(
            f"{str(primary.get('priority') or 'P3')} · "
            f"{str(primary.get('title') or 'Revisão necessária')} — "
            f"{str(primary.get('next_action') or 'Revisar a evidência disponível.')}"
        )
    else:
        st.caption(
            "Copiloto sem prioridade confirmada nesta execução. "
            "Ausência de item não é tratada como prova de que todo o sistema está pronto."
        )

    if _AION_ADMIN_ONBOARDING_STARTED_KEY not in st.session_state:
        st.session_state[_AION_ADMIN_ONBOARDING_STARTED_KEY] = datetime.now(
            timezone.utc
        ).isoformat()
    if _AION_ADMIN_ONBOARDING_MODE_KEY not in st.session_state:
        st.session_state[_AION_ADMIN_ONBOARDING_MODE_KEY] = "BEGINNER"

    with st.expander("Copiloto + Onboarding Inteligente", expanded=False):
        selected_mode = st.selectbox(
            "Experiência do onboarding",
            ADMIN_ONBOARDING_MODES,
            key=_AION_ADMIN_ONBOARDING_MODE_KEY,
            help=(
                "BEGINNER e ADVANCED alteram a trilha, nunca as permissões. "
                "Trocar o modo invalida progresso incompatível em vez de promovê-lo."
            ),
        )
        started_at = str(
            st.session_state.get(_AION_ADMIN_ONBOARDING_STARTED_KEY) or ""
        )
        progress = st.session_state.get(_AION_ADMIN_ONBOARDING_PROGRESS_KEY)
        progress_map = progress if isinstance(progress, Mapping) else None
        now = datetime.now(timezone.utc)

        try:
            onboarding = build_admin_onboarding_snapshot(
                access,
                experience_mode=selected_mode,
                started_at=started_at,
                feature_flags=flags,
                system_context=system_context,
                progress=progress_map,
                now=now,
            )
        except Exception:
            onboarding = {
                "state": "BLOCKED",
                "rejection": {"code": "ONBOARDING_SAFE_FALLBACK"},
                "completed_step_ids": [],
                "blocked_step_ids": [],
                "stale_step_ids": [],
                "recommendations": [],
                "steps": [],
                "executes_action": False,
                "runtime_written": False,
                "real_trading_enabled": False,
            }

        c1, c2, c3 = st.columns(3)
        c1.metric("Copiloto", str(copilot.get("state") or "UNKNOWN"))
        c2.metric("Onboarding", str(onboarding.get("state") or "UNKNOWN"))
        c3.metric(
            "Prioridades",
            int(copilot.get("attention_count") or 0),
        )

        copilot_items = [
            item for item in list(copilot.get("items") or [])[:3]
            if isinstance(item, Mapping)
        ]
        if copilot_items:
            st.markdown("**Prioridades do Copiloto**")
            for item in copilot_items:
                st.markdown(
                    "- **"
                    + str(item.get("priority") or "P3")
                    + " · "
                    + str(item.get("title") or "Item")
                    + "** — "
                    + str(item.get("next_action") or "Revisar evidência.")
                )

        recommendations = [
            item for item in list(onboarding.get("recommendations") or [])[:3]
            if isinstance(item, Mapping)
        ]
        steps = {
            str(item.get("step_id") or ""): item
            for item in list(onboarding.get("steps") or [])
            if isinstance(item, Mapping)
        }
        if recommendations:
            st.markdown("**Próximas etapas do Onboarding**")
            for item in recommendations:
                step_id = str(item.get("step_id") or "")
                row = steps.get(step_id, {})
                st.markdown(
                    "- **"
                    + step_id
                    + " · "
                    + str(item.get("status") or "UNKNOWN")
                    + "** — "
                    + str(item.get("next_safe_action") or "")
                )
                if row.get("completable") is True:
                    if st.button(
                        "Concluir etapa · " + step_id,
                        key="aion_admin_onboarding_complete_" + step_id,
                        width="stretch",
                    ):
                        try:
                            updated = complete_admin_onboarding_step(
                                access,
                                progress_map,
                                step_id,
                                experience_mode=selected_mode,
                                started_at=started_at,
                                feature_flags=flags,
                                system_context=system_context,
                                now=now,
                            )
                            st.session_state[
                                _AION_ADMIN_ONBOARDING_PROGRESS_KEY
                            ] = updated
                            st.rerun()
                        except Exception:
                            st.warning(
                                "A etapa não pôde ser registrada nesta sessão. "
                                "Nenhuma permissão ou runtime foi alterado."
                            )
        else:
            st.caption(
                "Nenhuma próxima etapa segura foi confirmada nesta execução."
            )

        rejection = (
            onboarding.get("rejection")
            if isinstance(onboarding.get("rejection"), Mapping)
            else {}
        )
        if rejection:
            st.caption(
                "Diagnóstico do onboarding: "
                + str(rejection.get("code") or "UNKNOWN")
                + "."
            )

        if progress_map is not None:
            if st.button(
                "Reiniciar onboarding nesta sessão",
                key="aion_admin_onboarding_reset",
                width="stretch",
            ):
                st.session_state.pop(
                    _AION_ADMIN_ONBOARDING_PROGRESS_KEY,
                    None,
                )
                st.session_state[_AION_ADMIN_ONBOARDING_STARTED_KEY] = datetime.now(
                    timezone.utc
                ).isoformat()
                st.rerun()

        st.caption(
            "Sessão local apenas · Checkpoint não é escrito · feature flags não são alteradas · "
            "promoção automática: NÃO · trading real: BLOQUEADO."
        )


def _render_central(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    memory_summary: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
    incident_snapshot: Mapping[str, Any],
    executive_snapshot: Mapping[str, Any],
    copilot_snapshot: Mapping[str, Any],
    specialist_snapshot: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🧠 Central AION")
    pending = checkpoint.get("pending") if isinstance(checkpoint.get("pending"), list) else []
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = operating.get("tasks", []) if isinstance(operating, Mapping) else []
    summary = queue_summary(tasks)
    cols = st.columns(4)
    cols[0].metric("Versão AION", AION_VERSION)
    cols[1].metric("Tarefas ativas", summary["active"])
    cols[2].metric("Aguardando aprovação", summary["waiting_approval"])
    cols[3].metric("Ordens reais", "BLOQUEADAS")
    layered_memory = memory_layer_summary(
        checkpoint.get("memory_layers")
        if isinstance(checkpoint.get("memory_layers"), Mapping)
        else None
    )
    st.markdown(
        """<div style="padding:12px 14px;border:1px solid rgba(79,163,255,.35);
        border-radius:12px;background:linear-gradient(135deg,rgba(12,31,54,.94),rgba(8,20,36,.96));
        margin:4px 0 14px"><strong style="color:#f8fbff">AION ONLINE · ORQUESTRAÇÃO SEGURA</strong>
        <span style="display:block;color:#d7e6f6;font-size:.8rem;margin-top:4px">
        Capability Registry + Truth Gate + Guardian + Critic ativos · execução externa e ordens reais bloqueadas
        </span></div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Memória em camadas: {layered_memory['active']} entrada(s) ativa(s) · "
        f"digest {layered_memory['digest']} · acesso entre personas automático: NÃO."
    )

    with st.expander("Personas AION e onde cada uma trabalha"):
        for item in AION_PERSONAS:
            st.markdown(f"- **{item['title']}** → área `{item['workspace']}`: {item['purpose']}")
        st.caption(
            "Cada persona tem contexto e escopo próprios. O escopo só restringe o Guardian; "
            "nenhuma persona amplia as próprias permissões."
        )

    view_mode = st.selectbox(
        "Visualização da Central",
        ("Essencial", "Completo"),
        key="aion_central_view_mode",
        help=(
            "Essencial prioriza o que exige atenção para reduzir carga e rolagem no celular. "
            "Completo mostra todos os painéis técnicos."
        ),
    )
    _render_admin_guidance(
        access,
        flags,
        system_context,
        copilot_snapshot,
    )
    _render_master_status_summary(status_board)
    _render_executive_pulse(executive_snapshot)

    if view_mode == "Completo":
        _render_commander_intelligence(checkpoint, system_context, executive_snapshot)
        _render_live_event_intelligence(checkpoint, system_context, allow_memory_sync=True)
        _render_learning_pulse(checkpoint)
        _render_reliability_governance(system_context)
        _render_release_gate(system_context)
        _render_publication_truth(system_context)
        _render_validation_center(system_context, runtime_result)
        _render_critical_surface_health(system_context)
        _render_workspace_overview(checkpoint, runtime_result)
        _render_attention_queue(
            status_board,
            approval_inbox,
            (system_context.get("critical_surfaces") if isinstance(system_context, Mapping) else None),
            (system_context.get("release_gate") if isinstance(system_context, Mapping) else None),
        )
        _render_memory_security_posture(access, checkpoint, runtime_result, flags)
        _render_security_incident_center(incident_snapshot)
        _render_continuity_center(checkpoint)
    else:
        st.caption(
            "Modo Essencial ativo: Copiloto, Onboarding, Painel Mestre e Pulso Executivo ficam em primeiro plano. "
            "Painéis técnicos permanecem disponíveis no modo Completo; nenhuma permissão ou proteção é ampliada."
        )
        _render_attention_queue(
            status_board,
            approval_inbox,
            (system_context.get("critical_surfaces") if isinstance(system_context, Mapping) else None),
            (system_context.get("release_gate") if isinstance(system_context, Mapping) else None),
        )
        _render_continuity_center(checkpoint)
        if (
            int(incident_snapshot.get("total") or 0) > 0
            or int(incident_snapshot.get("closed_total") or 0) > 0
            or bool(incident_snapshot.get("rollback_review_recommended"))
        ):
            _render_security_incident_center(incident_snapshot)

    st.markdown("#### Briefing de entrada")
    st.write(
        f"Prioridade registrada: **{(checkpoint.get('aion') or {}).get('priority','não confirmada')}**. "
        f"Checkpoint: **{checkpoint_digest(checkpoint)}**. "
        f"Runtime: **{runtime_result.get('status','UNKNOWN')}**."
    )
    if pending and view_mode == "Completo":
        st.markdown("**Próximas pendências registradas:**")
        for item in pending[:8]:
            st.markdown(f"- {item}")

    if view_mode == "Completo":
        _render_master_status(status_board)
        _render_approval_inbox(approval_inbox)

    st.markdown("#### Pergunte ao AION")
    question = st.text_input(
        "Pergunta ou missão",
        key="aion_admin_question",
        placeholder="Ex.: AION, onde paramos no sistema? / como está o Studio? / o que falta validar?",
    )

    core_voice_status = {}
    if neural_voice_status is not None:
        try:
            core_voice_status = neural_voice_status()
        except Exception:
            core_voice_status = {
                "configured": False,
                "provider": "UNKNOWN",
                "model": "UNKNOWN",
                "voice": "UNKNOWN",
            }

    core_runtime_result = {}
    if question.strip():
        if handle_runtime_intent is None:
            core_runtime_result = {
                "status": "UNAVAILABLE",
                "reason": "CORE_RUNTIME_BRIDGE_UNAVAILABLE",
                "route": {},
                "payload": None,
                "truth_state": "UNKNOWN",
                "evidence": {"status": "UNKNOWN", "records": []},
                "evidence_ingress": {
                    "input_rows": 0,
                    "accepted_records": 0,
                    "rejected_records": 0,
                },
                "persistence": {
                    "state": "UNAVAILABLE",
                    "reason": "BRIDGE_IMPORT_UNAVAILABLE",
                },
                "execution_authorized": False,
                "external_action_executed": False,
                "real_trading_enabled": False,
                "provider_called": False,
            }
        else:
            try:
                core_runtime_result = handle_runtime_intent(
                    access,
                    question,
                    system_context=system_context,
                    legacy_checkpoint=checkpoint,
                    voice_status=core_voice_status,
                )
            except Exception as exc:
                core_runtime_result = {
                    "status": "UNKNOWN",
                    "reason": type(exc).__name__,
                    "route": {},
                    "payload": None,
                    "truth_state": "UNKNOWN",
                    "evidence": {"status": "UNKNOWN", "records": []},
                    "evidence_ingress": {
                        "input_rows": 0,
                        "accepted_records": 0,
                        "rejected_records": 0,
                    },
                    "persistence": {
                        "state": "UNAVAILABLE",
                        "reason": "CORE_RUNTIME_ERROR",
                    },
                    "execution_authorized": False,
                    "external_action_executed": False,
                    "real_trading_enabled": False,
                    "provider_called": False,
                }

    if core_runtime_result:
        core_route = (
            core_runtime_result.get("route")
            if isinstance(core_runtime_result.get("route"), Mapping)
            else {}
        )
        core_evidence = (
            core_runtime_result.get("evidence")
            if isinstance(core_runtime_result.get("evidence"), Mapping)
            else {}
        )
        core_ingress = (
            core_runtime_result.get("evidence_ingress")
            if isinstance(core_runtime_result.get("evidence_ingress"), Mapping)
            else {}
        )
        core_persistence = (
            core_runtime_result.get("persistence")
            if isinstance(core_runtime_result.get("persistence"), Mapping)
            else {}
        )
        with st.expander("🧠 AION Core Intelligence · leitura local", expanded=False):
            ci1, ci2, ci3, ci4 = st.columns(4)
            ci1.metric("Capability", str(core_route.get("capability") or "UNKNOWN"))
            ci2.metric("Status", str(core_runtime_result.get("status") or "UNKNOWN"))
            ci3.metric("Verdade", str(core_runtime_result.get("truth_state") or "UNKNOWN"))
            ci4.metric("Persistência", str(core_persistence.get("state") or "UNAVAILABLE"))
            st.caption(
                "Contexto autenticado e evidência da mesma execução. "
                "Sem provider, rede, subprocess, deploy, publicação, pagamento ou trading."
            )
            st.caption(
                "Evidências do runtime: "
                + str(int(core_ingress.get("accepted_records") or 0))
                + " aceita(s) de "
                + str(int(core_ingress.get("input_rows") or 0))
                + " · freshness "
                + str(core_evidence.get("freshness") or "UNVERIFIED")
                + " · conflitos "
                + str(len(list(core_evidence.get("conflict_claims") or [])))
                + "."
            )
            if str(core_evidence.get("conflict_state") or "") == "CONFLICT":
                st.warning(
                    "Há fontes confirmadas em conflito. O Core não escolheu uma versão arbitrariamente."
                )
            core_payload = core_runtime_result.get("payload")
            core_system = (
                core_payload.get("system")
                if isinstance(core_payload, Mapping)
                and isinstance(core_payload.get("system"), Mapping)
                else None
            )
            if isinstance(core_system, Mapping):
                st.dataframe(
                    [
                        {
                            "Item": name,
                            "Estado": str(
                                (row if isinstance(row, Mapping) else {}).get("state")
                                or "UNKNOWN"
                            ),
                            "Valor": str(
                                (row if isinstance(row, Mapping) else {}).get("value")
                                or ""
                            ),
                            "Motivo": str(
                                (row if isinstance(row, Mapping) else {}).get("reason")
                                or ""
                            ),
                        }
                        for name, row in core_system.items()
                    ],
                    hide_index=True,
                    width="stretch",
                )
            elif isinstance(core_payload, Mapping):
                st.json(dict(core_payload))
            if core_runtime_result.get("execution_authorized") is not False:
                st.error("Gate inconsistente: execução não pode ser autorizada neste bridge.")
            else:
                st.caption(
                    "Gate físico: BLOQUEADO · execução autorizada NÃO · ações externas NÃO."
                )

    st.markdown("#### 🧠 Memória persistente do AION Core")
    if checkpoint_memory_snapshot is None or stage_user_approved_memory is None:
        st.caption(
            "Bridge de memória do Core indisponível nesta execução. "
            "Nenhum registro será criado por fallback."
        )
    else:
        try:
            core_memory = checkpoint_memory_snapshot(access, checkpoint)
        except Exception as exc:
            core_memory = {
                "state": "UNKNOWN",
                "records": [],
                "approved_decisions": [],
                "version": 0,
                "error_type": type(exc).__name__,
            }
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Estado", str(core_memory.get("state") or "UNKNOWN"))
        cm2.metric("Registros", len(list(core_memory.get("records") or [])))
        cm3.metric("Versão", int(core_memory.get("version") or 0))
        st.caption(
            "A memória do Core fica dentro do Checkpoint Mestre. Registrar aqui altera somente "
            "a cópia de trabalho; persistência externa continua dependendo de "
            "“Salvar Checkpoint Mestre no runtime” e do Guardian."
        )
        approved_rows = [
            row for row in list(core_memory.get("approved_decisions") or [])
            if isinstance(row, Mapping)
        ]
        if approved_rows:
            with st.expander("Decisões humanas aprovadas no Core", expanded=False):
                st.dataframe(
                    [
                        {
                            "Decisão": str(row.get("text") or ""),
                            "Versão": int(row.get("version") or 0),
                            "Origem": str(row.get("origin") or ""),
                            "Registrada em": str(row.get("created_at") or ""),
                        }
                        for row in approved_rows[-20:]
                    ],
                    hide_index=True,
                    width="stretch",
                )

        with st.expander("Registrar memória com aprovação humana", expanded=False):
            memory_kind = st.selectbox(
                "Tipo de memória",
                ("DECISION", "REQUIREMENT", "PRIORITY", "PENDING_TASK"),
                key="aion_core_memory_kind",
                format_func=lambda value: {
                    "DECISION": "Decisão",
                    "REQUIREMENT": "Requisito",
                    "PRIORITY": "Prioridade",
                    "PENDING_TASK": "Pendência",
                }.get(value, value),
            )
            memory_text = st.text_area(
                "Conteúdo",
                key="aion_core_memory_text",
                max_chars=2400,
                placeholder="Ex.: Manter a Central AION como porta administrativa principal.",
            )
            memory_confirm = st.checkbox(
                "Confirmo que revisei este texto e quero registrá-lo como memória aprovada por mim.",
                value=False,
                key="aion_core_memory_confirm",
            )
            if st.button(
                "✅ Aprovar e registrar no Checkpoint de trabalho",
                key="aion_core_memory_stage",
                disabled=not bool(memory_confirm and memory_text.strip()),
                width="stretch",
            ):
                try:
                    staged_memory = stage_user_approved_memory(
                        access,
                        checkpoint,
                        kind=memory_kind,
                        text=memory_text,
                        confirmation=True,
                    )
                    if staged_memory.get("status") == "STAGED":
                        _set_working_checkpoint(
                            staged_memory.get("checkpoint") or checkpoint,
                            dirty=True,
                        )
                        st.session_state["aion_core_memory_last_stage"] = {
                            "status": "STAGED",
                            "record_id": (
                                (staged_memory.get("record") or {}).get("record_id")
                                if isinstance(staged_memory.get("record"), Mapping)
                                else ""
                            ),
                            "external_persisted": False,
                        }
                        st.success(
                            "Memória aprovada e colocada no Checkpoint de trabalho. "
                            "Ela ainda NÃO foi gravada externamente."
                        )
                        st.rerun()
                    else:
                        st.warning(
                            "Memória não foi registrada: "
                            + str(staged_memory.get("reason") or staged_memory.get("status") or "UNKNOWN")
                        )
                except Exception as exc:
                    st.error(
                        "Registro bloqueado em modo seguro: "
                        + type(exc).__name__
                        + ". Nenhuma memória foi gravada por fallback."
                    )

    st.markdown("#### 🔊 Voz & ⏱️ Automação do AION Core")
    voice_ready = bool(core_voice_status.get("configured"))
    va1, va2, va3 = st.columns(3)
    va1.metric("Voz neural", "PRONTA" if voice_ready else "NÃO CONFIGURADA")
    va2.metric(
        "Agenda",
        "CONECTADA"
        if CheckpointAutomationAdapter is not None and authenticated_context is not None
        else "UNAVAILABLE",
    )
    va3.metric("Executor background", "BLOQUEADO")
    st.caption(
        "Voz: o Core prepara e valida o texto sem chamar o provedor; áudio só é gerado "
        "no botão explícito da voz AtlasQuant. Automação: a agenda é persistida no "
        "Checkpoint, mas nenhum job é executado em background neste bloco."
    )

    scheduler_context = None
    scheduler_snapshot = {
        "status": "UNAVAILABLE",
        "schedules": [],
        "count": 0,
        "due_count": 0,
        "execution_adapter": "UNAVAILABLE",
    }
    if authenticated_context is not None and CheckpointAutomationAdapter is not None:
        try:
            scheduler_context = authenticated_context(access, Domain.ADMIN)
            scheduler_snapshot = CheckpointAutomationAdapter(
                scheduler_context,
                checkpoint,
            ).snapshot(datetime.now(timezone.utc))
        except Exception as exc:
            scheduler_snapshot = {
                "status": "UNKNOWN",
                "schedules": [],
                "count": 0,
                "due_count": 0,
                "execution_adapter": "UNAVAILABLE",
                "error_type": type(exc).__name__,
            }

    sa1, sa2, sa3 = st.columns(3)
    sa1.metric("Agendas", int(scheduler_snapshot.get("count") or 0))
    sa2.metric("Devidas", int(scheduler_snapshot.get("due_count") or 0))
    sa3.metric(
        "Execução",
        str(scheduler_snapshot.get("execution_adapter") or "UNAVAILABLE"),
    )
    schedule_rows = [
        row for row in list(scheduler_snapshot.get("schedules") or [])
        if isinstance(row, Mapping)
    ]
    if schedule_rows:
        with st.expander("Agendas registradas", expanded=False):
            st.dataframe(
                [
                    {
                        "Nome": str(row.get("title") or ""),
                        "Capability": str(row.get("capability") or "NÃO VINCULADA"),
                        "Cadência": str(row.get("cadence") or ""),
                        "Estado": str(row.get("state") or ""),
                        "Próxima": str(row.get("next_run_at") or ""),
                        "Devida": "SIM" if row.get("due") else "NÃO",
                        "Executor": (
                            "LOCAL MANUAL"
                            if str(row.get("capability") or "").strip()
                            else "BLOQUEADO"
                        ),
                    }
                    for row in schedule_rows[-50:]
                ],
                hide_index=True,
                width="stretch",
            )

    with st.expander("Criar agenda persistida", expanded=False):
        schedule_title = st.text_input(
            "Nome da agenda",
            key="aion_core_schedule_title",
            max_chars=240,
            placeholder="Ex.: Briefing macro da manhã",
        )
        schedule_prompt = st.text_area(
            "O que o AION deverá fazer quando houver executor aprovado",
            key="aion_core_schedule_prompt",
            max_chars=2400,
            placeholder="Ex.: Preparar um briefing macro com fatos confirmados e pendências.",
        )
        schedule_capability = st.selectbox(
            "Capability local autorizada para esta agenda",
            tuple(CORE_AUTOMATION_CAPABILITIES),
            key="aion_core_schedule_capability",
            format_func=lambda value: {
                "ADMINISTRATION": "Administração · leitura",
                "MEMORY": "Memória · leitura",
                "RESEARCH": "Pesquisa · síntese local",
                "VOICE": "Voz · preparação sem gerar áudio",
                "CONTENT": "Conteúdo · rascunho",
                "OBSERVABILITY": "Observabilidade · leitura",
            }.get(value, value),
        )
        cadence = st.selectbox(
            "Cadência",
            tuple(CORE_AUTOMATION_CADENCES),
            key="aion_core_schedule_cadence",
            format_func=lambda value: {
                "ONCE": "Uma vez",
                "HOURLY": "A cada hora",
                "DAILY": "Diariamente",
                "WEEKLY": "Semanalmente",
            }.get(value, value),
        )
        zone = application_timezone()
        timezone_name = st.text_input(
            "Timezone",
            value=str(getattr(zone, "key", "America/Cuiaba")),
            key="aion_core_schedule_timezone",
        )
        sc1, sc2 = st.columns(2)
        schedule_hour = int(sc1.number_input(
            "Hora",
            min_value=0,
            max_value=23,
            value=8,
            step=1,
            key="aion_core_schedule_hour",
        ))
        schedule_minute = int(sc2.number_input(
            "Minuto",
            min_value=0,
            max_value=59,
            value=0,
            step=1,
            key="aion_core_schedule_minute",
        ))
        schedule_weekday = None
        if cadence == "WEEKLY":
            weekday_labels = (
                "Segunda",
                "Terça",
                "Quarta",
                "Quinta",
                "Sexta",
                "Sábado",
                "Domingo",
            )
            schedule_weekday = weekday_labels.index(
                st.selectbox(
                    "Dia da semana",
                    weekday_labels,
                    key="aion_core_schedule_weekday",
                )
            )
        schedule_date = None
        if cadence == "ONCE":
            local_now = datetime.now(timezone.utc).astimezone(zone)
            schedule_date = st.date_input(
                "Data",
                value=local_now.date(),
                key="aion_core_schedule_date",
            )
        schedule_confirm = st.checkbox(
            "Confirmo que quero registrar esta agenda. Isto NÃO autoriza execução automática.",
            value=False,
            key="aion_core_schedule_confirm",
        )
        if st.button(
            "⏱️ Registrar agenda no Checkpoint de trabalho",
            key="aion_core_schedule_stage",
            disabled=not bool(
                schedule_confirm
                and schedule_title.strip()
                and schedule_prompt.strip()
                and scheduler_context is not None
                and stage_schedule is not None
            ),
            width="stretch",
        ):
            try:
                schedule_run_at = None
                if cadence == "ONCE":
                    selected_zone = application_timezone(timezone_name)
                    schedule_run_at = datetime(
                        schedule_date.year,
                        schedule_date.month,
                        schedule_date.day,
                        schedule_hour,
                        schedule_minute,
                        tzinfo=selected_zone,
                    )
                staged_schedule = stage_schedule(
                    checkpoint,
                    scheduler_context,
                    title=schedule_title,
                    prompt=schedule_prompt,
                    cadence=cadence,
                    capability=schedule_capability,
                    timezone_name=timezone_name,
                    hour=schedule_hour,
                    minute=schedule_minute,
                    weekday=schedule_weekday,
                    run_at=schedule_run_at,
                    confirmation=True,
                )
                if staged_schedule.get("status") == "STAGED":
                    _set_working_checkpoint(
                        staged_schedule.get("checkpoint") or checkpoint,
                        dirty=True,
                    )
                    st.success(
                        "Agenda registrada no Checkpoint de trabalho. "
                        "Ela ainda NÃO foi persistida externamente e NÃO será executada automaticamente."
                    )
                    st.rerun()
                else:
                    st.warning(
                        "Agenda não registrada: "
                        + str(
                            staged_schedule.get("reason")
                            or staged_schedule.get("status")
                            or "UNKNOWN"
                        )
                    )
            except Exception as exc:
                st.error(
                    "Agenda bloqueada em modo seguro: "
                    + type(exc).__name__
                    + ". Nenhuma execução foi autorizada."
                )

    st.markdown("#### ⚙️ Executor Local V1 · trabalhos devidos")
    executor_state = {
        "status": "UNAVAILABLE",
        "receipts": [],
        "receipt_count": 0,
        "due_count": 0,
        "autonomous_worker_connected": False,
        "physical_action_adapter": "UNAVAILABLE",
    }
    if executor_snapshot is not None:
        try:
            executor_state = executor_snapshot(access, checkpoint)
        except Exception as exc:
            executor_state = {
                "status": "UNKNOWN",
                "receipts": [],
                "receipt_count": 0,
                "due_count": 0,
                "autonomous_worker_connected": False,
                "physical_action_adapter": "UNAVAILABLE",
                "error_type": type(exc).__name__,
            }

    ex1, ex2, ex3, ex4 = st.columns(4)
    ex1.metric("Trabalhos devidos", int(executor_state.get("due_count") or 0))
    ex2.metric("Receipts", int(executor_state.get("receipt_count") or 0))
    ex3.metric(
        "Worker autônomo",
        "VER RUNTIME V1",
    )
    ex4.metric(
        "Ação física",
        str(executor_state.get("physical_action_adapter") or "UNAVAILABLE"),
    )
    st.caption(
        "O Executor V1 só roda por clique ADMIN autenticado e somente em capabilities "
        "locais allowlisted. Idempotência, Guardian e retry ficam registrados por ocorrência. "
        "Publicação, pagamento, deploy, trading e ações externas permanecem bloqueados."
    )

    executor_receipts = [
        row for row in list(executor_state.get("receipts") or [])
        if isinstance(row, Mapping)
    ]
    if executor_receipts:
        with st.expander("Receipts recentes do executor", expanded=False):
            st.dataframe(
                [
                    {
                        "Schedule": str(row.get("schedule_id") or ""),
                        "Capability": str(row.get("capability") or ""),
                        "Estado": str(row.get("state") or ""),
                        "Tentativa": int(row.get("attempt") or 0),
                        "Due": str(row.get("due_at") or ""),
                        "Motivo": str(row.get("reason") or ""),
                        "Retry": str(row.get("retry_after") or ""),
                    }
                    for row in executor_receipts[-50:]
                ],
                hide_index=True,
                width="stretch",
            )

    executor_batch_size = int(st.number_input(
        "Máximo de trabalhos locais por execução manual",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        key="aion_core_executor_batch_size",
    ))
    executor_confirm = st.checkbox(
        "Confirmo esta execução local dos trabalhos devidos. "
        "Isto NÃO autoriza provider, publicação, pagamento, deploy ou trading.",
        value=False,
        key="aion_core_executor_confirm",
    )
    if st.button(
        "▶️ Executar trabalhos locais devidos agora",
        key="aion_core_executor_run",
        disabled=not bool(
            executor_confirm
            and int(executor_state.get("due_count") or 0) > 0
            and execute_due_local_work is not None
        ),
        width="stretch",
    ):
        try:
            batch = execute_due_local_work(
                access,
                checkpoint,
                system_context=system_context,
                voice_status=core_voice_status,
                confirmation=True,
                max_jobs=executor_batch_size,
            )
            if int(batch.get("processed") or 0) > 0:
                _set_working_checkpoint(
                    batch.get("checkpoint") or checkpoint,
                    dirty=True,
                )
                st.session_state["aion_core_executor_last_batch"] = {
                    "status": str(batch.get("status") or "UNKNOWN"),
                    "processed": int(batch.get("processed") or 0),
                    "succeeded": int(batch.get("succeeded") or 0),
                    "failed": int(batch.get("failed") or 0),
                    "blocked": int(batch.get("blocked") or 0),
                    "external_persisted": False,
                }
                if int(batch.get("failed") or 0) > 0:
                    st.warning(
                        "Lote local processado com falhas controladas. "
                        "Os receipts registram retry/backoff; nenhuma ação externa foi executada."
                    )
                else:
                    st.success(
                        "Lote local processado e receipts colocados no Checkpoint de trabalho. "
                        "Ainda NÃO foi persistido externamente."
                    )
                st.rerun()
            else:
                st.info(
                    "Nenhum novo trabalho foi executado. Pode não haver tarefa devida "
                    "ou a ocorrência já possuir receipt terminal/idempotente."
                )
        except Exception as exc:
            st.error(
                "Executor bloqueado em modo seguro: "
                + type(exc).__name__
                + ". Nenhuma ação externa foi autorizada."
            )

    st.markdown("#### 🤖 Worker Runtime V1 · autonomia da sessão")
    worker_runtime_id = str(
        st.session_state.get(_AION_WORKER_RUNTIME_ID_KEY) or ""
    ).strip()
    if not worker_runtime_id:
        worker_runtime_id = "AION-WRK-" + uuid4().hex[:16].upper()
        st.session_state[_AION_WORKER_RUNTIME_ID_KEY] = worker_runtime_id

    worker_state = {
        "status": "UNAVAILABLE",
        "state": "DISABLED",
        "kill_switch": True,
        "retry_queue_count": 0,
        "lease_active": False,
        "lease_owned_by_this_runtime": False,
        "continuous_24x7_confirmed": False,
        "multi_instance_safe": False,
        "stats": {},
    }
    if worker_snapshot is not None:
        try:
            worker_state = worker_snapshot(
                access,
                checkpoint,
                runtime_id=worker_runtime_id,
            )
        except Exception as exc:
            worker_state = {
                "status": "UNKNOWN",
                "state": "DISABLED",
                "kill_switch": True,
                "retry_queue_count": 0,
                "lease_active": False,
                "lease_owned_by_this_runtime": False,
                "continuous_24x7_confirmed": False,
                "multi_instance_safe": False,
                "stats": {},
                "error_type": type(exc).__name__,
            }

    ws1, ws2, ws3, ws4 = st.columns(4)
    ws1.metric("Worker", str(worker_state.get("state") or "UNKNOWN"))
    ws2.metric(
        "Lease",
        "ATIVO" if worker_state.get("lease_active") else "LIVRE",
    )
    ws3.metric("Retry queue", int(worker_state.get("retry_queue_count") or 0))
    ws4.metric(
        "24/7 confirmado",
        "SIM" if worker_state.get("continuous_24x7_confirmed") else "NÃO",
    )
    st.caption(
        "Autonomia V1: somente durante esta sessão Streamlit ativa. "
        "Lease e heartbeat ficam no Checkpoint de trabalho. "
        "Multi-instância global: NÃO confirmada. Persistência externa automática: NÃO."
    )

    worker_interval = int(st.number_input(
        "Intervalo do worker (segundos)",
        min_value=60,
        max_value=900,
        value=int(worker_state.get("interval_seconds") or 60),
        step=30,
        key="aion_worker_interval_seconds",
    ))
    worker_lease_seconds = max(90, min(1800, worker_interval * 2 + 30))

    arm_confirm = st.checkbox(
        "Confirmo que quero armar a autonomia local da sessão. "
        "Somente capabilities allowlisted e sem efeitos externos.",
        value=False,
        key="aion_worker_arm_confirm",
    )
    wc1, wc2, wc3 = st.columns(3)
    if wc1.button(
        "🟢 Armar Worker",
        key="aion_worker_arm",
        disabled=not bool(arm_confirm and arm_worker is not None),
        width="stretch",
    ):
        try:
            armed = arm_worker(
                access,
                checkpoint,
                runtime_id=worker_runtime_id,
                confirmation=True,
                interval_seconds=worker_interval,
                lease_seconds=worker_lease_seconds,
            )
            if armed.get("status") == "ARMED":
                _set_working_checkpoint(
                    armed.get("checkpoint") or checkpoint,
                    dirty=True,
                )
                st.success(
                    "Worker armado para esta sessão. Nenhuma ação externa foi autorizada."
                )
                st.rerun()
        except Exception as exc:
            st.error(
                "Arming bloqueado em modo seguro: "
                + type(exc).__name__
                + "."
            )

    if wc2.button(
        "⏸️ Pausar Worker",
        key="aion_worker_pause",
        disabled=not bool(
            pause_worker is not None
            and str(worker_state.get("state") or "") == "ARMED"
        ),
        width="stretch",
    ):
        try:
            paused = pause_worker(
                access,
                checkpoint,
                confirmation=True,
            )
            _set_working_checkpoint(
                paused.get("checkpoint") or checkpoint,
                dirty=True,
            )
            st.info("Worker pausado. Lease liberado.")
            st.rerun()
        except Exception as exc:
            st.error("Pausa bloqueada: " + type(exc).__name__ + ".")

    if wc3.button(
        "🛑 Kill switch",
        key="aion_worker_kill",
        disabled=not bool(kill_worker is not None),
        width="stretch",
    ):
        try:
            killed = kill_worker(
                access,
                checkpoint,
                confirmation=True,
            )
            _set_working_checkpoint(
                killed.get("checkpoint") or checkpoint,
                dirty=True,
            )
            st.warning(
                "Kill switch acionado. O worker não executará novos ticks "
                "até novo arming explícito."
            )
            st.rerun()
        except Exception as exc:
            st.error("Kill switch bloqueado: " + type(exc).__name__ + ".")

    stats = (
        worker_state.get("stats")
        if isinstance(worker_state.get("stats"), Mapping)
        else {}
    )
    st.caption(
        "Ticks "
        + str(int(stats.get("ticks") or 0))
        + " · processados "
        + str(int(stats.get("processed") or 0))
        + " · sucesso "
        + str(int(stats.get("succeeded") or 0))
        + " · falhas "
        + str(int(stats.get("failed") or 0))
        + " · bloqueados "
        + str(int(stats.get("blocked") or 0))
        + " · crash recoveries "
        + str(int(stats.get("crash_recoveries") or 0))
        + "."
    )

    if (
        worker_tick is not None
        and str(worker_state.get("state") or "") == "ARMED"
        and not bool(worker_state.get("kill_switch"))
    ):
        try:
            @st.fragment(run_every=max(60, int(worker_state.get("interval_seconds") or 60)))
            def _aion_worker_fragment():
                live_checkpoint = ensure_operating_checkpoint(
                    st.session_state.get(_WORKING_CHECKPOINT_KEY)
                    if isinstance(st.session_state.get(_WORKING_CHECKPOINT_KEY), Mapping)
                    else checkpoint
                )
                try:
                    tick = worker_tick(
                        access,
                        live_checkpoint,
                        runtime_id=worker_runtime_id,
                        system_context=system_context,
                        voice_status=core_voice_status,
                        max_jobs=min(5, executor_batch_size),
                    )
                    updated_checkpoint = tick.get("checkpoint")
                    if isinstance(updated_checkpoint, Mapping):
                        before_digest = checkpoint_source_digest(live_checkpoint)
                        after_digest = checkpoint_source_digest(updated_checkpoint)
                        if after_digest != before_digest:
                            _set_working_checkpoint(
                                updated_checkpoint,
                                dirty=True,
                            )
                    st.caption(
                        "Worker tick · "
                        + str(tick.get("status") or "UNKNOWN")
                        + " · processados "
                        + str(int(tick.get("processed") or 0))
                        + " · retry queue "
                        + str(int(tick.get("retry_queue_count") or 0))
                        + " · efeitos externos NÃO."
                    )
                except Exception as exc:
                    st.caption(
                        "Worker tick bloqueado em modo seguro: "
                        + type(exc).__name__
                        + "."
                    )
            _aion_worker_fragment()
        except Exception as exc:
            st.caption(
                "Fragmento autônomo indisponível nesta execução: "
                + type(exc).__name__
                + ". Worker permanece fail-closed."
            )

    st.markdown("#### 🌐 Worker Global/Durable V1 · control plane")
    global_state = {
        "status": "UNAVAILABLE",
        "state": "DISABLED",
        "kill_switch": True,
        "fencing_counter": 0,
        "lease_active": False,
        "lease_owner": "",
        "delegated_scope_matches": False,
        "feature_flag_observed_here": False,
        "stats": {},
    }
    if global_worker_snapshot is not None:
        try:
            global_state = global_worker_snapshot(access, checkpoint)
        except Exception as exc:
            global_state = {
                "status": "UNKNOWN",
                "state": "DISABLED",
                "kill_switch": True,
                "fencing_counter": 0,
                "lease_active": False,
                "lease_owner": "",
                "delegated_scope_matches": False,
                "feature_flag_observed_here": False,
                "stats": {},
                "error_type": type(exc).__name__,
            }

    gw1, gw2, gw3, gw4 = st.columns(4)
    gw1.metric("Global Worker", str(global_state.get("state") or "UNKNOWN"))
    gw2.metric("Fencing", int(global_state.get("fencing_counter") or 0))
    gw3.metric(
        "Lease global",
        "ATIVO" if global_state.get("lease_active") else "LIVRE",
    )
    gw4.metric(
        "Runner flag local",
        "ON" if global_state.get("feature_flag_observed_here") else "OFF/UNKNOWN",
    )
    st.caption(
        "Control plane global usa o mesmo Checkpoint Mestre e CAS por SHA. "
        "O runner reaproveita o pulso GitHub Actions já existente; nenhum cron novo foi criado. "
        "A variável ATLASQUANT_AION_GLOBAL_WORKER_ENABLED continua OFF por padrão."
    )
    st.caption(
        "Armar/Pausar/Kill abaixo altera somente o Checkpoint de trabalho. "
        "O estado global só passa a valer depois do salvamento explícito do Checkpoint Mestre. "
        "Mesmo armado, publicação, pagamento, deploy, merge, provider e trading continuam bloqueados."
    )
    from atlasquant_aion_coordination_adapter_readiness import (
        coordination_adapter_readiness,
        format_coordination_adapter_caption,
    )
    st.markdown("##### Shared Coordination Adapter · readiness futuro")
    st.caption(format_coordination_adapter_caption(coordination_adapter_readiness(None)))
    st.caption(
        "Diagnóstico futuro e somente leitura. "
        "Nenhum provider foi conectado, nenhum probe foi executado, "
        "nenhuma feature flag foi alterada e o Worker Global não foi iniciado."
    )

    global_max_jobs = int(st.number_input(
        "Máximo de trabalhos por tick global",
        min_value=1,
        max_value=20,
        value=int(global_state.get("max_jobs") or 5),
        step=1,
        key="aion_global_worker_max_jobs",
    ))
    global_lease_seconds = int(st.number_input(
        "Lease global (segundos)",
        min_value=300,
        max_value=1800,
        value=int(global_state.get("lease_seconds") or 1200),
        step=60,
        key="aion_global_worker_lease_seconds",
    ))
    global_approval_ttl = int(st.number_input(
        "TTL da autorização de arming (segundos)",
        min_value=300,
        max_value=3600,
        value=900,
        step=300,
        key="aion_global_worker_approval_ttl",
    ))

    st.markdown("##### 🧾 Cerimônia de Arming")
    st.caption(
        "Etapa 1: gerar um plano preso ao contexto ADMIN e ao digest atual do Checkpoint. "
        "Gerar o plano NÃO altera o Checkpoint e NÃO ativa o runner."
    )
    if st.button(
        "🧾 Gerar plano de Arming",
        key="aion_global_worker_plan",
        disabled=prepare_global_worker_arming_plan is None,
        width="stretch",
    ):
        try:
            planned = prepare_global_worker_arming_plan(
                access,
                checkpoint,
                max_jobs=global_max_jobs,
                lease_seconds=global_lease_seconds,
                approval_ttl_seconds=global_approval_ttl,
            )
            if planned.get("status") == "PLAN_READY":
                st.session_state[_AION_GLOBAL_ARMING_PLAN_KEY] = planned.get("plan")
                st.session_state.pop(_AION_GLOBAL_ARMING_APPROVAL_KEY, None)
                st.success(
                    "Plano criado somente em memória da sessão. "
                    "Readiness real continua sendo evidência separada do gate #288."
                )
            else:
                st.warning(
                    "Plano não foi criado: "
                    + str(planned.get("reason") or planned.get("status") or "UNKNOWN")
                )
        except Exception as exc:
            st.error("Plano de arming bloqueado: " + type(exc).__name__ + ".")

    arming_plan = st.session_state.get(_AION_GLOBAL_ARMING_PLAN_KEY)
    if isinstance(arming_plan, Mapping):
        plan_budgets = (
            arming_plan.get("budgets")
            if isinstance(arming_plan.get("budgets"), Mapping)
            else {}
        )
        st.caption(
            "Plan digest: "
            + str(arming_plan.get("plan_digest") or "")[:24]
            + "… · expira em "
            + str(arming_plan.get("expires_at") or "UNKNOWN")
        )
        pb1, pb2, pb3, pb4 = st.columns(4)
        pb1.metric("Jobs/tick", int(plan_budgets.get("max_jobs_per_tick") or 0))
        pb2.metric(
            "Writes runtime/tick",
            int(plan_budgets.get("max_runtime_checkpoint_writes_per_tick") or 0),
        )
        pb3.metric(
            "Provider calls",
            int(plan_budgets.get("provider_calls_per_tick") or 0),
        )
        pb4.metric(
            "Ordens reais",
            int(plan_budgets.get("market_orders_per_tick") or 0),
        )
        st.caption(
            "Pré-requisito registrado no plano: READY_FOR_ADMIN_ARMING. "
            "O plano não declara que esse readiness foi verificado; essa prova vem do gate read-only."
        )

        global_phrase = st.text_input(
            'Digite exatamente "ARMAR WORKER GLOBAL" para autorizar este plano',
            value="",
            key="aion_global_worker_confirmation_phrase",
        )
        global_plan_confirm = st.checkbox(
            "Confirmo este plano, escopo, TTL e budgets para apenas preparar o estado ARMED staged.",
            value=False,
            key="aion_global_worker_plan_confirm",
        )
        if st.button(
            "✅ Criar autorização temporária",
            key="aion_global_worker_approve_plan",
            disabled=not bool(
                global_plan_confirm
                and approve_global_worker_arming_plan is not None
            ),
            width="stretch",
        ):
            try:
                approved_plan = approve_global_worker_arming_plan(
                    access,
                    arming_plan,
                    confirmation=True,
                    confirmation_phrase=global_phrase,
                )
                if approved_plan.get("status") == "APPROVED_FOR_STAGING":
                    st.session_state[_AION_GLOBAL_ARMING_APPROVAL_KEY] = (
                        approved_plan.get("approval")
                    )
                    st.success(
                        "Autorização temporária criada somente na sessão. "
                        "Ainda não houve alteração do Checkpoint nem do runtime."
                    )
                else:
                    st.warning(
                        "Autorização bloqueada: "
                        + str(
                            approved_plan.get("reason")
                            or approved_plan.get("status")
                            or "UNKNOWN"
                        )
                    )
            except Exception as exc:
                st.error(
                    "Autorização temporária bloqueada: "
                    + type(exc).__name__
                    + "."
                )

    arming_approval = st.session_state.get(_AION_GLOBAL_ARMING_APPROVAL_KEY)
    if isinstance(arming_approval, Mapping):
        st.caption(
            "Approval digest: "
            + str(arming_approval.get("approval_digest") or "")[:24]
            + "… · expira em "
            + str(arming_approval.get("expires_at") or "UNKNOWN")
        )
        if st.button(
            "🌐 Preparar ARMED (staged, sem salvar)",
            key="aion_global_worker_stage_armed",
            disabled=stage_arm_global_worker is None,
            width="stretch",
        ):
            try:
                armed_global = stage_arm_global_worker(
                    access,
                    checkpoint,
                    confirmation=True,
                    arming_approval=arming_approval,
                    max_jobs=global_max_jobs,
                    lease_seconds=global_lease_seconds,
                )
                if armed_global.get("status") == "STAGED_ARMED":
                    _set_working_checkpoint(
                        armed_global.get("checkpoint") or checkpoint,
                        dirty=True,
                    )
                    st.session_state.pop(_AION_GLOBAL_ARMING_PLAN_KEY, None)
                    st.session_state.pop(_AION_GLOBAL_ARMING_APPROVAL_KEY, None)
                    st.success(
                        "Estado ARMED preparado somente no Checkpoint de trabalho. "
                        "NÃO foi salvo no runtime e a feature flag continua separada."
                    )
                    st.rerun()
                else:
                    st.warning(
                        "Staging bloqueado: "
                        + str(
                            armed_global.get("reason")
                            or armed_global.get("status")
                            or "UNKNOWN"
                        )
                    )
            except Exception as exc:
                st.error(
                    "Staging ARMED bloqueado em modo seguro: "
                    + type(exc).__name__
                    + "."
                )

    gc2, gc3 = st.columns(2)
    if gc2.button(
        "⏸️ Pausar Global (staged)",
        key="aion_global_worker_pause",
        disabled=not bool(
            stage_pause_global_worker is not None
            and str(global_state.get("state") or "") == "ARMED"
        ),
        width="stretch",
    ):
        try:
            paused_global = stage_pause_global_worker(
                access,
                checkpoint,
                confirmation=True,
            )
            _set_working_checkpoint(
                paused_global.get("checkpoint") or checkpoint,
                dirty=True,
            )
            st.info(
                "Pausa global colocada no Checkpoint de trabalho. "
                "Salve o Checkpoint Mestre para torná-la global."
            )
            st.rerun()
        except Exception as exc:
            st.error("Pausa global bloqueada: " + type(exc).__name__ + ".")

    if gc3.button(
        "🛑 Kill Global (staged)",
        key="aion_global_worker_kill",
        disabled=not bool(stage_kill_global_worker is not None),
        width="stretch",
    ):
        try:
            killed_global = stage_kill_global_worker(
                access,
                checkpoint,
                confirmation=True,
            )
            _set_working_checkpoint(
                killed_global.get("checkpoint") or checkpoint,
                dirty=True,
            )
            st.warning(
                "Kill switch global colocado no Checkpoint de trabalho. "
                "Use Salvar Checkpoint Mestre para persistir o bloqueio no runtime compartilhado."
            )
            st.rerun()
        except Exception as exc:
            st.error("Kill global bloqueado: " + type(exc).__name__ + ".")

    global_stats = (
        global_state.get("stats")
        if isinstance(global_state.get("stats"), Mapping)
        else {}
    )
    st.caption(
        "Global ticks "
        + str(int(global_stats.get("ticks") or 0))
        + " · processados "
        + str(int(global_stats.get("processed") or 0))
        + " · conflitos lease "
        + str(int(global_stats.get("lease_conflicts") or 0))
        + " · conflitos checkpoint "
        + str(int(global_stats.get("checkpoint_conflicts") or 0))
        + " · crash recoveries "
        + str(int(global_stats.get("crash_recoveries") or 0))
        + "."
    )

    provider_env = _provider_env()
    provider = provider_status(feature_flags=flags, env=provider_env)
    budget = normalize_budget((checkpoint.get("aion") or {}).get("model_budget", {}))
    hits_preview = _aion_memory_hits(question, checkpoint) if question.strip() else []
    domain_preview = route_context(question).get("domain") if question.strip() else "central"
    cognitive_preview = orchestrator_snapshot(
        question,
        domain_hint=domain_preview,
        memory_hits=hits_preview,
        system_context=system_context,
    ) if question.strip() else {}
    if cognitive_preview:
        selected = [
            x for x in list((cognitive_preview.get("routing") or {}).get("selected", []) or [])
            if isinstance(x, Mapping)
        ]
        with st.expander("🧠 Conselho Cognitivo · especialistas + Critic", expanded=False):
            c1,c2,c3 = st.columns(3)
            c1.metric("Especialistas", int((cognitive_preview.get("routing") or {}).get("selected_count") or 0))
            c2.metric("Readiness", str(cognitive_preview.get("readiness") or "UNKNOWN"))
            c3.metric("Critic", "OBRIGATÓRIO" if bool((cognitive_preview.get("critic_gate") or {}).get("required", True)) else "NÃO")
            if selected:
                st.markdown("**Especialistas selecionados:** " + " · ".join(str(x.get("name") or x.get("id")) for x in selected))
            blockers = list((cognitive_preview.get("research_plan") or {}).get("blockers", []) or [])
            if blockers:
                for blocker in blockers:
                    st.warning(str(blocker))
            stages = list((cognitive_preview.get("research_plan") or {}).get("steps", []) or [])
            if stages:
                st.dataframe([
                    {"Etapa":row.get("stage"),"Regra":row.get("instruction")}
                    for row in stages if isinstance(row, Mapping)
                ], width="stretch", hide_index=True)
            st.caption(
                "O AION não mostra raciocínio privado/chain-of-thought. Ele mostra conclusão, evidências, "
                "conflitos, lacunas e justificativa verificável."
            )
    access_session = access.get("session") if isinstance(access.get("session"), Mapping) else {}
    access_role = str(access.get("role") or access_session.get("role") or "USER").upper()
    core_preview = orchestrate_aion_core(
        question,
        context={
            "role": access_role,
            "persona": "admin",
            "experience_mode": "ADVANCED" if view_mode == "Completo" else "BEGINNER",
            "domain_hint": domain_preview,
        },
    ) if question.strip() else {}
    if core_preview:
        dispatch_preview = plan_specialist_dispatch(core_preview)
        selected_capability = dict(core_preview.get("selected_capability") or {})
        truth_preview = dict(core_preview.get("truth") or {})
        decision_preview = dict(core_preview.get("decision") or {})
        with st.expander("⚙️ Orquestração AION · plano e gates", expanded=False):
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Especialista", str(selected_capability.get("specialist") or "core").upper())
            o2.metric("Capability", str(selected_capability.get("capability_id") or "UNKNOWN"))
            o3.metric("Verdade", str(truth_preview.get("status") or "UNKNOWN"))
            o4.metric("Decisão", str(decision_preview.get("state") or "BLOCKED"))
            if specialist_snapshot is None:
                specialist_session = loaded_session_from_checkpoint(checkpoint)
            else:
                specialist_session = specialist_snapshot
            local_evidence = read_specialist_evidence(
                dispatch_preview.get("specialist"),
                session=specialist_session,
            )
            evidence_conflicts = [
                str(item.get("claim") or "conflito")
                for item in list(local_evidence.get("conflicts") or [])
                if isinstance(item, Mapping)
            ]
            st.caption(
                f"Dispatch {dispatch_preview.get('state')} · risco "
                f"{(core_preview.get('risk') or {}).get('level', 'UNKNOWN')} · "
                "Builder → Critic → Validator · nenhuma ação é executada nesta prévia."
            )
            st.caption(
                "Leitura local do especialista: "
                + str(local_evidence.get("summary") or "sem leitura")
                + " Verdade da resposta: "
                + str(local_evidence.get("answer_truth") or "UNKNOWN")
                + ". Esta leitura não responde à pergunta."
            )
            st.caption(
                "Snapshot "
                + str(local_evidence.get("origin") or "SESSION")
                + " · observed_at "
                + str(local_evidence.get("observed_at") or "não informado")
                + " · freshness "
                + str(local_evidence.get("freshness") or "UNVERIFIED")
                + " · truth_state "
                + str(local_evidence.get("truth_state") or "UNKNOWN")
                + " · input_state "
                + str(local_evidence.get("input_state") or "ABSENT")
                + " · conflicts "
                + ("nenhum" if not evidence_conflicts else " · ".join(evidence_conflicts))
                + " · evidência observada "
                + evidence_scope_label(local_evidence)
                + " · answers_user_question "
                + ("NÃO" if not local_evidence.get("answers_user_question") else "SIM")
                + "."
            )
            blockers = list(decision_preview.get("blockers") or [])
            if blockers:
                st.warning("Bloqueios: " + " · ".join(str(x) for x in blockers))
            if view_mode == "Completo":
                st.dataframe([
                    {
                        "Etapa": row.get("stage"),
                        "Estado": row.get("status"),
                        "Executa ação": row.get("executes_action"),
                    }
                    for row in list((core_preview.get("plan") or {}).get("steps", []) or [])
                    if isinstance(row, Mapping)
                ], hide_index=True, width="stretch")
    capability_plan_preview = plan_agentic_mission(
        question,
        access=access,
        feature_flags=flags,
        system_context=system_context,
    ) if question.strip() else {}
    if capability_plan_preview:
        with st.expander("🧭 Planejador Agentivo · capacidades + gates", expanded=False):
            p1,p2,p3,p4 = st.columns(4)
            p1.metric("Estado", str(capability_plan_preview.get("readiness") or "UNKNOWN"))
            p2.metric("Local agora", int(capability_plan_preview.get("available_local") or 0))
            p3.metric("Aprovações", int(capability_plan_preview.get("approval_gates") or 0))
            p4.metric("Bloqueios/deps", int(capability_plan_preview.get("blockers") or 0))
            stages = [
                row for row in list(capability_plan_preview.get("stages", []) or [])
                if isinstance(row, Mapping)
            ]
            if stages:
                st.dataframe([
                    {
                        "Etapa":row.get("order"),
                        "Capacidade":row.get("label"),
                        "Estado":row.get("state"),
                        "Aprovação": "SIM" if row.get("requires_explicit_approval") else "NÃO",
                        "Evidência":", ".join(row.get("evidence_requirements") or []),
                        "Motivo":row.get("reason"),
                    }
                    for row in stages
                ], width="stretch", hide_index=True)
            next_stage = capability_plan_preview.get("next_safe_stage")
            if isinstance(next_stage, Mapping):
                st.caption(
                    "Próxima etapa segura de planejamento: "
                    + str(next_stage.get("label") or next_stage.get("capability_id"))
                    + "."
                )
            st.caption(
                "O plano não concede aprovação e não executa ferramenta, conector, deploy, "
                "publicação, pagamento ou ordem real."
            )

    prompt_preview = build_provider_prompt(
        question,
        domain=domain_preview,
        memory_hits=hits_preview,
        system_context=system_context,
    ) if question.strip() else ""
    local_command_preview = orchestrate_local_command(
        question,
        execute=False,
    ) if question.strip() else {}
    if local_command_preview:
        preview_state = str(local_command_preview.get("state") or "")
        preview_plan = (
            local_command_preview.get("plan")
            if isinstance(local_command_preview.get("plan"), Mapping)
            else {}
        )
        if preview_state in {"PLANNED", "PLANNED_MULTI"}:
            preview_ids = list(local_command_preview.get("tool_ids") or [])
            if not preview_ids and preview_plan.get("tool_id"):
                preview_ids = [str(preview_plan.get("tool_id"))]
            st.caption(
                "Tool Hub local · prévia: "
                + (" · ".join(preview_ids) if preview_ids else "nenhum")
                + " · modo "
                + str(local_command_preview.get("mode") or "SINGLE")
                + ". Handler(s) só rodam após clicar em Analisar com AION e cada chamada passar pelo preflight."
            )
        elif preview_state == "BLOCKED_INTENT":
            st.warning(
                "O comando contém intenção sensível/externa. O orquestrador local não tentará "
                "converter esse pedido em READ/SEARCH/DRAFT nem executar um handler."
            )
    estimate = estimate_request_cost(
        prompt_preview,
        config=provider_config(provider_env),
    ) if prompt_preview else {
        "estimable": False,
        "estimated_max_cost_usd": None,
        "state": "NO_PROMPT",
    }

    external_ready = bool(
        provider.get("state") == "EXTERNAL_READY"
        and flags.get("external_llm", False)
        and budget.get("allow_paid", False)
        and estimate.get("estimable", False)
    )
    use_external = st.checkbox(
        "Usar inteligência externa nesta pergunta",
        value=False,
        disabled=not external_ready,
        key="aion_use_external_model",
        help=(
            "Só fica disponível quando feature flag, provedor, preços e orçamento estão configurados. "
            "Desmarcado = resposta local/custo zero."
        ),
    )
    approve_external = False
    if use_external:
        estimated_cost = estimate.get("estimated_max_cost_usd")
        st.warning(
            f"Custo máximo estimado desta solicitação: US$ {float(estimated_cost or 0):.6f}. "
            "É uma estimativa técnica; a cobrança real pertence ao provedor."
        )
        approve_external = st.checkbox(
            "Aprovo esta solicitação externa dentro do teto informado",
            value=False,
            key="aion_external_request_approval",
        )
    elif provider.get("state") != "ZERO_COST_LOCAL":
        st.caption(
            f"IA externa: {provider.get('state')} · "
            "nenhuma chamada paga será feita sem configuração e aprovação."
        )

    if st.button("Analisar com AION", key="aion_admin_ask", type="primary", width="stretch"):
        hits = _aion_memory_hits(question, checkpoint)
        estimated_cost = float(estimate.get("estimated_max_cost_usd") or 0.0)
        core_orchestration = orchestrate_aion_core(
            question,
            context={
                "role": access_role,
                "persona": "admin",
                "experience_mode": "ADVANCED" if view_mode == "Completo" else "BEGINNER",
                "domain_hint": domain_preview,
            },
        )
        st.session_state["aion_last_core_orchestration"] = core_orchestration
        route = route_intelligence(
            question,
            provider_state=provider.get("state"),
            external_feature_enabled=bool(flags.get("external_llm", False)),
            budget=budget,
            estimated_request_cost_usd=estimated_cost,
            request_approved=bool(use_external and approve_external),
        )

        answer = None
        if use_external and approve_external and str(route.get("lane") or "").startswith("EXTERNAL_"):
            prompt = build_provider_prompt(
                question,
                domain=route_context(question).get("domain"),
                memory_hits=hits,
                system_context=system_context,
            )
            external = execute_openai_answer(
                prompt,
                lane=route.get("lane"),
                budget=budget,
                external_feature_enabled=bool(flags.get("external_llm", False)),
                request_approved=True,
                values=provider_env,
            )
            st.session_state["aion_last_external_state"] = external
            if external.get("state") == "ANSWER_READY":
                answer = {
                    "schema": "ATLASQUANT_AION_EXTERNAL_ANSWER_V1",
                    "answer": external.get("answer"),
                    "domain": route_context(question).get("domain"),
                    "provider": provider,
                    "evidence": hits,
                    "truth_state": external.get("truth_state"),
                    "executes_action": False,
                    "real_orders_enabled": False,
                }
                usage = external.get("usage") if isinstance(external.get("usage"), Mapping) else {}
                tracked_cost = usage.get("actual_cost_usd_estimate")
                if tracked_cost is None:
                    tracked_cost = estimated_cost
                updated = record_model_spend_estimate(checkpoint, tracked_cost)
                updated = update_operating_checkpoint(updated, dirty=True)
                updated = _record_working_event(
                    updated,
                    "external_model_answer",
                    "AION recebeu uma resposta de modelo externo para uma consulta aprovada.",
                    evidence={
                        "lane": route.get("lane"),
                        "model": external.get("model"),
                        "tracked_cost_usd_estimate": tracked_cost,
                        "truth_state": external.get("truth_state"),
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
            else:
                st.warning(
                    "A chamada externa não foi concluída. "
                    f"Estado: {external.get('state')} · motivo: {external.get('reason','não informado')}."
                )

        if answer is None:
            local_tool_call = orchestrate_local_command(
                question,
                execute=True,
                runtime_context={
                    "checkpoint": checkpoint,
                    "memory_layers": (
                        checkpoint.get("memory_layers")
                        if isinstance(checkpoint.get("memory_layers"), Mapping)
                        else {}
                    ),
                    "session": specialist_snapshot if isinstance(specialist_snapshot, Mapping) else None,
                    "system_context": dict(system_context),
                    "persona": "admin",
                },
                hub=(
                    checkpoint.get("tool_hub")
                    if isinstance(checkpoint.get("tool_hub"), Mapping)
                    else None
                ),
                portable_core=(
                    checkpoint.get("portable_core")
                    if isinstance(checkpoint.get("portable_core"), Mapping)
                    else None
                ),
                access=access,
                feature_flags=flags,
                source_kind="ADMIN",
                authenticated_admin=is_admin(access),
                request_id="aion-admin-local-command",
            )
            answer = local_answer(
                question,
                checkpoint=checkpoint,
                memory_hits=hits,
                system_context=dict(system_context),
                feature_flags=flags,
            )
            if isinstance(answer, Mapping):
                answer = dict(answer)
                local_state = str(local_tool_call.get("state") or "")
                if local_state not in {"", "NO_MATCH", "NO_COMMAND"}:
                    answer["local_tool_call"] = local_tool_call
                    local_summary = str(local_tool_call.get("summary") or "").strip()
                    if local_summary:
                        answer["answer"] = (
                            str(answer.get("answer") or "").rstrip()
                            + " Tool Hub local: "
                            + local_summary
                        ).strip()
            st.session_state["aion_last_local_tool_call"] = local_tool_call
        unified_result = build_aion_result(
            core_orchestration,
            answer=answer.get("answer", ""),
            evidence=answer.get("evidence") if isinstance(answer.get("evidence"), list) else hits,
            provider_state=route.get("lane"),
        )
        st.session_state["aion_last_route"] = route
        st.session_state["aion_last_answer"] = answer
        st.session_state["aion_last_unified_result"] = unified_result

    route = st.session_state.get("aion_last_route")
    if isinstance(route, Mapping):
        st.caption(
            f"Roteamento: {route.get('lane')} · complexidade {route.get('complexity')} · "
            f"{route.get('reason')}"
        )

    answer = st.session_state.get("aion_last_answer")
    if isinstance(answer, Mapping):
        st.markdown("#### Resposta AION")
        unified_result = st.session_state.get("aion_last_unified_result")
        validation = {}
        evidence_count = 0
        if isinstance(unified_result, Mapping):
            evidence_count = int(unified_result.get("evidence_count") or 0)
            if isinstance(unified_result.get("validation"), Mapping):
                validation = unified_result.get("validation")
        presentation = present_validated_answer(validation, answer=answer.get("answer", ""))
        if presentation["display"] == "ANSWER":
            st.write(presentation["text"])
        elif presentation["display"] == "BLOCK":
            st.error(presentation["notice"])
            if presentation["issues"]:
                st.caption("Motivo: " + ", ".join(presentation["issues"]))
        else:
            st.warning(presentation["notice"])
            if presentation["issues"]:
                st.caption("Pendências: " + ", ".join(presentation["issues"]))
        st.caption(
            f"Validação: {presentation['state']} · "
            f"verdade {presentation['truth_status']} · "
            f"{evidence_count} evidência(s)"
        )
        cognitive_answer = answer.get("cognitive_orchestrator")
        if isinstance(cognitive_answer, Mapping):
            routing = (
                cognitive_answer.get("routing")
                if isinstance(cognitive_answer.get("routing"), Mapping)
                else {}
            )
            selected_names = [
                str(x.get("name") or "")
                for x in list(routing.get("selected", []) or [])
                if isinstance(x, Mapping) and str(x.get("name") or "").strip()
            ]
            if selected_names:
                st.caption("Conselho usado: " + " · ".join(selected_names[:5]) + " · Critic: obrigatório")
        evidence = answer.get("evidence")
        if isinstance(evidence, list) and evidence:
            with st.expander("Evidências da memória"):
                for hit in evidence:
                    review = str(hit.get("review_state") or "").strip()
                    suffix = f" · revisão {review}" if review else ""
                    st.caption(
                        f"{hit.get('path')} · verdade {hit.get('kind') or hit.get('truth_state') or 'UNKNOWN'}"
                        f" · score {hit.get('score')}{suffix}"
                    )
                    st.write(hit.get("excerpt"))

    spoken = (
        f"Bem-vindo à Central AION. A prioridade atual é "
        f"{(checkpoint.get('aion') or {}).get('priority','revisar o checkpoint')}. "
        "O AION trabalha com regra da verdade, custo controlado e ordens reais bloqueadas."
    )
    _context_voice("Central", spoken, key="aion_admin_welcome_voice")

    st.markdown("#### Secretaria executiva")
    st.caption(
        "AION consolida tarefas, pendências e aprovações. Agenda, e-mail e clientes externos "
        "só entram como confirmados quando a fonte correspondente estiver conectada."
    )
    if bool(st.session_state.get(_WORKING_DIRTY_KEY, False)):
        st.warning("Há alterações locais no Checkpoint Mestre aguardando salvamento no runtime.")


def _render_secretary(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    market_context: Mapping[str, Any],
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
) -> None:
    st.markdown("### 🗂️ Secretaria AION")
    _render_persona_capabilities("admin", {
        "system_status": bool(status_board),
        "incidents": isinstance(system_context.get("reliability"), Mapping),
        "pending": isinstance(checkpoint.get("pending"), list),
        "checks": bool(system_context.get("source_build")),
        "degraded_sources": isinstance(system_context.get("source_mesh"), Mapping),
        "tasks": isinstance((checkpoint.get("operating") or {}).get("tasks"), list),
        "checkpoint": bool(checkpoint),
    })
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = list(operating.get("tasks", []) or [])
    events = list(operating.get("events", []) or [])
    summary = queue_summary(tasks)
    obs = observability_summary(events)
    brief = executive_briefing(
        tasks=tasks,
        events=events,
        system_context=system_context,
        market_context=market_context,
        clients_context={"truth_state":"UNKNOWN"},
        content_context={"truth_state":"UNKNOWN"},
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Ativas", summary["active"])
    c2.metric("Aprovação", summary["waiting_approval"])
    c3.metric("Bloqueadas", summary["blocked"])
    c4.metric("Alertas", obs["by_severity"]["WARNING"] + obs["by_severity"]["ERROR"] + obs["by_severity"]["CRITICAL"])

    st.markdown("#### Briefing executivo")
    st.write(brief["system"]["message"])
    st.write(brief["market"]["message"])
    st.write(brief["clients"]["message"])
    st.write(brief["content"]["message"])
    if bool(approval_inbox.get("has_pending")):
        st.warning(
            f"Central de Aprovações: {int(approval_inbox.get('total') or 0)} item(ns) aguardam decisão administrativa."
        )
    else:
        st.caption("Central de Aprovações: nenhuma decisão pendente nesta memória.")
    attention = status_board.get("attention") if isinstance(status_board.get("attention"), list) else []
    with st.expander("Pendências do Painel Mestre", expanded=False):
        if attention:
            for item in attention[:10]:
                st.markdown(
                    f"- **{item.get('state')} · {item.get('label')}** — "
                    f"{item.get('detail')}"
                )
                if item.get("next_action"):
                    st.caption("Próxima ação: " + str(item.get("next_action")))
        else:
            st.write("Nenhuma pendência foi fornecida pelo Painel Mestre nesta execução.")
    _context_voice(
        "Secretaria",
        (
            f"Bem-vindo à Secretaria AION. Existem {summary['active']} tarefas ativas, "
            f"{summary['waiting_approval']} aguardando aprovação e {summary['blocked']} bloqueadas. "
            "Mercado, clientes e conteúdo só são anunciados quando a fonte está confirmada."
        ),
        key="aion_secretary_voice",
    )

    st.markdown("#### Nova tarefa")
    with st.form("aion_secretary_new_task", clear_on_submit=True):
        title = st.text_input("Tarefa")
        cdom,cprio = st.columns(2)
        domain = cdom.selectbox(
            "Área",
            ["central","trading","studio","business","laboratory","secretary","development","subscriptions","promotions"],
        )
        priority = cprio.selectbox("Prioridade", list(PRIORITIES), index=2)
        action = st.selectbox("Tipo de ação", list(ACTIONS), index=0)
        note = st.text_area("Observação", max_chars=1200)
        cost = st.number_input("Custo mensal estimado (USD)", min_value=0.0, value=0.0, step=1.0)
        submit = st.form_submit_button("Adicionar à fila", type="primary")
    if submit:
        try:
            task = new_task(
                title,
                domain=domain,
                priority=priority,
                action=action,
                note=note,
                estimated_monthly_cost_usd=cost,
                source=str(access.get("username") or "ADMIN"),
            )
            requirement = approval_requirement(task, access, feature_flags=flags)
            if requirement["required"]:
                task["status"] = "WAITING_APPROVAL"
                task["approval"]["required"] = True
            tasks = upsert_task(tasks, task)
            updated = update_operating_checkpoint(checkpoint, tasks=tasks, events=events, dirty=True)
            updated = _record_working_event(
                updated,
                "task_created",
                f"Tarefa criada: {task['title']}",
                evidence={"task_id":task["task_id"],"action":task["action"],"priority":task["priority"]},
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Tarefa adicionada à memória operacional local.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a tarefa: {type(exc).__name__}")

    if tasks:
        rows = [{
            "ID":x.get("task_id"),
            "Prioridade":x.get("priority"),
            "Status":x.get("status"),
            "Área":x.get("domain"),
            "Ação":x.get("action"),
            "Tarefa":x.get("title"),
            "Custo USD":x.get("estimated_monthly_cost_usd"),
        } for x in tasks]
        st.dataframe(rows, width="stretch", hide_index=True)

        options=[str(x.get("task_id")) for x in tasks]
        selected_id=st.selectbox("Tarefa selecionada", options, key="aion_secretary_selected_task")
        selected=next((x for x in tasks if str(x.get("task_id"))==selected_id),None)
        if isinstance(selected,Mapping):
            st.caption(
                f"{selected.get('priority')} · {selected.get('status')} · {selected.get('domain')} · "
                f"ação {selected.get('action')}"
            )
            b1,b2,b3,b4=st.columns(4)
            if b1.button("▶️ Iniciar", key="aion_task_start"):
                tasks=transition_task(tasks,selected_id,"IN_PROGRESS")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_started",f"Tarefa iniciada: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
            if b2.button("✅ Aprovar", key="aion_task_approve"):
                try:
                    tasks=approve_task(tasks,selected_id,access,feature_flags=flags)
                    updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                    _set_working_checkpoint(_record_working_event(updated,"task_approved",f"Aprovação registrada: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")
            if b3.button("✔️ Concluir", key="aion_task_done"):
                tasks=transition_task(tasks,selected_id,"DONE")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_done",f"Tarefa concluída manualmente: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
            if b4.button("⛔ Cancelar", key="aion_task_cancel"):
                tasks=transition_task(tasks,selected_id,"CANCELED")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_canceled",f"Tarefa cancelada: {selected_id}",severity="NOTICE",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
    else:
        st.info("A fila operacional do AION está vazia.")

    st.markdown("#### Handoff da sessão")
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    handoff_preview = build_session_handoff(
        missions,
        tasks=tasks,
        events=events,
        checkpoint_digest=checkpoint_digest(checkpoint),
        source=str(access.get("username") or "ADMIN"),
    )
    st.caption(
        "O preview é montado apenas com o estado registrado no Checkpoint. "
        "Registrar o handoff grava a continuidade na memória de trabalho; persistência definitiva ainda exige salvar o Checkpoint."
    )
    h1,h2,h3 = st.columns(3)
    h1.metric("Foco", str(handoff_preview.get("current_focus") or "sem missão ativa")[:80])
    h2.metric("Bloqueios", len(list(handoff_preview.get("blockers") or [])))
    h3.metric("Próximos passos", len(list(handoff_preview.get("next_steps") or [])))
    if handoff_preview.get("next_steps"):
        st.markdown("**Próximos passos do handoff:**")
        for item in list(handoff_preview.get("next_steps") or [])[:8]:
            st.markdown(f"- {item}")

    if st.button(
        "📌 Registrar handoff no Checkpoint",
        key="aion_register_session_handoff",
        width="stretch",
    ):
        updated_handoffs = append_handoff(handoffs, handoff_preview)
        updated = update_continuity_checkpoint(
            checkpoint,
            missions=missions,
            handoffs=updated_handoffs,
            dirty=True,
        )
        updated = _record_working_event(
            updated,
            "session_handoff_recorded",
            "Handoff estruturado da sessão registrado na memória de trabalho.",
            evidence={
                "handoff_id":handoff_preview.get("handoff_id"),
                "current_focus":handoff_preview.get("current_focus"),
                "next_steps":len(list(handoff_preview.get("next_steps") or [])),
                "automatic_execution":False,
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success("Handoff registrado localmente. Salve o Checkpoint Mestre para persistir entre sessões.")
        st.rerun()

    with st.expander("Observabilidade / auditoria"):
        st.caption(
            f"Eventos: {obs['total']} · warnings {obs['by_severity']['WARNING']} · "
            f"errors {obs['by_severity']['ERROR']} · críticos {obs['by_severity']['CRITICAL']}"
        )
        if events:
            st.dataframe(list(reversed(events[-30:])), width="stretch", hide_index=True)
        else:
            st.write("Nenhum evento operacional registrado nesta memória.")


def _render_trading(
    market_context: Mapping[str, Any],
    system_context: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 📈 Trading · leitura segura")
    _render_persona_capabilities("trader", {
        "radar": bool(market_context.get("fresh_confirmed", False)),
        "macro": bool(market_context.get("fresh_confirmed", False)),
        "pairs": bool(market_context.get("fresh_confirmed", False)),
        "calendar": isinstance((system_context or {}).get("live_event_intelligence"), Mapping),
        "pre_news": isinstance((system_context or {}).get("live_event_intelligence"), Mapping),
        "technical_context": bool(market_context.get("technical_confirmed", False)),
        "risk": isinstance((system_context or {}).get("reliability"), Mapping),
    })
    market_text, market_truth = _safe_market_state(market_context)
    st.info(f"Estado: {market_truth} — {market_text}")
    st.markdown(
        "- AION pode explicar Radar, Macro, dados, filtros, Gate e evidências já calculadas.\n"
        "- AION não converte score em promessa de lucro.\n"
        "- AION não habilita corretora nem execução real.\n"
        "- Backtest/Paper/Forward continuam separados de produção real."
    )
    _context_voice(
        "Trading",
        (
            "Bem-vindo ao Trading do AION. Aqui eu explico Radar, Macro e evidências já calculadas. "
            f"O estado de mercado nesta tela é {market_truth}. Ordens reais permanecem bloqueadas."
        ),
        key="aion_trading_voice",
    )

    _render_live_event_intelligence({}, system_context, allow_memory_sync=False)

    st.markdown("#### 🧪 Simulador de Cenários Macro")
    st.caption(
        "Simula mecanismos possíveis a partir de uma surpresa hipotética. "
        "Não é previsão ao vivo, não é sinal e não representa probabilidade de lucro."
    )
    c_event,c_surprise = st.columns(2)
    event = c_event.selectbox(
        "Evento",
        scenario_events(),
        format_func=lambda x: {
            "CPI":"CPI / inflação",
            "PCE":"PCE",
            "PAYROLL":"Payroll / NFP",
            "FOMC":"FOMC / Fed",
            "GEOPOLITICAL_RISK":"Risco geopolítico",
        }.get(x,x),
        key="aion_macro_scenario_event",
    )
    surprise = c_surprise.selectbox(
        "Hipótese",
        ("ABOVE","BELOW"),
        format_func=lambda x: (
            "Acima / mais forte / hawkish / escalada"
            if x=="ABOVE"
            else "Abaixo / mais fraco / dovish / desescalada"
        ),
        key="aion_macro_scenario_surprise",
    )

    live_evidence = [{
        "claim":"market_context",
        "kind":"CONFIRMED" if bool(market_context.get("fresh_confirmed",False)) else "UNKNOWN",
        "source":"market_context",
        "value":market_text,
        "note":"Contexto fornecido à tela Trading.",
    }]
    scenario = simulate_macro_scenario(
        event,
        surprise,
        evidence=live_evidence,
    )
    sc_conf = (
        scenario.get("evidence_confidence")
        if isinstance(scenario.get("evidence_confidence"), Mapping)
        else {}
    )
    s1,s2,s3 = st.columns(3)
    s1.metric("Estado", str(scenario.get("scenario_truth_kind") or "UNKNOWN"))
    s2.metric("Evidência ao vivo", f"{int(sc_conf.get('score') or 0)}/100")
    s3.metric("Sinal de trade", "NÃO")
    st.write(f"**Cenário:** {scenario.get('headline') or 'não mapeado'}")
    channels = list(scenario.get("channels") or [])
    if channels:
        st.dataframe([
            {
                "Ativo/canal":row.get("asset"),
                "Possível reação":row.get("direction"),
                "Mecanismo":row.get("mechanism"),
                "Estado":row.get("truth_kind"),
            }
            for row in channels if isinstance(row, Mapping)
        ], width="stretch", hide_index=True)
    invalidators = list(scenario.get("invalidators") or [])
    if invalidators:
        with st.expander("O que pode invalidar ou inverter esse cenário"):
            for item in invalidators:
                st.markdown(f"- {item}")
    st.warning(
        "Antes de usar este cenário em leitura real, o AION precisa confirmar o dado divulgado, "
        "consenso, revisões, componentes internos, preço e contexto atual."
    )


def _render_studio(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 🎬 AION Studio")
    _render_persona_capabilities("video", {
        "script": True,
        "storyboard": True,
        "scenes": True,
        "narration": False,
        "captions": False,
        "thumbnail": False,
        "formats": True,
        "approval_queue": True,
    })
    st.write(
        "Pipeline persistente para **ideia → roteiro → imagem/capa → vídeo → revisão → aprovação → publicação**."
    )
    _context_voice(
        "Studio",
        (
            "Bem-vindo ao AION Studio. Aqui organizamos ideias, roteiros, imagens, vídeos, legendas e capas. "
            "Todo conteúdo fica registrado no Checkpoint Mestre e publicação externa exige aprovação."
        ),
        key="aion_studio_voice",
    )

    studio = checkpoint.get("studio") if isinstance(checkpoint.get("studio"), Mapping) else {}
    projects = list(studio.get("projects", []) or [])
    summary = studio_summary(projects)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Projetos", summary["total"])
    c2.metric("Em revisão", summary["in_review"])
    c3.metric("Aprovados", summary["approved"])
    c4.metric("Publicados confirmados", summary["published"])

    publish = bool(flags.get("social_publish", False))
    st.warning(
        "Publicação automática está "
        + ("HABILITADA POR FLAG, mas ainda depende do Guardian e de integração real." if publish else "DESLIGADA por feature flag.")
    )
    media = provider_readiness()
    with st.expander("Providers de mídia, clipagem e voz"):
        st.dataframe([
            {"Capacidade": name, "Estado": item["state"]}
            for name, item in media["providers"].items()
        ], width="stretch", hide_index=True)
        st.caption(
            "Sem credencial/provider: NÃO CONFIGURADO. Voz de Mikael também exige consentimento e amostra autorizada. "
            "Nenhum conteúdo é baixado, renderizado ou publicado nesta tela."
        )

    st.markdown("#### Novo projeto de conteúdo")
    with st.form("aion_studio_new_project", clear_on_submit=True):
        title = st.text_input("Título / ideia")
        objective = st.text_area("Objetivo do conteúdo", max_chars=1200)
        platforms = st.multiselect(
            "Canais",
            list(STUDIO_PLATFORMS),
            default=["Instagram","TikTok"],
        )
        cfmt,cdur = st.columns(2)
        ratio = cfmt.selectbox("Formato", list(STUDIO_FORMATS), index=0)
        duration = cdur.number_input("Duração alvo (segundos)", min_value=10, max_value=600, value=60, step=5)
        audience = st.text_input("Público")
        cta = st.text_input("CTA")
        create_project = st.form_submit_button("Criar projeto no Studio", type="primary")
    if create_project:
        try:
            project = new_content_project(
                title,
                objective=objective,
                platforms=platforms,
                format_ratio=ratio,
                duration_seconds=duration,
                audience=audience,
                cta=cta,
                source=str(access.get("username") or "ADMIN"),
            )
            projects = upsert_project(projects, project)
            updated = update_studio_checkpoint(checkpoint, projects=projects, dirty=True)
            updated = _record_working_event(
                updated,
                "studio_project_created",
                f"Projeto de conteúdo criado: {project['title']}",
                evidence={
                    "content_id":project["content_id"],
                    "platforms":",".join(project["platforms"]),
                    "status":project["status"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Projeto salvo na memória de trabalho do AION Studio.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar o projeto: {type(exc).__name__}")

    if projects:
        rows=[{
            "ID":p.get("content_id"),
            "Status":p.get("status"),
            "Título":p.get("title"),
            "Canais":", ".join(p.get("platforms",[])),
            "Formato":p.get("format_ratio"),
            "Duração":p.get("duration_seconds"),
            "Aprovado":bool((p.get("approval") or {}).get("approved",False)),
            "Publicado":bool((p.get("publication") or {}).get("executed",False)),
        } for p in projects]
        st.dataframe(rows, width="stretch", hide_index=True)
        selected_id=st.selectbox(
            "Projeto selecionado",
            [str(p.get("content_id")) for p in projects],
            key="aion_studio_selected_project",
        )
        selected=next((p for p in projects if str(p.get("content_id"))==selected_id),None)
        if isinstance(selected, Mapping):
            blueprint=script_blueprint(selected)
            pipeline=content_job(
                selected.get("title") or "Conteúdo sem título",
                source_reference=(selected.get("research") or {}).get("source","")
                if isinstance(selected.get("research"),Mapping) else "",
                rights_state="UNKNOWN",
                formats=list(selected.get("platforms") or []),
            )
            with st.expander("Roteiro-base / storyboard", expanded=True):
                st.write(f"**{blueprint['title']} · {blueprint['total_seconds']}s**")
                for segment in blueprint["segments"]:
                    st.markdown(
                        f"- **{segment['name']} ({segment['seconds']}s):** {segment['instruction']}"
                    )
                st.caption("Roteiro-base determinístico; não afirma resultados nem recursos inexistentes.")
            with st.expander("Clipagem, formatos e fila de aprovação"):
                st.dataframe(pipeline["variants"], width="stretch", hide_index=True)
                st.warning(
                    "Direitos de uso: REVISÃO OBRIGATÓRIA. Transcrição, cortes, legendas, thumbnail "
                    "e metadados estão preparados como etapas, mas nenhum provider foi executado."
                )

            p1,p2=st.columns(2)
            if p1.button("✅ Aprovar conteúdo", key="aion_studio_approve"):
                try:
                    approved=approve_project(selected,access)
                    projects=upsert_project(projects,approved)
                    updated=update_studio_checkpoint(checkpoint,projects=projects,dirty=True)
                    updated=_record_working_event(
                        updated,
                        "studio_project_approved",
                        f"Conteúdo aprovado: {approved['content_id']}",
                        evidence={"content_id":approved["content_id"]},
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight=publication_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            if preflight["allowed"]:
                st.success("Pré-requisitos de publicação disponíveis; execução ainda não ocorre nesta tela.")
            else:
                st.caption(f"Publicação: BLOQUEADA · {preflight['reason']}")
    else:
        st.info("Nenhum projeto de conteúdo registrado no Studio.")



def _render_business_guided_training() -> None:
    """Session-only training lab. Uses fictional fixtures and executes nothing."""
    st.markdown("#### 🎓 Treinamento Guiado AION Business")
    st.caption(
        "Ambiente de prática com empresas fictícias. Nenhum dado real, contato, cobrança, "
        "publicação ou runtime é usado aqui."
    )
    catalog = business_scenario_catalog()
    labels = {row["label"]: row["id"] for row in catalog}
    selected_label = st.selectbox(
        "Empresa fictícia para treinar",
        list(labels),
        key="aion_business_training_scenario",
    )
    scenario_id = labels[selected_label]
    session = business_training_session(scenario_id, step=1)
    scenario = session["scenario"]

    st.info(
        f"**{scenario['company']} · {scenario['segment']}**\n\n{scenario['situation']}"
    )

    stages = (
        "1 · Diagnóstico",
        "2 · Radar & Pacote",
        "3 · Entrega",
        "4 · Objeções",
        "5 · Venda simulada",
        "6 · Minha preparação",
    )
    selected_stage = st.selectbox(
        "Etapa do treinamento",
        stages,
        key="aion_business_training_stage",
        help="Carrega uma etapa por vez para manter a navegação leve no celular.",
    )

    if selected_stage == stages[0]:
        brief = business_diagnostic_brief(scenario_id)
        st.markdown("**Como explicar o problema antes da tecnologia**")
        st.write(brief["summary"])
        st.markdown("**Gargalos do exercício**")
        for gap in brief["priority_gaps"]:
            st.markdown(f"- {gap}")
        st.markdown("**Perguntas que precisam ser feitas numa empresa real**")
        for question in brief["questions_to_confirm"]:
            st.markdown(f"- {question}")
        st.caption("Estado deste exercício: FICTIONAL_FIXTURE. Nada aqui é dado de cliente.")

    elif selected_stage == stages[1]:
        fit = business_package_fit(scenario_id)
        fixture = scenario["fixture"]
        r1,r2,r3,r4 = st.columns(4)
        r1.metric("Leads abertos", fixture["leads_open"])
        r2.metric("Resposta média", f"{fixture['avg_response_hours']:.1f}h")
        r3.metric("Orçamentos parados", fixture["abandoned_quotes"])
        r4.metric("Clientes retornando", f"{fixture['returning_customers_pct']:.0f}%")
        st.caption("Dados fictícios usados apenas para aprender a ler o Radar.")
        st.success(f"**Pacote de treino:** {fit['package_label']}")
        for component in fit["components"]:
            st.markdown(f"- {component}")
        st.warning(
            "Em empresa real o pacote e o preço só são fechados depois do diagnóstico. "
            "Este encaixe é didático e não promete resultado."
        )

    elif selected_stage == stages[2]:
        delivery = business_delivery_walkthrough(scenario_id)
        st.markdown("**O que o cliente recebe**")
        for item in delivery["what_client_receives"]:
            st.markdown(f"- {item}")
        st.markdown("**O que o cliente deve enxergar no painel**")
        for item in delivery["what_client_sees"]:
            st.markdown(f"- {item}")
        st.markdown("**O que entra na manutenção mensal**")
        for item in delivery["maintenance_covers"]:
            st.markdown(f"- {item}")
        st.info(
            "Modelo comercial didático: implantação + manutenção mensal. "
            "Preço não está definido automaticamente."
        )

    elif selected_stage == stages[3]:
        objections = business_objection_catalog()
        qmap = {row["question"]: row["id"] for row in objections}
        question = st.selectbox(
            "Escolha uma pergunta comum do cliente",
            list(qmap),
            key="aion_business_training_objection",
        )
        answer = business_objection_answer(qmap[question])
        st.markdown("**Resposta segura para praticar**")
        st.write(answer["answer"])
        st.caption(
            "Regra: se surgir uma dúvida que não sabemos responder, não inventar. "
            "Registrar, conferir o escopo/evidência e responder depois."
        )

    elif selected_stage == stages[4]:
        conversation = business_simulated_sales_conversation(scenario_id)
        st.markdown("**Simulação de conversa**")
        for row in conversation:
            who = "Você / ADMIN" if row["speaker"] == "ADMIN" else "Cliente fictício"
            st.markdown(f"**{who}:** {row['text']}")
        st.caption(
            "Treino somente. Nenhuma mensagem é enviada e nenhuma proposta comercial é criada."
        )

    else:
        st.markdown("**Checklist antes de você divulgar ou conversar com cliente real**")
        checks = {}
        labels_checks = (
            ("explained_problem_before_technology", "Consigo explicar o problema antes de falar de IA."),
            ("separated_fact_from_assumption", "Separo fato confirmado de hipótese."),
            ("explained_package_scope", "Sei explicar o que entra e o que não entra no pacote."),
            ("explained_installation_and_maintenance", "Sei explicar implantação + manutenção mensal."),
            ("avoided_financial_guarantee", "Sei explicar que não existe garantia de venda/lucro."),
            ("explained_client_portal", "Consigo mostrar o Portal/Radar em linguagem simples."),
            ("asked_for_next_step", "Sei conduzir para diagnóstico/proposta como próximo passo."),
        )
        for key, label in labels_checks:
            checks[key] = st.checkbox(
                label,
                key=f"aion_business_training_check_{key}",
            )
        score = business_training_scorecard(**checks)
        st.progress(int(round(score["progress_pct"])))
        st.write(
            f"Preparação neste checklist: **{score['completed']}/{score['total']} "
            f"({score['progress_pct']:.0f}%)**"
        )
        if score["training_complete"]:
            st.success(
                "Checklist concluído nesta sessão. Continue praticando com outros cenários antes "
                "de transformar o treino em atendimento real."
            )
        else:
            st.info("Complete os itens restantes e pratique novamente.")
        st.caption(
            "Concluir o checklist não autoriza venda automática, runtime ou ação externa."
        )



def _render_business_diagnostic_proposal_simulator() -> None:
    """Session-only diagnostic/proposal simulator. Draft-only, no external action."""
    st.markdown("#### 🧭 Simulador de Diagnóstico + Proposta")
    st.caption(
        "Use dados fictícios para praticar o processo completo. Nada é enviado, cobrado, "
        "assinado ou publicado. Preços permanecem A DEFINIR até existir escopo real validado."
    )

    with st.form("aion_business_diagnostic_simulator_form", clear_on_submit=False):
        company_name = st.text_input(
            "Empresa fictícia",
            value="Clínica Horizonte Demo",
            key="aion_business_sim_company",
        )
        segment = st.text_input(
            "Segmento",
            value="Clínica",
            key="aion_business_sim_segment",
        )
        channels = st.multiselect(
            "Canais usados",
            ["WhatsApp", "Instagram", "Facebook", "Site", "Google", "Telefone", "E-mail"],
            default=["WhatsApp", "Instagram"],
            key="aion_business_sim_channels",
        )
        weekly_leads = st.number_input(
            "Leads por semana",
            min_value=0,
            max_value=100000,
            value=120,
            step=1,
            key="aion_business_sim_weekly_leads",
        )
        avg_response_hours = st.number_input(
            "Tempo médio de resposta (horas)",
            min_value=0.0,
            max_value=720.0,
            value=4.5,
            step=0.5,
            key="aion_business_sim_response",
        )
        abandoned_quotes = st.number_input(
            "Orçamentos/leads abandonados por mês",
            min_value=0,
            max_value=100000,
            value=18,
            step=1,
            key="aion_business_sim_abandoned",
        )
        returning_pct = st.number_input(
            "Clientes retornando (%)",
            min_value=0.0,
            max_value=100.0,
            value=14.0,
            step=1.0,
            key="aion_business_sim_returning",
        )
        content_posts = st.number_input(
            "Publicações de conteúdo por mês",
            min_value=0,
            max_value=1000,
            value=2,
            step=1,
            key="aion_business_sim_posts",
        )
        followup = st.radio(
            "Existe processo de follow-up?",
            ["Não", "Sim"],
            horizontal=True,
            key="aion_business_sim_followup",
        )
        crm = st.radio(
            "Existe CRM/pipeline organizado?",
            ["Não", "Sim"],
            horizontal=True,
            key="aion_business_sim_crm",
        )
        sla = st.radio(
            "Existe SLA/tempo-alvo de atendimento?",
            ["Não", "Sim"],
            horizontal=True,
            key="aion_business_sim_sla",
        )
        conversion = st.radio(
            "A empresa mede conversão?",
            ["Não", "Sim"],
            horizontal=True,
            key="aion_business_sim_conversion",
        )
        goals_text = st.text_input(
            "Objetivos do exercício",
            value="responder mais rápido; recuperar leads; organizar atendimento",
            key="aion_business_sim_goals",
        )
        notes = st.text_area(
            "Observações fictícias",
            value="Treino interno do administrador.",
            key="aion_business_sim_notes",
        )
        generate = st.form_submit_button("Gerar diagnóstico e rascunho")

    if generate:
        goals = [item.strip() for item in goals_text.split(";") if item.strip()]
        intake = {
            "company_name": company_name,
            "segment": segment,
            "channels": channels,
            "goals": goals,
            "weekly_leads": weekly_leads,
            "avg_response_hours": avg_response_hours,
            "abandoned_quotes_monthly": abandoned_quotes,
            "returning_customers_pct": returning_pct,
            "content_posts_monthly": content_posts,
            "has_followup_process": followup == "Sim",
            "has_crm": crm == "Sim",
            "has_sla": sla == "Sim",
            "tracks_conversion": conversion == "Sim",
            "notes": notes,
        }
        diagnostic = business_diagnose_company(intake)
        fit = business_recommend_package(diagnostic)
        radar = business_client_radar(diagnostic)
        proposal = business_build_proposal_draft(diagnostic, fit)
        st.session_state["aion_business_simulator_result"] = {
            "diagnostic": diagnostic,
            "fit": fit,
            "radar": radar,
            "proposal": proposal,
            "proposal_text": business_proposal_text(proposal),
        }

    result = st.session_state.get("aion_business_simulator_result")
    if not isinstance(result, Mapping):
        st.info("Preencha o exercício e toque em **Gerar diagnóstico e rascunho**.")
        return

    diagnostic = result.get("diagnostic") if isinstance(result.get("diagnostic"), Mapping) else {}
    fit = result.get("fit") if isinstance(result.get("fit"), Mapping) else {}
    radar = result.get("radar") if isinstance(result.get("radar"), Mapping) else {}
    proposal = result.get("proposal") if isinstance(result.get("proposal"), Mapping) else {}

    stages = (
        "1 · Diagnóstico",
        "2 · Radar",
        "3 · Pacote",
        "4 · Proposta",
    )
    selected = st.selectbox(
        "Resultado para visualizar",
        stages,
        key="aion_business_simulator_result_stage",
        help="Uma etapa por vez para manter a experiência leve no celular.",
    )

    if selected == stages[0]:
        st.markdown("**Diagnóstico preliminar do exercício**")
        st.caption(
            f"Fonte: {diagnostic.get('truth_state') or 'UNKNOWN'} · "
            "empresa real não verificada · sem execução externa."
        )
        issues = diagnostic.get("issues") if isinstance(diagnostic.get("issues"), list) else []
        if not issues:
            st.success("Nenhum alerta básico foi acionado pelos dados deste exercício.")
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            st.markdown(
                f"**{issue.get('pillar_label')} · {issue.get('severity')} — {issue.get('title')}**"
            )
            st.caption(str(issue.get("evidence") or ""))
            st.write(str(issue.get("recommendation") or ""))

    elif selected == stages[1]:
        st.markdown("**Radar do Negócio · exercício fictício**")
        cards = radar.get("cards") if isinstance(radar.get("cards"), list) else []
        cols = st.columns(4)
        for index, card in enumerate(cards[:4]):
            if not isinstance(card, Mapping):
                continue
            cols[index].metric(
                str(card.get("label") or ""),
                f"{int(card.get('health_score') or 0)}/100",
                str(card.get("state") or ""),
            )
        st.markdown("**Próximas ações sugeridas para revisão**")
        actions = radar.get("next_actions") if isinstance(radar.get("next_actions"), list) else []
        for item in actions:
            if isinstance(item, Mapping):
                st.markdown(
                    f"- **{item.get('severity')} · {item.get('title')}** — "
                    f"{item.get('recommendation')}"
                )
        st.caption("Radar didático; não representa dados reais nem garantia de resultado.")

    elif selected == stages[2]:
        st.success(f"**Pacote preliminar:** {fit.get('package_label') or 'A DEFINIR'}")
        st.write(str(fit.get("reason") or ""))
        st.markdown("**Entregas preliminares**")
        for item in list(fit.get("deliverables") or []):
            st.markdown(f"- {item}")
        st.info(
            "Preço de implantação e mensalidade continuam A DEFINIR. "
            "Em cliente real, diagnóstico + escopo + integrações + volume vêm antes do preço."
        )

    else:
        p = proposal.get("proposal") if isinstance(proposal.get("proposal"), Mapping) else {}
        if proposal.get("state") != "DRAFT_READY":
            st.warning("O diagnóstico ainda não tem dados suficientes para montar a proposta.")
            return
        st.markdown(f"**{p.get('title')}**")
        st.caption("RASCUNHO INTERNO · NÃO ENVIADO · NÃO ASSINADO · SEM COBRANÇA")
        st.markdown("**Objetivo**")
        st.write(str(p.get("objective") or ""))
        st.markdown("**Entregas previstas**")
        for item in list(p.get("deliverables") or []):
            st.markdown(f"- {item}")
        st.markdown("**Implantação**")
        for item in list(p.get("implementation_phases") or []):
            st.markdown(f"- {item}")
        st.markdown("**Manutenção mensal**")
        for item in list(p.get("monthly_maintenance") or []):
            st.markdown(f"- {item}")
        terms = p.get("commercial_terms") if isinstance(p.get("commercial_terms"), Mapping) else {}
        st.markdown("**Condições comerciais**")
        st.write(f"Implantação: **{terms.get('implementation_price') or 'A DEFINIR'}**")
        st.write(f"Mensalidade: **{terms.get('monthly_maintenance') or 'A DEFINIR'}**")
        st.markdown("**Próximo passo**")
        st.write(str(p.get("next_step") or ""))
        with st.expander("Ver texto completo do rascunho", expanded=False):
            st.code(str(result.get("proposal_text") or ""), language=None)
        st.caption(
            "Este simulador só produz rascunho. Não envia proposta, não assina contrato, "
            "não cobra e não ativa runtime."
        )



def _render_business_client_portal_demo() -> None:
    """Render the future client-facing experience from session-only demo data."""
    st.markdown("#### 🖥️ Portal Executivo do Cliente · Demo")
    st.caption(
        "Esta é a visão que o cliente deverá receber: simples, objetiva e sem complexidade técnica. "
        "Usa somente o último exercício fictício do simulador."
    )
    result = st.session_state.get("aion_business_simulator_result")
    if not isinstance(result, Mapping):
        st.info(
            "Primeiro gere um exercício no **Simulador de Diagnóstico + Proposta**. "
            "Depois o mesmo diagnóstico aparece aqui na visão do cliente."
        )
        return

    diagnostic = result.get("diagnostic") if isinstance(result.get("diagnostic"), Mapping) else {}
    fit = result.get("fit") if isinstance(result.get("fit"), Mapping) else {}
    radar = result.get("radar") if isinstance(result.get("radar"), Mapping) else {}
    proposal = result.get("proposal") if isinstance(result.get("proposal"), Mapping) else {}
    portal = business_build_client_portal_demo(diagnostic, radar, fit, proposal)
    attention = business_portal_attention_summary(portal)

    st.markdown(f"### {portal.get('company') or 'Empresa Demo'}")
    st.caption(
        f"{portal.get('segment') or 'Segmento Demo'} · DEMO ONLY · RUNTIME OFF · "
        "SEM AÇÃO EXTERNA"
    )
    st.write(str(portal.get("headline") or ""))
    st.markdown(f"**{portal.get('tagline') or ''}**")

    section = st.selectbox(
        "Área do Portal",
        list(BUSINESS_CLIENT_PORTAL_SECTIONS),
        key="aion_business_client_portal_section",
        help="O cliente navega por uma área de cada vez, inclusive no celular.",
    )
    selected = business_portal_section(portal, section)
    payload = selected.get("payload")

    if section == "VISÃO GERAL":
        overview = payload if isinstance(payload, Mapping) else {}
        package = overview.get("package") if isinstance(overview.get("package"), Mapping) else {}
        st.info(str(attention.get("headline") or ""))
        a1,a2,a3 = st.columns(3)
        a1.metric("Prioridades", int(attention.get("pending_actions") or 0))
        a2.metric("Críticas", int(attention.get("critical_count") or 0))
        a3.metric("Importantes", int(attention.get("high_count") or 0))
        st.markdown(f"**Pacote do exercício:** {package.get('label') or 'A DEFINIR'}")
        st.caption("Preço e escopo final continuam pendentes de validação real.")

    elif section == "RADAR":
        row = payload if isinstance(payload, Mapping) else {}
        cards = row.get("cards") if isinstance(row.get("cards"), list) else []
        cols = st.columns(4)
        for index, card in enumerate(cards[:4]):
            if isinstance(card, Mapping):
                cols[index].metric(
                    str(card.get("label") or ""),
                    f"{int(card.get('health_score') or 0)}/100",
                    str(card.get("state") or ""),
                )
        st.caption("Fonte: DEMO_USER_INPUT. Nenhum dado real de empresa foi conectado.")

    elif section == "PLANO DE AÇÃO":
        items = payload if isinstance(payload, list) else []
        if not items:
            st.success("Nenhuma ação básica apareceu no exercício.")
        for item in items:
            if isinstance(item, Mapping):
                st.markdown(
                    f"**{item.get('severity')} · {item.get('title')}**  \n"
                    f"{item.get('recommendation')}  \n"
                    f"_Estado: {item.get('status')}_"
                )

    elif section == "RESULTADOS":
        row = payload if isinstance(payload, Mapping) else {}
        st.info(str(row.get("message") or ""))
        st.metric("Resultados reais disponíveis", 0)
        st.caption(
            "O AION não preenche números de resultado sem fonte confiável e período de medição."
        )

    elif section == "SUPORTE":
        row = payload if isinstance(payload, Mapping) else {}
        s1,s2,s3 = st.columns(3)
        s1.metric("Chamados abertos", int(row.get("open_tickets") or 0))
        s2.metric("Incidentes críticos", int(row.get("critical_incidents") or 0))
        s3.metric("SLA", str(row.get("sla_state") or "A DEFINIR"))
        st.write(f"Canal de suporte: **{row.get('contact_channel') or 'A DEFINIR'}**")
        st.caption("Valores demonstrativos; SLA real é definido no contrato/escopo.")

    else:
        items = payload if isinstance(payload, list) else []
        st.markdown("**Histórico visível ao cliente**")
        for item in items:
            if isinstance(item, Mapping):
                st.markdown(
                    f"- **{item.get('label') or item.get('event')}** · "
                    f"{item.get('timestamp') or 'DEMO'}"
                )

    with st.expander("O que fica escondido do cliente", expanded=False):
        st.write(
            "Filas, roteamento de especialistas, validações, auditoria, segurança, fingerprints, "
            "gates de runtime e outras camadas técnicas ficam por dentro do AION. "
            "O cliente recebe contexto, prioridade, resultado verificável e próximo passo."
        )
    st.caption(
        "Portal de demonstração. Sem cliente real conectado, sem cobrança, sem publicação, "
        "sem mensagem automática e com runtime OFF."
    )



def _render_business_onboarding_demo() -> None:
    """Teach the post-sale onboarding path using session-only demo data."""
    st.markdown("#### 🧩 Onboarding + Implantação · Demo")
    st.caption(
        "Mostra como o cliente sai da proposta e chega à implantação controlada. "
        "Sem credenciais reais, sem conexão externa e sem runtime."
    )
    simulator = st.session_state.get("aion_business_simulator_result")
    if not isinstance(simulator, Mapping):
        st.info(
            "Gere primeiro um exercício no simulador. O onboarding usa o pacote e o objetivo "
            "da mesma empresa fictícia."
        )
        return

    diagnostic = simulator.get("diagnostic") if isinstance(simulator.get("diagnostic"), Mapping) else {}
    fit = simulator.get("fit") if isinstance(simulator.get("fit"), Mapping) else {}
    intake_source = diagnostic.get("intake") if isinstance(diagnostic.get("intake"), Mapping) else {}
    company = str(intake_source.get("company_name") or "Empresa Demo")
    package = str(fit.get("package_label") or "A DEFINIR")

    with st.form("aion_business_onboarding_demo_form", clear_on_submit=False):
        owner = st.text_input(
            "Responsável fictício da empresa",
            value="Responsável Demo",
            key="aion_business_onboarding_owner",
        )
        goal = st.text_area(
            "Objetivo do onboarding",
            value=str(intake_source.get("notes") or "Implantar o pacote com escopo e métricas claras."),
            key="aion_business_onboarding_goal",
        )
        access_requested = st.multiselect(
            "Integrações que o exercício diz precisar",
            list(BUSINESS_ONBOARDING_ACCESS_CATEGORIES),
            default=[],
            key="aion_business_onboarding_access",
        )
        create_plan = st.form_submit_button("Montar plano de implantação")

    if create_plan:
        intake = business_onboarding_intake(
            company_name=company,
            package_label=package,
            business_owner=owner,
            business_goal=goal,
            requested_channels=list(intake_source.get("channels") or []),
            requested_integrations=access_requested,
        )
        access_flags = {name: name in access_requested for name in BUSINESS_ONBOARDING_ACCESS_CATEGORIES}
        access = business_minimum_access_plan(intake, access_flags)
        plan = business_build_implementation_plan(intake, access)
        st.session_state["aion_business_onboarding_demo_result"] = {
            "intake": intake,
            "access": access,
            "plan": plan,
        }

    result = st.session_state.get("aion_business_onboarding_demo_result")
    if not isinstance(result, Mapping):
        st.info("Monte o plano para visualizar as etapas.")
        return

    intake = result.get("intake") if isinstance(result.get("intake"), Mapping) else {}
    access = result.get("access") if isinstance(result.get("access"), Mapping) else {}
    plan = result.get("plan") if isinstance(result.get("plan"), Mapping) else {}

    stage = st.selectbox(
        "Etapa do onboarding",
        (
            "1 · Escopo",
            "2 · Dados & acessos",
            "3 · Integrações",
            "4 · Sandbox",
            "5 · Validação",
            "6 · Entrega assistida",
            "7 · Status",
        ),
        key="aion_business_onboarding_stage",
        help="Uma etapa por vez para facilitar o uso pelo celular.",
    )

    if stage == "1 · Escopo":
        st.markdown(f"**Empresa:** {intake.get('company_name') or 'Demo'}")
        st.markdown(f"**Pacote:** {intake.get('package_label') or 'A DEFINIR'}")
        st.markdown(f"**Responsável:** {intake.get('business_owner') or 'A DEFINIR'}")
        st.markdown("**Objetivo**")
        st.write(str(intake.get("business_goal") or ""))
        st.caption("Nenhum preço, credencial ou ação externa é definido nesta etapa.")

    elif stage == "2 · Dados & acessos":
        st.markdown("**Princípio: acesso mínimo necessário**")
        for item in list(access.get("items") or []):
            if isinstance(item, Mapping) and item.get("needed"):
                st.markdown(
                    f"- **{item.get('category')}** — {item.get('access_level')} · "
                    "aprovação necessária"
                )
        st.caption("Este demo não coleta nem armazena valor de senha/token/chave.")

    elif stage == "3 · Integrações":
        requested = list(intake.get("requested_integrations") or [])
        if requested:
            for item in requested:
                st.markdown(f"- {item}: **PLANEJADA PARA SANDBOX**")
        else:
            st.info("Nenhuma integração selecionada neste exercício.")
        st.caption("Conexão real não é feita neste demo.")

    elif stage == "4 · Sandbox":
        st.success("Primeiro ambiente: **SANDBOX / ISOLADO**")
        st.write(
            "Fluxos são montados e testados antes de qualquer futura ativação operacional."
        )
        st.caption("Runtime produtivo continua OFF.")

    elif stage == "5 · Validação":
        plan_body = plan.get("plan") if isinstance(plan.get("plan"), Mapping) else {}
        for item in list(plan_body.get("validation_checklist") or []):
            st.markdown(f"- [ ] {item}")
        st.caption("Checklist visual do demo; não registra aprovação real.")

    elif stage == "6 · Entrega assistida":
        st.write(
            "A entrega assistida só prepara a futura transição. Ela não liga runtime, "
            "não envia mensagens e não autoriza cobrança."
        )
        st.warning(
            "Qualquer go-live real exige gate separado, evidência e aprovação humana específica."
        )

    else:
        demo_completed = st.multiselect(
            "Marque as fases concluídas somente neste exercício",
            list(BUSINESS_ONBOARDING_PHASES),
            default=[],
            key="aion_business_onboarding_completed",
        )
        status = business_onboarding_status(plan, demo_completed)
        st.progress(int(round(status.get("progress_pct") or 0)))
        st.write(
            f"Progresso do exercício: **{status.get('completed_count')}/{status.get('total_phases')} "
            f"({status.get('progress_pct'):.0f}%)**"
        )
        packet = business_go_live_review_packet(plan, status)
        if packet.get("state") == "LIVE_REVIEW_REQUIRED":
            st.success("Demo concluído: pode ser preparado um pedido separado de revisão de go-live.")
        else:
            st.info("Ainda existem fases do exercício a concluir.")
        st.caption(
            "Mesmo com 100% no demo: runtime não é autorizado automaticamente e permanece OFF."
        )



def _render_business_customer_success_demo() -> None:
    """Session-only customer success, SLA, renewal and expansion demo."""
    st.markdown("#### 🤝 Customer Success + SLA · Demo")
    st.caption(
        "Treina o acompanhamento depois da implantação: saúde do cliente, suporte, adoção, "
        "renovação e oportunidades de expansão. Dados totalmente fictícios."
    )
    simulator = st.session_state.get("aion_business_simulator_result")
    diagnostic = (
        simulator.get("diagnostic")
        if isinstance(simulator, Mapping) and isinstance(simulator.get("diagnostic"), Mapping)
        else {}
    )
    intake = diagnostic.get("intake") if isinstance(diagnostic.get("intake"), Mapping) else {}
    company = str(intake.get("company_name") or "Empresa Demo")

    with st.form("aion_business_customer_success_demo_form", clear_on_submit=False):
        usage = st.slider(
            "Uso do serviço (%)",
            min_value=0,
            max_value=100,
            value=72,
            step=1,
            key="aion_business_cs_usage",
        )
        goals = st.slider(
            "Progresso dos objetivos (%)",
            min_value=0,
            max_value=100,
            value=65,
            step=1,
            key="aion_business_cs_goals",
        )
        satisfaction = st.slider(
            "Satisfação fictícia (1–5)",
            min_value=1.0,
            max_value=5.0,
            value=4.0,
            step=0.5,
            key="aion_business_cs_satisfaction",
        )
        inactivity = st.number_input(
            "Dias desde última atividade",
            min_value=0,
            max_value=3650,
            value=3,
            step=1,
            key="aion_business_cs_inactivity",
        )
        open_tickets = st.number_input(
            "Chamados abertos",
            min_value=0,
            max_value=10000,
            value=1,
            step=1,
            key="aion_business_cs_tickets",
        )
        critical_incidents = st.number_input(
            "Incidentes críticos",
            min_value=0,
            max_value=1000,
            value=0,
            step=1,
            key="aion_business_cs_incidents",
        )
        onboarding_complete = st.checkbox(
            "Onboarding concluído",
            value=True,
            key="aion_business_cs_onboarding_complete",
        )
        monthly_review = st.checkbox(
            "Revisão mensal concluída",
            value=True,
            key="aion_business_cs_review_done",
        )
        renewal_days = st.number_input(
            "Dias até renovação fictícia",
            min_value=0,
            max_value=3650,
            value=45,
            step=1,
            key="aion_business_cs_renewal_days",
        )
        payment_state = st.selectbox(
            "Estado comercial fictício",
            ["CURRENT", "UNKNOWN", "OVERDUE_DEMO"],
            key="aion_business_cs_payment_state",
        )
        evaluate = st.form_submit_button("Avaliar saúde do cliente demo")

    if evaluate:
        signals = {
            "company_name": company,
            "usage_pct": usage,
            "goals_progress_pct": goals,
            "satisfaction_score": satisfaction,
            "days_since_last_activity": inactivity,
            "open_tickets": open_tickets,
            "critical_incidents": critical_incidents,
            "onboarding_complete": onboarding_complete,
            "monthly_review_done": monthly_review,
            "payment_state": payment_state,
            "renewal_days": renewal_days,
        }
        health = business_customer_health(signals)
        success = business_success_plan(health)
        expansion = business_expansion_opportunity(health)
        renewal = business_renewal_readiness(health)
        ticket = business_sla_ticket(
            title="Chamado fictício de acompanhamento",
            priority="P3" if critical_incidents == 0 else "P1",
            age_hours=2,
        )
        st.session_state["aion_business_customer_success_demo_result"] = {
            "health": health,
            "success": success,
            "expansion": expansion,
            "renewal": renewal,
            "ticket": ticket,
        }

    result = st.session_state.get("aion_business_customer_success_demo_result")
    if not isinstance(result, Mapping):
        st.info("Avalie o cliente fictício para abrir o painel de Customer Success.")
        return

    stage = st.selectbox(
        "Visão de Customer Success",
        (
            "1 · Saúde",
            "2 · SLA & Suporte",
            "3 · Plano de Sucesso",
            "4 · Renovação & Expansão",
        ),
        key="aion_business_customer_success_stage",
        help="Uma visão por vez para manter o uso simples no celular.",
    )
    health = result.get("health") if isinstance(result.get("health"), Mapping) else {}
    if stage == "1 · Saúde":
        h1,h2,h3 = st.columns(3)
        h1.metric("Health Score", f"{int(health.get('health_score') or 0)}/100")
        h2.metric("Estado", str(health.get("state") or "UNKNOWN"))
        h3.metric("Risco de churn", "SIM" if health.get("churn_risk") else "NÃO")
        flags = health.get("flags") if isinstance(health.get("flags"), list) else []
        if not flags:
            st.success("Nenhum alerta básico foi acionado neste exercício.")
        for flag in flags:
            if isinstance(flag, Mapping):
                st.markdown(
                    f"- **{flag.get('severity')} · {flag.get('code')}** — {flag.get('message')}"
                )
        st.caption("Health Score didático, calculado somente pelos dados fictícios desta sessão.")

    elif stage == "2 · SLA & Suporte":
        ticket = result.get("ticket") if isinstance(result.get("ticket"), Mapping) else {}
        s1,s2,s3 = st.columns(3)
        s1.metric("Prioridade", str(ticket.get("priority") or "P3"))
        s2.metric("Meta", f"{int(ticket.get('target_hours') or 0)}h")
        s3.metric("SLA", str(ticket.get("sla_state") or "UNKNOWN"))
        st.write(str(ticket.get("title") or ""))
        st.caption(
            "Chamado apenas demonstrativo. Não foi enviado a suporte e não produz escrita externa."
        )

    elif stage == "3 · Plano de Sucesso":
        success = result.get("success") if isinstance(result.get("success"), Mapping) else {}
        st.markdown("**Próximas ações para revisão humana**")
        for item in list(success.get("actions") or []):
            if isinstance(item, Mapping):
                st.markdown(f"- {item.get('action')}  \n  _Fonte: {item.get('source')}_")
        st.caption(
            "O plano organiza o acompanhamento; não envia contato nem altera a conta do cliente."
        )

    else:
        renewal = result.get("renewal") if isinstance(result.get("renewal"), Mapping) else {}
        expansion = result.get("expansion") if isinstance(result.get("expansion"), Mapping) else {}
        st.markdown("**Renovação**")
        st.write(
            f"Estado: **{renewal.get('state') or 'UNKNOWN'}** · "
            f"{renewal.get('recommended_focus') or ''}"
        )
        st.markdown("**Expansão / Upsell**")
        if expansion.get("state") == "EXPANSION_REVIEW_AVAILABLE":
            st.success(str(expansion.get("reason") or "Pode avaliar expansão."))
        else:
            st.info(str(expansion.get("reason") or "Sem expansão agora."))
        st.caption(
            "Renovação e upsell nunca são automáticos. Saúde e necessidade real vêm antes da venda."
        )



def _render_business_client_finance_demo() -> None:
    """Session-only client economics and capacity demo. Never moves money."""
    st.markdown("#### 💰 Central Financeira por Cliente · Demo")
    st.caption(
        "Separa receita, custo, margem e capacidade por cliente. "
        "Dados fictícios; não gera cobrança nem movimenta dinheiro."
    )
    simulator = st.session_state.get("aion_business_simulator_result")
    diagnostic = (
        simulator.get("diagnostic")
        if isinstance(simulator, Mapping) and isinstance(simulator.get("diagnostic"), Mapping)
        else {}
    )
    fit = (
        simulator.get("fit")
        if isinstance(simulator, Mapping) and isinstance(simulator.get("fit"), Mapping)
        else {}
    )
    intake = diagnostic.get("intake") if isinstance(diagnostic.get("intake"), Mapping) else {}
    company = str(intake.get("company_name") or "Empresa Demo")
    package = str(fit.get("package_label") or "A DEFINIR")

    with st.form("aion_business_client_finance_demo_form", clear_on_submit=False):
        implementation_revenue = st.number_input(
            "Receita de implantação fictícia (R$)",
            min_value=0.0,
            value=2500.0,
            step=100.0,
            key="aion_business_fin_implementation",
        )
        monthly_revenue = st.number_input(
            "Receita mensal recorrente fictícia (R$)",
            min_value=0.0,
            value=1800.0,
            step=100.0,
            key="aion_business_fin_monthly_revenue",
        )
        f1,f2,f3 = st.columns(3)
        ai_cost = f1.number_input(
            "Custo IA (R$)", min_value=0.0, value=180.0, step=10.0,
            key="aion_business_fin_ai",
        )
        integration_cost = f2.number_input(
            "Integrações (R$)", min_value=0.0, value=120.0, step=10.0,
            key="aion_business_fin_integrations",
        )
        support_cost = f3.number_input(
            "Suporte (R$)", min_value=0.0, value=250.0, step=10.0,
            key="aion_business_fin_support",
        )
        f4,f5,f6 = st.columns(3)
        tool_cost = f4.number_input(
            "Ferramentas (R$)", min_value=0.0, value=90.0, step=10.0,
            key="aion_business_fin_tools",
        )
        tax_estimate = f5.number_input(
            "Impostos estimados (R$)", min_value=0.0, value=180.0, step=10.0,
            key="aion_business_fin_tax",
        )
        other_costs = f6.number_input(
            "Outros custos (R$)", min_value=0.0, value=30.0, step=10.0,
            key="aion_business_fin_other",
        )
        q1,q2 = st.columns(2)
        monthly_requests = q1.number_input(
            "Uso mensal / requisições",
            min_value=0,
            value=6000,
            step=100,
            key="aion_business_fin_requests",
        )
        request_quota = q2.number_input(
            "Quota mensal / requisições",
            min_value=1,
            value=10000,
            step=100,
            key="aion_business_fin_request_quota",
        )
        q3,q4 = st.columns(2)
        support_hours = q3.number_input(
            "Horas de suporte usadas",
            min_value=0.0,
            value=4.0,
            step=0.5,
            key="aion_business_fin_support_hours",
        )
        support_hour_quota = q4.number_input(
            "Quota de suporte (horas)",
            min_value=0.5,
            value=8.0,
            step=0.5,
            key="aion_business_fin_support_hour_quota",
        )
        payment_state = st.selectbox(
            "Estado de pagamento fictício",
            ["CURRENT", "DUE_SOON", "UNKNOWN", "OVERDUE_DEMO"],
            key="aion_business_fin_payment_state",
        )
        calculate = st.form_submit_button("Calcular economia do cliente demo")

    if calculate:
        economics = business_client_economics({
            "company_name": company,
            "package_label": package,
            "implementation_revenue": implementation_revenue,
            "monthly_revenue": monthly_revenue,
            "ai_cost": ai_cost,
            "integration_cost": integration_cost,
            "support_cost": support_cost,
            "tool_cost": tool_cost,
            "tax_estimate": tax_estimate,
            "other_costs": other_costs,
            "payment_state": payment_state,
            "monthly_requests": monthly_requests,
            "request_quota": request_quota,
            "support_hours": support_hours,
            "support_hour_quota": support_hour_quota,
        })
        review = business_pricing_review(economics)
        portfolio = business_finance_portfolio_summary([economics])
        st.session_state["aion_business_client_finance_demo_result"] = {
            "economics": economics,
            "review": review,
            "portfolio": portfolio,
        }

    result = st.session_state.get("aion_business_client_finance_demo_result")
    if not isinstance(result, Mapping):
        st.info("Calcule o exercício para abrir a visão financeira.")
        return

    economics = result.get("economics") if isinstance(result.get("economics"), Mapping) else {}
    eco = economics.get("economics") if isinstance(economics.get("economics"), Mapping) else {}
    capacity = economics.get("capacity") if isinstance(economics.get("capacity"), Mapping) else {}
    review = result.get("review") if isinstance(result.get("review"), Mapping) else {}

    view = st.selectbox(
        "Visão financeira",
        ("1 · Receita & margem", "2 · Custos", "3 · Capacidade", "4 · Revisão comercial"),
        key="aion_business_client_finance_view",
        help="Uma visão por vez para manter a navegação leve no celular.",
    )

    if view == "1 · Receita & margem":
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Receita mensal", f"R$ {float(eco.get('monthly_revenue') or 0):,.2f}")
        m2.metric("Custos mensais", f"R$ {float(eco.get('total_monthly_costs') or 0):,.2f}")
        m3.metric("Contribuição", f"R$ {float(eco.get('monthly_contribution') or 0):,.2f}")
        margin = eco.get("margin_pct")
        m4.metric("Margem", "N/D" if margin is None else f"{float(margin):.1f}%")
        st.caption(
            "Receita não é lucro. A contribuição mensal é receita menos os custos informados no exercício."
        )

    elif view == "2 · Custos":
        st.markdown("**Quebra de custos do cliente demo**")
        for key,value in dict(eco.get("cost_breakdown") or {}).items():
            st.write(f"{key}: **R$ {float(value or 0):,.2f}**")
        st.caption(
            "Custos de IA, integrações, suporte, ferramentas, impostos estimados e demais itens "
            "devem ser acompanhados para proteger a margem."
        )

    elif view == "3 · Capacidade":
        c1,c2,c3 = st.columns(3)
        req_pct = capacity.get("request_utilization_pct")
        support_pct = capacity.get("support_utilization_pct")
        c1.metric("Uso de requisições", "N/D" if req_pct is None else f"{float(req_pct):.1f}%")
        c2.metric("Uso de suporte", "N/D" if support_pct is None else f"{float(support_pct):.1f}%")
        c3.metric("Estado", str(capacity.get("state") or "UNKNOWN"))
        st.caption(
            "Quota por cliente ajuda a evitar sobrecarga do AION e protege a margem da operação."
        )

    else:
        st.markdown("**Revisão comercial**")
        st.write(f"Estado: **{review.get('state') or 'UNKNOWN'}**")
        for reason in list(review.get("reasons") or []):
            st.markdown(f"- {reason}")
        st.warning(
            "Preço, cobrança e reajuste nunca mudam automaticamente. "
            "Qualquer alteração comercial exige revisão humana e escopo atualizado."
        )
    st.caption(
        "Demo financeiro. Não é contabilidade real, não emite cobrança e não movimenta dinheiro."
    )



def _render_business_trend_intelligence_demo() -> None:
    """Evidence-first trend/opportunity demo with controlled improvement review."""
    st.markdown("#### 📡 Radar de Tendências & Melhoria Contínua · Demo")
    st.caption(
        "O AION deve procurar oportunidades continuamente, mas só promove ideias com evidência. "
        "Neste bloco usamos fixtures; o coletor web contínuo ainda permanece desligado."
    )

    now = datetime.now(timezone.utc)
    demo_evidence = [
        {
            "source_kind": "DEMO_FIXTURE",
            "source": "Pesquisa Demo A",
            "claim": "Empresas locais relatam demora no atendimento e perda de leads.",
            "segment": "Clínica",
            "observed_at": now.isoformat(),
            "confidence": 82,
            "demo": True,
        },
        {
            "source_kind": "DEMO_FIXTURE",
            "source": "Pesquisa Demo B",
            "claim": "Follow-up manual deixa oportunidades sem resposta.",
            "segment": "Clínica",
            "observed_at": now.isoformat(),
            "confidence": 78,
            "demo": True,
        },
    ]
    opportunities = [
        {
            "name": "AION Recupera Vendas",
            "segment": "Clínica",
            "problem": "Leads e orçamentos ficam sem retorno.",
            "offer": "Qualificação + follow-up + Radar de conversão.",
            "demand_signal": 84,
            "pain_intensity": 90,
            "recurring_revenue_fit": 92,
            "margin_potential": 78,
            "implementation_complexity": 42,
            "support_load": 32,
            "strategic_fit": 95,
        },
        {
            "name": "AION Atendimento & Agendamento",
            "segment": "Clínica",
            "problem": "Tempo de resposta alto e agendamentos perdidos.",
            "offer": "FAQ + triagem + agendamento + acompanhamento.",
            "demand_signal": 80,
            "pain_intensity": 86,
            "recurring_revenue_fit": 90,
            "margin_potential": 74,
            "implementation_complexity": 48,
            "support_load": 38,
            "strategic_fit": 93,
        },
        {
            "name": "AION Conteúdo Local",
            "segment": "Clínica",
            "problem": "Divulgação irregular.",
            "offer": "Calendário + criativos + relatório simples.",
            "demand_signal": 68,
            "pain_intensity": 60,
            "recurring_revenue_fit": 76,
            "margin_potential": 70,
            "implementation_complexity": 35,
            "support_load": 45,
            "strategic_fit": 72,
        },
    ]
    assessments = [
        business_evaluate_opportunity(item, demo_evidence, now=now)
        for item in opportunities
    ]
    ranked = business_rank_opportunities(assessments)
    posture = business_trend_watch_posture(assessments)

    view = st.selectbox(
        "Visão do Radar de Tendências",
        (
            "1 · Oportunidades",
            "2 · Evidências",
            "3 · Melhoria contínua",
            "4 · Monitoramento futuro",
        ),
        key="aion_business_trend_intelligence_view",
        help="Uma visão por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Oportunidades":
        st.markdown("**Ranking didático de oportunidades**")
        if not ranked:
            st.info("Nenhuma oportunidade passou do nível mínimo de observação.")
        for index,item in enumerate(ranked, start=1):
            opp = item.get("opportunity") if isinstance(item.get("opportunity"), Mapping) else {}
            st.markdown(
                f"**{index}. {opp.get('name') or 'Oportunidade'}** · "
                f"{item.get('state')} · score {float(item.get('score') or 0):.1f}/100"
            )
            st.write(str(item.get("recommendation") or ""))
            st.caption(
                f"Verdade: {item.get('truth_state')} · evidência: {item.get('evidence_quality')} · "
                "nenhum lançamento automático."
            )

    elif view == "2 · Evidências":
        st.markdown("**Por que uma tendência não pode ser só opinião**")
        for row in demo_evidence:
            st.markdown(
                f"- **{row['source']}** · {row['segment']} · confiança {row['confidence']}%  \n"
                f"  {row['claim']}"
            )
        st.warning(
            "Estas fontes são fixtures de demonstração. No runtime futuro, evidência precisa ter "
            "fonte, data, frescor e confiança verificáveis. Evidência velha ou incompleta não confirma tendência."
        )

    elif view == "3 · Melhoria contínua":
        st.markdown("**Experimento controlado**")
        before = st.number_input(
            "Métrica antes",
            min_value=0.0,
            value=100.0,
            step=1.0,
            key="aion_business_improvement_before",
        )
        after = st.number_input(
            "Métrica depois",
            min_value=0.0,
            value=112.0,
            step=1.0,
            key="aion_business_improvement_after",
        )
        sample = st.number_input(
            "Tamanho da amostra",
            min_value=0,
            value=80,
            step=1,
            key="aion_business_improvement_sample",
        )
        review = business_improvement_review(
            hypothesis="Follow-up mais rápido melhora a taxa de próximo passo.",
            metric_name="proximos_passos",
            before_value=before,
            after_value=after,
            sample_size=sample,
            higher_is_better=True,
        )
        st.write(f"Estado: **{review.get('state')}**")
        if review.get("change_pct") is not None:
            st.metric("Mudança observada", f"{float(review.get('change_pct')):.2f}%")
        if review.get("eligible_for_promotion_review"):
            st.success(
                "A evidência do exercício permite revisão humana para promover a melhoria."
            )
        else:
            st.info(
                "Ainda não há evidência suficiente para promover essa mudança."
            )
        st.caption(
            "Melhoria apoiada por dados ainda não altera produção automaticamente. "
            "Sem auto-deploy, auto-publicação ou auto-promoção."
        )

    else:
        m1,m2,m3 = st.columns(3)
        m1.metric("Candidatos fortes", int(posture.get("strong_candidates") or 0))
        m2.metric("Candidatos", int(posture.get("candidates") or 0))
        m3.metric("Em observação", int(posture.get("watch") or 0))
        st.write(
            "Objetivo futuro: coletar sinais autorizados de mercado e clientes, reavaliar "
            "oportunidades e aprender com experimentos de forma contínua."
        )
        st.warning(
            "Monitoramento contínuo real ainda está OFF. Para funcionar 24/7 será necessário "
            "um coletor autorizado, limites, proveniência, quotas e os gates de runtime."
        )
        st.caption(
            "Buscar tendências continuamente não significa lançar tudo que aparece. "
            "O AION observa → valida → testa → mede → submete para revisão."
        )



def _render_business_commercial_acquisition_demo() -> None:
    """Demo of acquisition, divulgação, outreach, contract handoff and content."""
    st.markdown("#### 🚀 Captação, Divulgação & Contrato · Demo")
    st.caption(
        "Mostra como a empresa entra no funil, como o site/divulgação explicam a oferta, "
        "como o lead é qualificado e como a proposta segue para contrato e onboarding. "
        "Nada é enviado, publicado, assinado ou cobrado."
    )

    simulator = st.session_state.get("aion_business_simulator_result")
    diagnostic = (
        simulator.get("diagnostic")
        if isinstance(simulator, Mapping) and isinstance(simulator.get("diagnostic"), Mapping)
        else {}
    )
    fit = (
        simulator.get("fit")
        if isinstance(simulator, Mapping) and isinstance(simulator.get("fit"), Mapping)
        else {}
    )
    intake = diagnostic.get("intake") if isinstance(diagnostic.get("intake"), Mapping) else {}
    segment = str(intake.get("segment") or "Clínica")
    company = str(intake.get("company_name") or "Empresa Demo")
    package = str(fit.get("package_label") or "AION Business")

    view = st.selectbox(
        "Etapa comercial",
        (
            "1 · Onde buscar empresas",
            "2 · Site / Landing Page",
            "3 · Qualificação & abordagem",
            "4 · Contrato & entrega",
            "5 · Conteúdo & divulgação",
            "6 · Funil",
        ),
        key="aion_business_commercial_acquisition_view",
        help="Uma etapa por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Onde buscar empresas":
        plan = business_build_channel_plan(segment)
        st.markdown(f"**Plano de captação para {segment}**")
        for item in list(plan.get("channels") or []):
            if isinstance(item, Mapping):
                st.markdown(f"**{item.get('id')}**  \n{item.get('play')}")
        st.caption(
            "A lista organiza canais de prospecção. Não coleta dados, não raspa contatos e "
            "não dispara mensagens automaticamente."
        )

    elif view == "2 · Site / Landing Page":
        brief = business_build_landing_page_brief(
            segment=segment,
            offer_name=package,
            primary_problem=(
                "Atendimento, follow-up, divulgação e gestão ficam fragmentados e difíceis de acompanhar."
            ),
            package_summary=(
                "Diagnóstico + implantação + Radar/Portal simples + manutenção mensal dentro do escopo."
            ),
        )
        body = brief.get("brief") if isinstance(brief.get("brief"), Mapping) else {}
        st.markdown(f"### {body.get('headline') or 'AION Business'}")
        st.write(str(body.get("problem") or ""))
        st.markdown("**Como o site deve ser organizado**")
        for section in list(body.get("sections") or []):
            st.markdown(f"- {section}")
        st.success(f"CTA principal: **{body.get('cta') or 'Solicitar diagnóstico'}**")
        st.caption(
            "O site vende o próximo passo — diagnóstico — e não promete lucro ou vendas garantidas."
        )

    elif view == "3 · Qualificação & abordagem":
        st.markdown("**Exercício de lead fictício**")
        permission = st.selectbox(
            "Estado de permissão do contato",
            ["UNKNOWN", "PERMITTED_DEMO", "OPT_IN_DEMO", "DO_NOT_CONTACT"],
            key="aion_business_commercial_permission",
        )
        pain = st.slider("Aderência do problema", 0, 100, 85, key="aion_business_commercial_pain")
        urgency = st.slider("Urgência", 0, 100, 70, key="aion_business_commercial_urgency")
        recurring = st.slider("Aderência a recorrência", 0, 100, 90, key="aion_business_commercial_recurring")
        prospect = business_qualify_prospect({
            "company_name": company,
            "segment": segment,
            "contact_permission_state": permission,
            "pain_fit": pain,
            "urgency": urgency,
            "recurring_fit": recurring,
            "decision_maker_access": 70,
            "data_readiness": 70,
        })
        p1,p2 = st.columns(2)
        p1.metric("Score", "N/D" if prospect.get("score") is None else f"{float(prospect.get('score')):.1f}/100")
        p2.metric("Estado", str(prospect.get("state") or "UNKNOWN"))
        draft = business_outreach_draft(prospect, sender_name="Mikael")
        if draft.get("draft"):
            st.markdown("**Rascunho de abordagem**")
            st.write(str(draft.get("draft")))
            st.caption("Rascunho somente; revisão humana obrigatória; não enviado.")
        else:
            st.warning(
                f"Abordagem bloqueada neste exercício: {draft.get('state') or 'UNKNOWN'}."
            )

    elif view == "4 · Contrato & entrega":
        st.markdown("**Trâmite depois da proposta**")
        handoff = business_build_contract_handoff(
            company_name=company,
            proposal_ready=True,
            scope_confirmed=True,
            privacy_terms_reviewed=True,
            sla_defined=True,
            commercial_terms_defined=True,
        )
        for item in list(handoff.get("flow") or []):
            if isinstance(item, Mapping):
                st.markdown(f"- **{item.get('stage')}** — {item.get('status')}")
        st.info(
            "Depois da revisão comercial/jurídica e assinatura real, o fluxo segue para cobrança "
            "e onboarding. Este demo para antes disso."
        )
        st.write(
            f"Portal do cliente: **{handoff.get('client_portal_state') or 'A DEFINIR'}**"
        )
        st.caption(
            "Nenhum contrato foi assinado, nenhuma fatura foi emitida e nenhum pagamento foi coletado."
        )

    elif view == "5 · Conteúdo & divulgação":
        verified_case = st.checkbox(
            "Existe caso real verificado disponível?",
            value=False,
            key="aion_business_commercial_verified_case",
        )
        plan = business_build_content_plan(
            segment=segment,
            weeks=6,
            verified_case_available=verified_case,
        )
        st.markdown("**Plano editorial demonstrativo**")
        for item in list(plan.get("items") or []):
            if isinstance(item, Mapping):
                st.markdown(
                    f"- Semana {item.get('week')} · **{item.get('content_type')}** — {item.get('theme')}"
                )
        st.caption(
            "Conteúdo nasce como DRAFT. Publicação exige aprovação. Caso real só entra se for verificável."
        )

    else:
        snapshot = business_commercial_funnel_snapshot({
            "PROSPECT": 30,
            "QUALIFIED": 12,
            "DIAGNOSTIC": 8,
            "PROPOSAL_DRAFT": 4,
            "CONTRACT_REVIEW": 2,
            "ONBOARDING_READY": 1,
        })
        counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), Mapping) else {}
        f1,f2,f3,f4 = st.columns(4)
        f1.metric("Prospects", int(counts.get("PROSPECT") or 0))
        f2.metric("Qualificados", int(counts.get("QUALIFIED") or 0))
        f3.metric("Diagnósticos", int(counts.get("DIAGNOSTIC") or 0))
        f4.metric("Propostas", int(counts.get("PROPOSAL_DRAFT") or 0))
        st.caption(
            "Funil fictício. Contatos reais enviados, contratos assinados e pagamentos reais continuam em zero."
        )



def _render_business_integration_hub_demo() -> None:
    """Render read-only readiness for future BUSINESS integrations."""
    st.markdown("#### 🔌 Hub de Integrações · Readiness Demo")
    st.caption(
        "Mostra quais sistemas o AION Business poderá integrar e quais permissões mínimas seriam "
        "necessárias. Nenhuma credencial real é pedida e nenhuma conexão externa acontece aqui."
    )

    demo_records = [
        business_integration_record(
            integration="WHATSAPP_BUSINESS",
            display_name="WhatsApp Business Demo",
            purpose="Atendimento e follow-up",
            account_reference="demo-whatsapp",
            config_complete=True,
            auth_review_complete=True,
            read_probe_ok=True,
            last_check_at=datetime.now(timezone.utc).isoformat(),
        ),
        business_integration_record(
            integration="EMAIL",
            display_name="E-mail Demo",
            purpose="Atendimento e propostas",
            account_reference="demo-email",
            config_complete=True,
            auth_review_complete=False,
        ),
        business_integration_record(
            integration="CRM",
            display_name="CRM Demo",
            purpose="Pipeline comercial",
            account_reference="demo-crm",
            config_complete=True,
            auth_review_complete=False,
        ),
        business_integration_record(
            integration="PAYMENTS",
            display_name="Pagamentos Demo",
            purpose="Leitura futura de cobrança",
            account_reference="demo-payments",
            config_complete=False,
        ),
    ]
    snapshot = business_integration_hub_snapshot(demo_records)
    secret_policy = business_integration_secret_policy()

    view = st.selectbox(
        "Visão do Hub de Integrações",
        (
            "1 · Estado geral",
            "2 · Permissões mínimas",
            "3 · Saúde das integrações",
            "4 · Segurança de credenciais",
            "5 · Pedido de conexão futuro",
        ),
        key="aion_business_integration_hub_view",
        help="Uma visão por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Estado geral":
        h1,h2,h3 = st.columns(3)
        h1.metric("Integrações mapeadas", int(snapshot.get("configured_count") or 0))
        h2.metric("Saudáveis read-only", int(snapshot.get("healthy_read_only_count") or 0))
        h3.metric("Conexões reais", int(snapshot.get("real_connections_active") or 0))
        st.markdown("**Catálogo previsto**")
        for name in BUSINESS_INTEGRATIONS:
            status = next(
                (
                    row.get("state")
                    for row in demo_records
                    if isinstance(row, Mapping) and row.get("integration") == name
                ),
                "NOT_CONFIGURED",
            )
            st.markdown(f"- **{name}** — {status}")
        st.caption(
            "WhatsApp, e-mail, formulários, calendário, CRM, pagamentos, redes sociais e analytics "
            "fazem parte do Hub previsto."
        )

    elif view == "2 · Permissões mínimas":
        integration = st.selectbox(
            "Integração para revisar",
            list(BUSINESS_INTEGRATIONS),
            key="aion_business_integration_scope_target",
        )
        plan = business_integration_scope_plan(
            integration,
            use_case="AION Business · operação do cliente",
        )
        st.markdown("**Princípio: LEAST PRIVILEGE**")
        for scope,state in dict(plan.get("scopes") or {}).items():
            st.markdown(f"- **{scope}** — {state}")
        st.warning(
            "Enviar mensagem, publicar conteúdo, emitir cobrança ou alterar dados externos nunca "
            "é liberado só porque a integração existe."
        )

    elif view == "3 · Saúde das integrações":
        for row in demo_records:
            if not isinstance(row, Mapping):
                continue
            health = business_integration_health(row, now=datetime.now(timezone.utc))
            st.markdown(
                f"**{row.get('display_name')}** · {health.get('state')} · "
                f"read-only={health.get('read_only')}"
            )
            age = health.get("last_check_age_hours")
            st.caption(
                "Última evidência: N/D"
                if age is None else
                f"Última evidência há {float(age):.1f}h"
            )
        st.caption(
            "Saúde aqui é demonstrativa; nenhum probe real de fornecedor foi executado."
        )

    elif view == "4 · Segurança de credenciais":
        st.markdown("**Política de segredo**")
        st.write(f"Modo: **{secret_policy.get('policy')}**")
        st.markdown("- Senha/token/chave real: **não inserir neste demo**")
        st.markdown("- Segredo em log: **proibido**")
        st.markdown("- Segredo em checkpoint/UI state: **proibido**")
        st.markdown(
            f"- Produção futura: **{secret_policy.get('future_secret_storage')}**"
        )
        st.caption(
            "Quando integrações reais forem liberadas, credenciais precisarão de armazenamento "
            "dedicado, rotação e menor privilégio possível."
        )

    else:
        selected = st.selectbox(
            "Sistema para preparar revisão",
            ["EMAIL", "CRM", "WHATSAPP_BUSINESS"],
            key="aion_business_integration_review_target",
        )
        record = next(
            (
                row for row in demo_records
                if isinstance(row, Mapping) and row.get("integration") == selected
            ),
            {},
        )
        scope = business_integration_scope_plan(selected)
        packet = business_integration_connection_review(
            record,
            scope,
            requested_by="Mikael",
        )
        st.write(f"Estado: **{packet.get('state')}**")
        st.write(f"Escopo de aprovação: **{packet.get('approval_scope')}**")
        st.caption(
            "O packet só prepara futura revisão. OAuth não é executado, credencial não é armazenada "
            "e nenhum write scope é concedido."
        )



def _render_business_privacy_audit_demo() -> None:
    """Render privacy/LGPD and audit governance with fictional metadata only."""
    st.markdown("#### 🛡️ Privacidade, LGPD & Auditoria · Demo")
    st.caption(
        "Organiza finalidade, consentimento, retenção, acesso por perfil, solicitações de dados, "
        "versionamento e rollback. Não contém dado pessoal real e não executa exclusão/exportação."
    )

    profile = business_privacy_profile(
        client_name="Clínica Horizonte Demo",
        purposes=["Atendimento", "Qualificação de leads", "Suporte"],
        data_categories=["CONTACT", "LEAD", "SUPPORT", "USAGE_METRICS"],
        legal_basis_label="Base jurídica a validar com responsável",
        retention_days=90,
        controller_contact="responsavel-demo",
    )
    matrix = business_privacy_role_access_matrix(profile)

    view = st.selectbox(
        "Visão de governança",
        (
            "1 · Finalidade & consentimento",
            "2 · Acesso por perfil",
            "3 · Retenção / exportação / exclusão",
            "4 · Trilha de auditoria",
            "5 · Versionamento & rollback",
        ),
        key="aion_business_privacy_audit_view",
        help="Uma visão por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Finalidade & consentimento":
        st.markdown("**Perfil de privacidade fictício**")
        st.write(f"Cliente: **{profile.get('client_name')}**")
        st.markdown("**Finalidades**")
        for purpose in list(profile.get("purposes") or []):
            st.markdown(f"- {purpose}")
        st.markdown("**Categorias previstas**")
        for category in list(profile.get("data_categories") or []):
            st.markdown(f"- {category}")
        consent = business_privacy_consent_record(
            subject_reference="subject-demo-001",
            purpose="Atendimento",
            granted=True,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            source="form-demo",
        )
        st.info(
            f"Consentimento de exercício: **{consent.get('state')}** · "
            "sujeito real não verificado."
        )
        st.caption(
            "O AION não decide sozinho a base jurídica. Finalidade e base aplicável precisam "
            "ser revisadas para o caso real."
        )

    elif view == "2 · Acesso por perfil":
        role = st.selectbox(
            "Perfil",
            ["CLIENT_ADMIN", "CLIENT_OPERATOR", "AION_SUPPORT", "AION_ADMIN", "AUDITOR"],
            key="aion_business_privacy_role",
        )
        category = st.selectbox(
            "Categoria de dado",
            list(profile.get("data_categories") or []),
            key="aion_business_privacy_category",
        )
        read = business_privacy_access_decision(
            matrix,
            role=role,
            category=category,
            requested_action="READ",
        )
        write = business_privacy_access_decision(
            matrix,
            role=role,
            category=category,
            requested_action="WRITE",
        )
        a1,a2 = st.columns(2)
        a1.metric("Leitura", "PERMITIDA DEMO" if read.get("allowed") else "NEGADA")
        a2.metric("Escrita", "PERMITIDA DEMO" if write.get("allowed") else "NEGADA")
        st.caption(
            "Default deny + least privilege. Permissão demonstrativa não executa leitura/escrita externa."
        )

    elif view == "3 · Retenção / exportação / exclusão":
        retention = business_privacy_retention_review(
            profile,
            created_at="2026-06-01T00:00:00Z",
            now=datetime.now(timezone.utc),
        )
        st.write(f"Retenção: **{retention.get('state')}**")
        st.write(f"Prazo configurado: **{profile.get('retention_days')} dias**")
        request_type = st.selectbox(
            "Solicitação de titular fictícia",
            ["EXPORT", "DELETE", "CORRECT", "RESTRICT"],
            key="aion_business_privacy_request_type",
        )
        request = business_privacy_subject_request(
            request_type=request_type,
            subject_reference="subject-demo-001",
            requested_at=datetime.now(timezone.utc).isoformat(),
            reason="Exercício de governança",
        )
        st.info(f"Pedido: **{request.get('state')}**")
        st.caption(
            "Identidade e aprovação ainda não foram verificadas. O demo não exporta, não corrige "
            "e não exclui nenhum dado."
        )

    elif view == "4 · Trilha de auditoria":
        events = [
            business_privacy_audit_event(
                actor="Mikael",
                action="VIEW",
                target="Radar do Cliente Demo",
            ),
            business_privacy_audit_event(
                actor="Mikael",
                action="APPROVAL",
                target="Proposta Demo",
                approval_reference="approval-demo-001",
            ),
            business_privacy_audit_event(
                actor="AION",
                action="DRAFT",
                target="Follow-up Demo",
            ),
        ]
        snapshot = business_privacy_governance_snapshot(profile, events)
        g1,g2 = st.columns(2)
        g1.metric("Eventos auditáveis", int(snapshot.get("audit_event_count") or 0))
        g2.metric("Dados pessoais reais", "NÃO")
        for event in events:
            st.markdown(
                f"- **{event.get('action')}** · {event.get('actor')} → {event.get('target')} · "
                f"digest {str(event.get('event_digest') or '')[:12]}…"
            )
        st.caption(
            "Registro de auditoria documenta ação/aprovação, mas nunca concede autoridade por si só."
        )

    else:
        v1 = business_privacy_automation_version(
            automation_name="followup-business-demo",
            version="1",
            config={"mode": "manual_review", "send": False},
            approved_by="Mikael",
        )
        v2 = business_privacy_automation_version(
            automation_name="followup-business-demo",
            version="2",
            config={"mode": "draft_only", "send": False, "audit": True},
            approved_by="Mikael",
        )
        rollback = business_privacy_rollback_plan(v2, v1)
        st.markdown("**Versões do exercício**")
        st.write(f"Atual: **v{v2.get('version')}** · anterior: **v{v1.get('version')}**")
        st.write(f"Rollback: **{rollback.get('state')}**")
        st.warning(
            "Rollback real exige aprovação humana. Este bloco apenas prepara referência de versão; "
            "nenhuma configuração de produção é alterada."
        )



def _render_business_master_readiness() -> None:
    """Compact at-a-glance Business status that never grants operational authority."""
    evidence = business_default_demo_evidence()
    snapshot = business_master_readiness_snapshot(evidence)
    rows = business_master_status_rows(snapshot)

    st.markdown("#### 🧭 Painel Mestre Business")
    st.caption(
        "Leitura rápida: o que está pronto em DEMO, o que ainda falta para revisar um piloto e "
        "por que o runtime continua desligado."
    )
    cols = st.columns(3)
    for index,row in enumerate(rows):
        cols[index].metric(
            str(row.get("layer") or ""),
            f"{float(row.get('progress_pct') or 0):.0f}%",
            str(row.get("state") or "UNKNOWN"),
        )
    st.progress(int(round(float(snapshot.get("demo", {}).get("progress_pct") or 0))))
    st.success(
        "Camada DEMO consolidada. Isso não significa piloto autorizado nem operação real."
        if snapshot.get("demo", {}).get("complete")
        else
        "Ainda existem gates de DEMO pendentes."
    )
    st.warning(
        "PILOT: revisão humana ainda necessária · LIVE: RUNTIME OFF · "
        "sem contato real, cobrança, publicação ou ação externa."
    )

    with st.expander("Ver gates do piloto que ainda faltam", expanded=False):
        missing = list(snapshot.get("pilot", {}).get("missing") or [])
        if missing:
            for gate in missing:
                st.markdown(f"- {gate}")
        else:
            packet = business_pilot_review_packet(
                snapshot,
                requested_by="Mikael",
                pilot_scope="Piloto Business controlado",
            )
            st.write(f"Estado: **{packet.get('state')}**")
            st.caption("Mesmo elegível, o packet não autoriza piloto automaticamente.")



def _render_business_pilot_governance_demo() -> None:
    """Bounded first-pilot planning; never authorizes or activates a real pilot."""
    st.markdown("#### 🧪 Governança do Primeiro Piloto · Readiness")
    st.caption(
        "Define como seria o primeiro piloto real sem liberar nada: 1 cliente, 1 fluxo, poucos canais, "
        "prazo curto, operador humano e critérios claros de parada."
    )

    evidence = business_default_demo_evidence()
    master = business_master_readiness_snapshot(evidence)
    charter = business_build_pilot_charter(
        client_reference="CLIENTE_REAL_A_DEFINIR",
        segment="Clínica",
        package_label="Atendimento & Conversão",
        workflow_name="Atendimento inicial + follow-up controlado",
        channels=["WhatsApp Business"],
        duration_days=14,
        human_operators=["Mikael"],
        support_owner="Mikael",
        daily_external_action_cap=0,
        allow_external_messages=False,
        allow_publication=False,
        allow_payments=False,
    )
    success = business_define_pilot_success_criteria(
        metric_names=["tempo_resposta", "leads_qualificados", "proximos_passos"],
        minimum_sample_size=30,
        review_cadence_days=7,
    )
    stop = business_define_pilot_stop_conditions(
        reasons=list(BUSINESS_PILOT_STOP_REASONS),
        immediate_stop_on_unexpected_external_action=True,
    )

    gates = {
        "business_specialist_certified": evidence.get("business_certified") is True,
        "master_readiness_demo_complete": master.get("demo", {}).get("complete") is True,
        "scope_confirmed": evidence.get("package_scope_reviewed") is True,
        "privacy_profile_ready": evidence.get("privacy_profile_reviewed") is True,
        "sla_defined": evidence.get("support_sla_reviewed") is True,
        "margin_reviewed": evidence.get("client_finance_reviewed") is True,
        "capacity_reviewed": evidence.get("capacity_reviewed") is True,
        "integration_readiness_reviewed": evidence.get("integration_scope_reviewed") is True,
        "rollback_ready": evidence.get("rollback_plan_reviewed") is True,
        "human_operator_assigned": evidence.get("human_operator_assigned") is True,
        "support_owner_assigned": evidence.get("human_operator_assigned") is True,
    }
    review = business_pilot_gate_review(charter, gates, success, stop)
    packet = business_bounded_pilot_review_packet(
        charter,
        review,
        requested_by="Mikael",
    )
    posture = business_pilot_posture(charter, review, packet)

    view = st.selectbox(
        "Visão do piloto",
        (
            "1 · Limites",
            "2 · Gates obrigatórios",
            "3 · Critérios de sucesso",
            "4 · Condições de parada",
            "5 · Estado de autorização",
        ),
        key="aion_business_pilot_governance_view",
        help="Uma visão por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Limites":
        row = charter.get("charter") if isinstance(charter.get("charter"), Mapping) else {}
        p1,p2,p3,p4 = st.columns(4)
        p1.metric("Clientes", int(row.get("client_count") or 0))
        p2.metric("Fluxos", int(row.get("workflow_count") or 0))
        p3.metric("Canais", len(list(row.get("channels") or [])))
        p4.metric("Prazo", f"{int(row.get('duration_days') or 0)} dias")
        st.markdown(f"**Pacote:** {row.get('package_label') or 'A DEFINIR'}")
        st.markdown(f"**Fluxo:** {row.get('workflow_name') or 'A DEFINIR'}")
        st.caption(
            "Nesta V1, mensagens externas, publicação, pagamentos e runtime continuam OFF. "
            "O charter é somente planejamento."
        )

    elif view == "2 · Gates obrigatórios":
        st.write(f"Estado: **{review.get('state')}**")
        gate_rows = review.get("gates") if isinstance(review.get("gates"), Mapping) else {}
        for name,passed in gate_rows.items():
            icon = "✅" if passed else "⛔"
            st.markdown(f"- {icon} **{name}**")
        st.caption(
            "Gate pendente bloqueia o piloto. DEMO completo, sozinho, não autoriza cliente real."
        )

    elif view == "3 · Critérios de sucesso":
        st.markdown("**Métricas do exercício**")
        for metric in list(success.get("metrics") or []):
            st.markdown(f"- {metric}")
        st.write(f"Amostra mínima: **{success.get('minimum_sample_size')}**")
        st.write(f"Revisão a cada: **{success.get('review_cadence_days')} dias**")
        st.caption(
            "Critério de sucesso não inclui garantia de lucro ou venda. Resultado precisa de amostra e fonte."
        )

    elif view == "4 · Condições de parada":
        st.markdown("**Parar e escalar para humano se ocorrer:**")
        for reason in list(stop.get("reasons") or []):
            st.markdown(f"- {reason}")
        st.warning(
            "A V1 ainda não possui desligamento automático de runtime porque runtime continua OFF. "
            "O objetivo é definir o procedimento antes de qualquer piloto."
        )

    else:
        a1,a2,a3 = st.columns(3)
        a1.metric("Charter", str(charter.get("state") or "UNKNOWN"))
        a2.metric("Gates", str(review.get("state") or "UNKNOWN"))
        a3.metric("Piloto autorizado", "NÃO")
        st.write(f"Postura: **{posture.get('state')}**")
        if review.get("failed_gates"):
            st.markdown("**Ainda falta revisar:**")
            for gate in list(review.get("failed_gates") or []):
                st.markdown(f"- {gate}")
        st.caption(
            "Mesmo quando todos os gates passarem, o máximo será HUMAN_PILOT_APPROVAL_REQUIRED. "
            "Nenhuma aprovação real foi registrada e o runtime permanece OFF."
        )



def _render_business_stack_consolidation_v2() -> None:
    """Frozen administrative view of the #394–#412 stack; never merges."""
    evidence = business_stack_frozen_green_evidence()
    validation = business_stack_validate(evidence)
    preview = business_stack_consolidation_preview(validation)
    bundle = business_stack_release_bundle(validation)
    rollback = business_stack_rollback_plan(validation)
    options = business_stack_admin_options(validation)

    st.markdown("#### 🧱 Consolidação da Stack Business · V2")
    st.caption(
        "Snapshot congelado da sequência #394–#412. Serve para revisão administrativa; "
        "não executa merge, deploy nem runtime."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("PRs na stack", int(validation.get("pr_count") or 0))
    c2.metric("Validadas", int(validation.get("passed_count") or 0))
    c3.metric("Bloqueadas", int(validation.get("blocked_count") or 0))
    c4.metric("Merge autorizado", "NÃO")

    view = st.selectbox(
        "Visão da consolidação",
        (
            "1 · Estado geral",
            "2 · Ordem técnica",
            "3 · Bundle congelado",
            "4 · Rollback de integração",
            "5 · Decisão administrativa",
            "6 · Dry-run fail-closed",
            "7 · Pedido de decisão vinculado",
            "8 · Contrato de autorização explícita",
            "9 · Preflight de execução",
            "10 · Pacote de revisão de execução",
            "11 · Verificação pós-merge",
            "12 · Ledger sequencial",
            "13 · Revisão final da consolidação",
            "14 · Handoff para decisão de deploy",
            "15 · Verificação de deploy & fronteira de runtime",
            "16 · Prontidão para ativação controlada",
            "17 · Pós-ativação & fronteira de expansão",
            "18 · Prontidão para expansão controlada",
            "19 · Pós-expansão & congelamento do ciclo",
            "20 · Ledger auditável de ciclos de expansão",
            "21 · Capacidade & quotas por tenant",
            "22 · Autorização de aplicação de quotas",
            "23 · Equipe & Acessos / RBAC",
            "24 · Gestor de Capacidade & Escala",
            "25 · FinOps & Tesouraria",
            "26 · AION · Roteador dos 8 papéis",
            "27 · Oferta B2B & Receita",
            "28 · Primeiro Piloto & Preco",
            "29 · Backup & Recovery",
            "30 · Indice de Independencia CLT",
            "31 · Pipeline Comercial · Dados Reais",
        ),
        key="aion_business_stack_consolidation_v2_view",
        help="Uma visão por vez para manter a experiência leve no celular.",
    )

    if view == "1 · Estado geral":
        st.write(f"Estado: **{validation.get('state')}**")
        st.progress(int(round((float(validation.get("passed_count") or 0) / max(1, int(validation.get("pr_count") or 1))) * 100)))
        st.success(
            "Snapshot tecnicamente coerente para revisão administrativa."
            if validation.get("state") == "READY_FOR_ADMIN_REVIEW"
            else
            "Existem bloqueios na stack."
        )
        st.warning(
            "CI verde não autoriza merge. Merge não autoriza deploy. Deploy não autoriza runtime."
        )
        with st.expander("Ver PRs congeladas no snapshot", expanded=False):
            for row in list(validation.get("rows") or []):
                icon = "✅" if row.get("passed") else "⛔"
                st.markdown(f"- {icon} **#{row.get('pr')}** · {row.get('title')}")

    elif view == "2 · Ordem técnica":
        st.write(f"Estratégia: **{preview.get('strategy') or 'BLOCKED'}**")
        for row in list(preview.get("sequence") or []):
            st.markdown(
                f"{row.get('order')}. **#{row.get('pr')}** · {row.get('title')}  \\n"
                f"   SHA: `{row.get('head_sha')}`"
            )
        st.caption(
            "A ordem é somente preview técnico. Nenhuma PR é mergeada por esta tela."
        )

    elif view == "3 · Bundle congelado":
        st.write(f"Estado: **{bundle.get('state')}**")
        digest = str(bundle.get("bundle_digest") or "")
        st.code(digest if digest else "BUNDLE BLOQUEADO", language=None)
        st.caption(
            "O digest congela a combinação esperada de SHAs/checks para revisão. "
            "Antes de qualquer merge real, GitHub deve ser verificado novamente ao vivo."
        )

    elif view == "4 · Rollback de integração":
        st.write(f"Estado: **{rollback.get('state')}**")
        for item in list(rollback.get("steps") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O plano não executa rollback. Ele define o procedimento para parar na primeira regressão "
            "e preservar o SHA anterior da main."
        )

    elif view == "5 · Decisão administrativa":
        st.markdown("**Opções disponíveis**")
        for item in options:
            if isinstance(item, Mapping):
                st.markdown(f"- **{item.get('label')}**")
        st.info(
            "A próxima ação que altera repositório continua dependendo de autorização administrativa "
            "explícita. Até lá, todas as PRs permanecem Draft."
        )
        st.caption(
            "Runtime BUSINESS OFF · sem deploy · sem publicação · sem cobrança · sem piloto."
        )

    elif view == "6 · Dry-run fail-closed":
        live = business_live_revalidation_snapshot_v2({})
        dry_run = business_build_consolidation_dry_run_v2(validation, live)
        st.write(f"Estado: **{dry_run.get('state')}**")
        st.warning(
            "Snapshot congelado não é evidência GitHub ao vivo. Antes de qualquer decisão futura, "
            "todos os gates abaixo precisam ser revalidados externamente."
        )
        for gate in list(live.get("missing") or []):
            st.markdown(f"- {gate}")
        st.caption(
            "Mesmo com revalidação completa, o máximo é READY_FOR_EXPLICIT_ADMIN_DECISION. "
            "Merge, deploy, piloto e runtime continuam sem autorização."
        )

    elif view == "7 · Pedido de decisão vinculado":
        request = business_consolidation_decision_request_template()
        st.write(f"Estado: **{request.get('state')}**")
        st.markdown("**Bindings obrigatórios para uma futura decisão explícita:**")
        for item in list(request.get("required_bindings") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Não existe autorização registrada. O pedido só poderá ser formado depois da "
            "revalidação ao vivo e ficará vinculado a SHA, base, bundle e evidência exatos."
        )
        st.caption(
            "Estado máximo do pedido: HUMAN_AUTHORIZATION_RECORD_REQUIRED. "
            "Ele não executa merge, deploy, piloto ou runtime."
        )

    elif view == "8 · Contrato de autorização explícita":
        contract = business_consolidation_authorization_requirements()
        st.write(f"Estado: **{contract.get('state')}**")
        st.markdown("**Token explícito obrigatório:**")
        st.code(str(contract.get("required_decision_token") or ""), language=None)
        st.markdown("**Acknowledgements obrigatórios:**")
        for item in list(contract.get("required_acknowledgements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Mensagens genéricas como ok, vamos lá ou pode seguir não são autorização de consolidação."
        )
        st.caption(
            "Mesmo um registro explícito validado não executa merge. "
            "Deploy, piloto e runtime continuam fronteiras separadas."
        )

    elif view == "9 · Preflight de execução":
        preflight = business_consolidation_execution_preflight_template()
        st.write(f"Estado: **{preflight.get('state')}**")
        st.markdown("**Gates da última barreira antes de qualquer merge físico:**")
        for item in list(preflight.get("requirements") or []):
            st.markdown(f"- {item}")
        st.markdown("**Depois de cada etapa futura:**")
        for item in list(preflight.get("post_step_requirements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O máximo deste preflight é MERGE_EXECUTION_REVIEW_REQUIRED. "
            "Ele não executa nem autoriza fisicamente merge."
        )
        st.caption(
            "Ordem sequencial obrigatória · stop-on-drift · BUSINESS runtime OFF · deploy separado."
        )

    elif view == "10 · Pacote de revisão de execução":
        packet = business_execution_review_packet_template()
        st.write(f"Estado: **{packet.get('state')}**")
        st.markdown("**Seções obrigatórias do dossiê de revisão:**")
        for item in list(packet.get("sections") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O pacote só congela evidência para leitura humana. Ele não cria autorização."
        )
        st.caption(
            "Estado máximo: READY_FOR_HUMAN_EXECUTION_REVIEW · "
            "merge_execution_authorized=false · runtime OFF."
        )

    elif view == "11 · Verificação pós-merge":
        post_merge = business_post_merge_verification_template()
        st.write(f"Estado: **{post_merge.get('state')}**")
        st.markdown("**Checks obrigatórios após qualquer merge futuro:**")
        for item in list(post_merge.get("required_checks") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Sem merge real e evidência real, o estado permanece POST_MERGE_EVIDENCE_REQUIRED."
        )
        st.caption(
            "Etapa verde: STEP_VERIFIED_FOR_NEXT_PREFLIGHT · "
            "regressão: ROLLBACK_REVIEW_REQUIRED · rollback automático proibido."
        )

    elif view == "12 · Ledger sequencial":
        ledger = business_consolidation_progress_ledger_template()
        st.write(f"Estado: **{ledger.get('state')}**")
        st.write(
            f"Progresso: **{ledger.get('completed_count', 0)}/{ledger.get('total_steps', 0)}** · "
            f"próxima PR esperada: **#{ledger.get('next_expected_pr')}**"
        )
        st.markdown("**Requisitos da revisão final depois das 19 etapas:**")
        for item in list(ledger.get("completion_requirements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O ledger aceita apenas recibos pós-merge verificados em ordem e com cadeia de rollback contínua."
        )
        st.caption(
            "Mesmo completo: CONSOLIDATION_COMPLETE_REVIEW_REQUIRED · "
            "deploy e runtime continuam separados."
        )

    elif view == "13 · Revisão final da consolidação":
        review = business_consolidation_completion_review_template()
        request = business_final_admin_decision_request(review)
        st.write(f"Estado: **{review.get('state')}**")
        st.markdown("**Evidências obrigatórias para fechar tecnicamente a consolidação:**")
        for item in list(review.get("requirements") or []):
            st.markdown(f"- {item}")
        st.markdown("**Checks finais obrigatórios na main:**")
        for item in list(review.get("required_checks") or []):
            st.markdown(f"- {item}")
        st.warning(
            "A consolidação só pode chegar a READY_FOR_FINAL_ADMIN_REVIEW depois de 19 etapas "
            "verificadas, SHA final da main coerente, CI/UI/mobile verdes, runtime BUSINESS OFF "
            "e decisão de deploy mantida separada."
        )
        st.markdown("**Acknowledgement final exigirá token explícito:**")
        st.code(str(review.get("required_decision_token") or ""), language=None)
        st.caption(
            "Mensagens genéricas como 'vamos lá', 'ok' ou 'pode seguir' não encerram a consolidação. "
            "Mesmo o acknowledgement técnico não autoriza deploy, produção, piloto ou runtime."
        )

    elif view == "14 · Handoff para decisão de deploy":
        handoff = business_release_handoff_template()
        request = business_deploy_decision_request(handoff)
        st.write(f"Estado: **{handoff.get('state')}**")
        st.markdown("**Itens obrigatórios antes de qualquer decisão futura de deploy:**")
        for item in list(handoff.get("required_items") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Consolidação técnica reconhecida não é deploy. Deploy, por sua vez, não liga o "
            "runtime BUSINESS. Cada fronteira exige decisão separada."
        )
        st.markdown("**Token reservado para uma futura decisão explícita de deploy:**")
        st.code(str(handoff.get("required_deploy_decision_token") or ""), language=None)
        st.markdown("**Acknowledgements obrigatórios do deploy:**")
        for item in list(handoff.get("deploy_acknowledgements") or []):
            st.markdown(f"- {item}")
        st.caption(
            "Esta tela só prepara o handoff. Nenhum deploy é autorizado ou executado; "
            "runtime, piloto e ações com cliente real permanecem OFF."
        )

    elif view == "15 · Verificação de deploy & fronteira de runtime":
        deploy = business_deploy_authorization_requirements()
        verification = business_deployment_verification_template()
        st.write(f"Estado de autorização: **{deploy.get('state')}**")
        st.markdown("**Token explícito reservado para deploy-only:**")
        st.code(str(deploy.get("required_decision_token") or ""), language=None)
        st.markdown("**Checks obrigatórios depois de um deploy futuro:**")
        for item in list(verification.get("required_health_checks") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Mesmo um deploy autorizado e executado precisa ser verificado com SHA, ambiente, "
            "saúde, monitoramento e runtime ainda OFF antes de qualquer discussão de ativação."
        )
        st.markdown("**Próxima fronteira futura:**")
        st.code("AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION", language=None)
        st.caption(
            "Esta visão não registra autorização, não executa deploy e não ativa runtime. "
            "Mensagem genérica como 'vamos lá' continua sem autoridade operacional."
        )

    elif view == "16 · Prontidão para ativação controlada":
        readiness = business_runtime_activation_requirements()
        post = business_post_activation_verification_template()
        st.write(f"Estado: **{readiness.get('state')}**")
        st.markdown("**Token explícito exigido para uma futura decisão de runtime:**")
        st.code(str(readiness.get("required_decision_token") or ""), language=None)
        st.markdown("**Escopos permitidos:**")
        for item in list(readiness.get("allowed_activation_scopes") or []):
            st.markdown(f"- {item}")
        st.markdown("**Acknowledgements obrigatórios:**")
        for item in list(readiness.get("required_acknowledgements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Autorização de runtime não é execução. Sandbox não aceita tenant real; "
            "pilot e bounded_production ficam limitados a até 10 tenants explicitamente listados."
        )
        st.markdown("**Checks exigidos depois de qualquer futura ativação executada por caminho separado:**")
        for item in list(post.get("required_checks") or []):
            st.markdown(f"- {item}")
        st.caption(
            "Execução física, expansão automática, cobrança e ações com clientes continuam bloqueadas. "
            "Mensagem genérica como 'vamos lá' não autoriza runtime."
        )

    elif view == "17 · Pós-ativação & fronteira de expansão":
        boundary = business_post_activation_boundary_requirements()
        st.write(f"Estado: **{boundary.get('state')}**")
        st.markdown("**Checks obrigatórios para verificar uma futura ativação:**")
        for item in list(boundary.get("required_checks") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Escopo e conjunto de tenants observados precisam ser exatamente iguais ao que foi autorizado. "
            "Qualquer drift bloqueia a verificação."
        )
        st.markdown("**Próxima fronteira, somente depois de ativação verificada:**")
        st.code(BUSINESS_EXPANSION_DECISION_TOKEN, language=None)
        st.markdown("**Acknowledgements de uma futura decisão de expansão:**")
        for item in BUSINESS_EXPANSION_ACKNOWLEDGEMENTS:
            st.markdown(f"- {item}")
        st.caption(
            "Ativação verificada congela o escopo. Expansão automática, cobrança e ações com clientes "
            "continuam bloqueadas e exigem decisões separadas."
        )

    elif view == "18 · Prontidão para expansão controlada":
        expansion = business_expansion_authorization_requirements()
        st.write(f"Estado: **{expansion.get('state')}**")
        st.markdown("**Token explícito para uma futura decisão de expansão:**")
        st.code(str(expansion.get("required_decision_token") or ""), language=None)
        st.markdown("**Acknowledgements obrigatórios:**")
        for item in list(expansion.get("required_acknowledgements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "A expansão só pode ser gradual: sandbox → pilot → bounded_production, "
            "ou aumento explícito de tenants dentro do estágio atual. "
            "Saltos, downgrades e remoção silenciosa de tenants são bloqueados."
        )
        st.caption(
            "Máximo de 10 tenants nesta versão. Privacidade, suporte, finanças, integrações, "
            "capacidade, monitoramento e rollback precisam ser revalidados. "
            "Autorização continua separada da execução."
        )

    elif view == "19 · Pós-expansão & congelamento do ciclo":
        verification = business_post_expansion_verification_requirements()
        st.write(f"Estado: **{verification.get('state')}**")
        st.markdown("**Checks obrigatórios depois de uma futura expansão executada por caminho separado:**")
        for item in list(verification.get("required_checks") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O escopo e os tenants observados precisam coincidir exatamente com a proposta autorizada. "
            "Qualquer drift, falha de saúde ou quebra de isolamento bloqueia o fechamento do ciclo."
        )
        st.markdown("**Estado verde esperado:**")
        st.code("SCOPE_EXPANSION_VERIFIED_AND_FROZEN", language=None)
        st.caption(
            "Depois da verificação, o novo escopo volta a ficar congelado. "
            "Uma nova expansão precisa recomeçar pelo boundary explícito; "
            "não existe crescimento automático, cobrança automática ou ação automática com clientes."
        )

    elif view == "20 · Ledger auditável de ciclos de expansão":
        ledger = business_expansion_cycle_ledger_template()
        audit = business_audit_expansion_cycle_ledger(ledger)
        st.write(f"Estado do ledger: **{ledger.get('state')}**")
        st.write(f"Integridade: **{audit.get('state')}**")
        st.markdown("**Proteções do histórico:**")
        for item in (
            "sequência estrita",
            "digest encadeado",
            "anti-replay",
            "continuidade exata de escopo",
            "continuidade exata de tenants",
            "progressão e limite de tenants revalidados",
        ):
            st.markdown(f"- {item}")
        st.warning(
            "Somente receipts pós-expansão já verificados e congelados podem entrar no ledger. "
            "História adulterada, duplicada ou descontínua bloqueia o append."
        )
        st.caption(
            "O ledger é somente administrativo. Ele não expande tenants, não altera runtime, "
            "não cobra, não publica e não executa ações com clientes."
        )

    elif view == "21 · Capacidade & quotas por tenant":
        capacity = business_capacity_policy_requirements()
        st.write(f"Estado: **{capacity.get('state')}**")
        st.markdown("**Quotas obrigatórias por tenant:**")
        for item in list(capacity.get("required_quota_fields") or []):
            st.markdown(f"- {item}")
        st.warning(
            "O conjunto de tenants precisa coincidir exatamente com o último estado íntegro do ledger. "
            "A margem mínima e a reserva de capacidade são políticas explícitas do administrador."
        )
        st.caption(
            "A análise não aplica quotas nem cobrança. Mesmo verde, o máximo é uma nova decisão de aplicação; "
            "runtime, billing, expansão e ações com clientes continuam separados."
        )

    elif view == "22 · Autorização de aplicação de quotas":
        quota_auth = business_quota_application_authorization_requirements()
        st.write(f"Estado: **{quota_auth.get('state')}**")
        st.markdown("**Token explícito obrigatório:**")
        st.code(str(quota_auth.get("required_decision_token") or ""), language=None)
        st.markdown("**Acknowledgements obrigatórios:**")
        for item in list(quota_auth.get("required_acknowledgements") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Autorizar o plano não aplica quotas. Antes de qualquer execução futura ainda são exigidos "
            "janela de mudança, monitoramento, rollback/restauração, dry-run, suporte e resposta a incidentes."
        )
        st.caption(
            "Mensagens genéricas como 'vamos lá' não autorizam aplicação de quotas. "
            "Billing, expansão, runtime e ações com clientes permanecem separados."
        )

    elif view == "23 · Equipe & Acessos / RBAC":
        st.write("Estado: **TEAM_ACCESS_RBAC_IMPLEMENTED_IN_VALIDATION**")
        st.markdown("**Perfis Business previstos:**")
        for profile in business_team_access_profiles:
            st.markdown(f"- {profile}")
        st.warning(
            "Funcionário usa conta individual. O login ADMIN não é compartilhado. "
            "Cada membership fica limitado aos tenants/clientes atribuídos e exige autenticação forte."
        )
        st.caption(
            "O AION obedece à mesma decisão de permissão da interface. "
            "Cross-tenant, elevação automática, billing, deploy, runtime e outras ações críticas "
            "continuam bloqueados por gates separados."
        )

    elif view == "24 · Gestor de Capacidade & Escala":
        scale = business_capacity_scale_policy()
        st.write(f"Estado: **{scale.get('state')}**")
        st.metric("Teto inicial planejado", f"R$ {float(scale.get('initial_budget_cap_brl') or 0):.0f}/mês")
        st.metric("Máximo de tenants nesta fase", int(scale.get("max_bounded_tenants") or 0))
        st.markdown("**O gestor considera antes de recomendar crescimento:**")
        for item in (
            "custo atual dos tenants + custo compartilhado da plataforma",
            "orçamento mensal aprovado",
            "horas de suporte disponíveis",
            "headroom de infraestrutura",
            "utilização e incidentes dos clientes atuais",
            "custo e receita estimados do próximo cliente",
            "margem mínima definida",
        ):
            st.markdown(f"- {item}")
        st.warning(
            "O resultado informa somente quantos novos clientes cabem com segurança. "
            "Admissão continua dependendo de decisão explícita."
        )
        st.caption(
            "Nenhum cliente é aceito automaticamente e o orçamento não pode ser aumentado por esta camada."
        )

    elif view == "25 · FinOps & Tesouraria":
        finops = business_finops_policy()
        treasury = business_revenue_routing_policy()
        st.write(f"Estado: **{finops.get('state')}**")
        st.metric(
            "Teto mensal inicial",
            f"R$ {float(finops.get('initial_monthly_ecosystem_cap_brl') or 0):.0f}",
        )
        st.metric(
            "Limite inicial de alocação ao Trader",
            f"{float(finops.get('initial_max_trader_allocation_pct') or 0):.0f}%",
        )
        st.markdown("**Direção de caixa:**")
        st.markdown("- Negócios: principal fonte de financiamento do ecossistema.")
        st.markdown("- Trader: lucro líquido retido no próprio bucket Trader.")
        st.markdown("- Investimentos: construção e preservação patrimonial.")
        st.warning(
            "Metas de retorno do Trader são planejamento, não promessa nem retorno esperado. "
            "Backtest, risco e histórico real continuam obrigatórios."
        )
        st.caption(
            "Nenhum gasto, transferência, trade ou aumento de orçamento é executado por esta camada."
        )

    elif view == "26 · AION · Roteador dos 8 papéis":
        checkpoint = aion_master_checkpoint_bootstrap_snapshot()
        registry = aion_eight_role_registry(checkpoint)
        st.write(f"Estado: **{registry.get('state')}**")
        st.metric("Papéis internos", int(registry.get("role_count") or 0))
        st.markdown("**Um único AION, funções especializadas:**")
        for row in list(registry.get("roles") or []):
            st.markdown(
                f"- **{str(row.get('role_id') or '').replace('_', ' ').title()}** · "
                f"{', '.join(list(row.get('allowed_actions') or []))}"
            )
        st.warning(
            "Os papéis são lógicos e compartilham infraestrutura. "
            "Nenhum deles ganha autoridade para executar ação crítica."
        )
        st.caption(
            "O roteador ativa somente os papéis necessários para cada tarefa, "
            "com limite de custo e sem criar oito IAs independentes."
        )

    elif view == "27 · Oferta B2B & Receita":
        offer = business_priority_offer_template()
        priority = business_revenue_priority_snapshot()
        st.write(f"Estado: **{offer.get('state')}**")
        st.markdown(f"**Oferta prioritária:** {offer.get('label')}")
        st.markdown(f"**Modelo:** {offer.get('commercial_model')}")
        st.markdown("**Entregas-base:**")
        for item in list(offer.get("deliverables") or []):
            st.markdown(f"- {item}")
        st.info(
            "Preço não é inventado pelo AION. Ele é revisado a partir do custo real, "
            "margem mínima definida pelo administrador, capacidade e escopo."
        )
        st.warning(
            "Oferta pronta internamente não significa cliente contratado. "
            "Contato, proposta enviada, assinatura, cobrança e onboarding real continuam em gates separados."
        )
        st.caption(
            "Negócios permanece como motor de receita de curto prazo; "
            "dropshipping fora da prioridade e Trade não é necessário para bancar o ecossistema."
        )

    elif view == "28 · Primeiro Piloto & Preco":
        pilot = business_first_pilot_policy()
        st.write(f"Estado: **{pilot.get('state')}**")
        st.metric("Clientes no primeiro piloto", int(pilot.get("max_clients") or 0))
        st.metric("Duração máxima do primeiro piloto", f"{int(pilot.get('max_duration_days') or 0)} dias")
        st.markdown("**Antes da revisão administrativa do primeiro piloto:**")
        for item in (
            "candidato/segmento com fit mensurado",
            "permissão de contato revisada",
            "preço do piloto acima do piso sustentável",
            "margem mínima preservada",
            "oferta B2B pronta para revisão",
            "Pilot Governance com todos os gates",
        ):
            st.markdown(f"- {item}")
        st.warning(
            "O AION não escolhe o cliente nem o preço sozinho. "
            "O máximo desta camada é READY_FOR_ADMIN_FIRST_PILOT_REVIEW."
        )
        st.caption(
            "Contato, proposta enviada, contrato, cobrança, admissão do cliente e runtime "
            "permanecem bloqueados até gates separados."
        )

    elif view == "29 · Backup & Recovery":
        policy = aion_backup_recovery_policy()
        readiness = aion_audit_repository_backup_readiness()
        st.write(f"Política: **{policy.get('state')}**")
        st.write(f"Controles do repositório: **{readiness.get('state')}**")
        st.markdown("**Camadas obrigatórias:**")
        for item in list(policy.get("required_backup_layers") or []):
            st.markdown(f"- {item}")
        st.warning(
            "Restore automático permanece proibido. RPO/RTO ainda precisam ser definidos "
            "como metas administrativas, e a cópia secundária deve ser separada da referência primária."
        )
        st.caption(
            "O backup de código valida SHA256, testa o ZIP e confere arquivos críticos. "
            "O checkpoint de runtime continua versionado separadamente."
        )

    elif view == "30 · Indice de Independencia CLT":
        independence = aion_independence_policy()
        st.write(f"Estado: **{independence.get('state')}**")
        st.markdown("**O índice considera:**")
        for item in (
            "renda líquida não-Trade do ecossistema ao longo de vários meses",
            "faixa de segurança definida pelo administrador",
            "reserva financeira",
            "percentual de receita recorrente",
            "concentração no maior cliente",
            "dependência ou não do Trade para despesas essenciais",
        ):
            st.markdown(f"- {item}")
        st.warning(
            "O índice não é probabilidade e não recomenda sair do emprego. "
            "Ele apenas sinaliza quando existe evidência suficiente para uma revisão humana da transição."
        )
        st.caption(
            "Valores pessoais são entradas privadas de runtime e não ficam hardcoded no repositório."
        )

    else:
        binding = business_live_binding_policy()
        st.write(f"Estado: **{binding.get('state')}**")
        st.metric("Máximo por snapshot", int(binding.get("max_records_per_snapshot") or 0))
        st.metric("Idade padrão máxima", f"{float(binding.get('default_max_age_hours') or 0):.0f} h")
        st.markdown("**Fontes previstas em leitura:**")
        for source in list(binding.get("allowed_sources") or []):
            st.markdown(f"- {source}")
        st.warning(
            "Dados reais entram somente com origem atestada, tenant, timestamp e escopo read-only. "
            "PII bruta, credenciais e escrita externa são bloqueadas."
        )
        st.caption(
            "O AION pode observar contagens e estado comercial, mas não avança o CRM, "
            "não envia mensagem, não cobra e não inicia onboarding por esta camada."
        )


def _render_business(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 💼 AION Negócios")
    demo_snapshot = business_demo_snapshot()
    st.markdown(business_demo_html(), unsafe_allow_html=True)
    _render_business_master_readiness()
    _render_business_pilot_governance_demo()
    _render_business_stack_consolidation_v2()
    with st.expander("🎓 Treinamento do administrador · visão geral", expanded=False):
        st.caption(
            "Treinamento interno antes de divulgação. Entender primeiro, demonstrar depois e "
            "vender somente o que estiver validado."
        )
        for index, instruction in enumerate(demo_snapshot["training_steps"], start=1):
            st.markdown(f"**{index}.** {instruction}")
    _render_business_guided_training()
    _render_business_diagnostic_proposal_simulator()
    _render_business_client_portal_demo()
    _render_business_onboarding_demo()
    _render_business_customer_success_demo()
    _render_business_client_finance_demo()
    _render_business_trend_intelligence_demo()
    _render_business_commercial_acquisition_demo()
    _render_business_integration_hub_demo()
    _render_business_privacy_audit_demo()
    _render_persona_capabilities("business", {
        "catalog": True,
        "suppliers": True,
        "economics": True,
        "fees": True,
        "cac": True,
        "ltv": True,
        "funnel": True,
        "tracking": False,
        "reports": True,
    })
    st.write(
        "Central AION para soluções empresariais: Atrair → Atender → Converter → Reter. "
        "O foco principal agora é diagnóstico, implantação, pacotes recorrentes, Radar do Negócio, "
        "Portal do Cliente, resultados, suporte e expansão por módulos."
    )
    _context_voice(
        "Negócios",
        (
            "Bem-vindo ao AION Negócios. Aqui organizamos diagnóstico, atendimento, conversão, retenção, "
            "pacotes e resultados de forma simples para o cliente. O que é complexo fica por dentro do AION. "
            "Nenhuma automação externa é executada sem os gates e aprovações definidos."
        ),
        key="aion_business_voice",
    )

    business = checkpoint.get("business") if isinstance(checkpoint.get("business"), Mapping) else {}
    products = list(business.get("products", []) or [])
    metrics = normalize_business_metrics(
        business.get("metrics") if isinstance(business, Mapping) else {}
    )
    metric_views = business_metrics_views(metrics)
    summary = business_summary(products)

    st.markdown("#### Métricas Business")
    finance = metric_views["finance"]
    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric("Receita / faturamento", "N/D" if finance["revenue"] is None else f"R$ {finance['revenue']:.2f}")
    m2.metric("Custos", "N/D" if finance["costs"] is None else f"R$ {finance['costs']:.2f}")
    m3.metric("Lucro bruto", "N/D" if finance["gross_profit"] is None else f"R$ {finance['gross_profit']:.2f}")
    m4.metric("Lucro líquido", "N/D" if finance["net_profit"] is None else f"R$ {finance['net_profit']:.2f}")
    m5.metric("Caixa disponível", "N/D" if finance["available_cash"] is None else f"R$ {finance['available_cash']:.2f}")
    st.caption(
        f"Estado: {metrics['state']} · verdade: {metrics['truth_state']} · "
        f"fonte: {metrics['source'] or 'N/D'}. "
        "Receita, lucro bruto, lucro líquido e caixa disponível são métricas diferentes e nunca são intercambiadas."
    )

    def _metric_input_value(name):
        value=metrics.get(name)
        return None if value is None else float(value)

    with st.expander("Registrar métricas com proveniência"):
        with st.form("aion_business_metrics"):
            source=st.text_input("Fonte / referência das métricas",value=str(metrics.get("source") or ""))
            truth_state=st.selectbox(
                "Estado de verdade",
                list(BUSINESS_TRUTH_STATES),
                index=list(BUSINESS_TRUTH_STATES).index(str(metrics.get("truth_state") or "UNKNOWN"))
                if str(metrics.get("truth_state") or "UNKNOWN") in BUSINESS_TRUTH_STATES else 3,
            )
            f1,f2,f3,f4=st.columns(4)
            visits=f1.number_input("Visitas",min_value=0.0,value=_metric_input_value("visits"),step=1.0)
            leads=f2.number_input("Leads",min_value=0.0,value=_metric_input_value("leads"),step=1.0)
            checkouts=f3.number_input("Checkouts",min_value=0.0,value=_metric_input_value("checkouts"),step=1.0)
            orders=f4.number_input("Pedidos",min_value=0.0,value=_metric_input_value("orders"),step=1.0)
            e1,e2,e3,e4=st.columns(4)
            marketing_cost=e1.number_input("Custo de marketing",min_value=0.0,value=_metric_input_value("marketing_cost"),step=1.0)
            acquired_customers=e2.number_input("Clientes adquiridos",min_value=0.0,value=_metric_input_value("acquired_customers"),step=1.0)
            gross_profit_per_order=e3.number_input("Lucro bruto / pedido",min_value=0.0,value=_metric_input_value("gross_profit_per_order"),step=1.0)
            average_orders_per_customer=e4.number_input("Pedidos médios / cliente",min_value=0.0,value=_metric_input_value("average_orders_per_customer"),step=0.1)
            r1,r2,r3,r4,r5=st.columns(5)
            revenue=r1.number_input("Receita / faturamento",min_value=0.0,value=_metric_input_value("revenue"),step=10.0)
            total_costs=r2.number_input("Custos totais",min_value=0.0,value=_metric_input_value("costs"),step=10.0)
            gross_profit=r3.number_input("Lucro bruto",min_value=0.0,value=_metric_input_value("gross_profit"),step=10.0)
            net_profit=r4.number_input("Lucro líquido",min_value=0.0,value=_metric_input_value("net_profit"),step=10.0)
            available_cash=r5.number_input("Caixa disponível",min_value=0.0,value=_metric_input_value("available_cash"),step=10.0)
            save_metrics=st.form_submit_button("Salvar métricas na sessão",type="primary")
        if save_metrics:
            record=new_business_metrics(
                source=source,
                truth_state=truth_state,
                recorded_by=str(access.get("username") or "ADMIN"),
                visits=visits,
                leads=leads,
                checkouts=checkouts,
                orders=orders,
                marketing_cost=marketing_cost,
                acquired_customers=acquired_customers,
                gross_profit_per_order=gross_profit_per_order,
                average_orders_per_customer=average_orders_per_customer,
                revenue=revenue,
                costs=total_costs,
                gross_profit=gross_profit,
                net_profit=net_profit,
                available_cash=available_cash,
            )
            updated=update_business_checkpoint(
                checkpoint,
                products=products,
                metrics=record,
                dirty=True,
            )
            updated=_record_working_event(
                updated,
                "business_metrics_updated",
                "Métricas Business atualizadas na memória de trabalho.",
                evidence={
                    "truth_state":record["truth_state"],
                    "source":record["source"],
                },
            )
            _set_working_checkpoint(updated,dirty=True)
            st.success(
                "Métricas salvas na sessão. Alterações pendentes até o ADMIN salvar "
                "e confirmar o Checkpoint Mestre."
            )
            st.rerun()

    st.markdown("#### Sustentabilidade do AtlasQuant · simulação não persistida")
    system_cost = st.number_input(
        "Custo mensal alvo do ecossistema (USD)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="aion_business_cost",
    )
    net_profit_sim = st.number_input(
        "Lucro líquido de vendas usado na simulação (USD)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="aion_business_revenue",
    )
    coverage=coverage_snapshot(system_cost,net_profit_sim)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Produtos pesquisados",summary["total"])
    c2.metric("Margem positiva",summary["positive_margin_candidates"])
    c3.metric("Tendências confirmadas",summary["confirmed_trends"])
    c4.metric("Cobertura", "N/D" if coverage["coverage_pct"] is None else f"{coverage['coverage_pct']:.1f}%")
    st.progress(0 if coverage["coverage_pct"] is None else min(100,int(round(coverage["coverage_pct"]))))
    st.caption(
        "Esta simulação usa entradas manuais da sessão e não representa faturamento, lucro ou caixa "
        "confirmados de marketplace. Esses valores não representam vendas confirmadas enquanto "
        "integrações de pedidos não estiverem conectadas. Nenhuma movimentação financeira é executada."
    )
    with st.expander("Funil, CAC, LTV, afiliados e tracking"):
        funnel=metric_views["funnel"]
        customers=metric_views["customers"]
        order_rate="N/D" if funnel["order_rate_pct"] is None else f"{funnel['order_rate_pct']:.2f}%"
        st.dataframe([
            {"Indicador":"Visitas → pedidos","Valor":order_rate,"Estado":funnel["state"]},
            {"Indicador":"CAC","Valor":"N/D" if customers["cac"] is None else customers["cac"],"Estado":customers["state"]},
            {"Indicador":"LTV","Valor":"N/D" if customers["ltv"] is None else customers["ltv"],"Estado":customers["state"]},
            {"Indicador":"Afiliados/comissões","Valor":"N/D","Estado":"NOT_CONFIGURED"},
            {"Indicador":"Tracking de campanha","Valor":"N/D","Estado":"NOT_CONFIGURED"},
        ],width="stretch",hide_index=True)
        st.caption(
            "Funil, CAC e LTV só ficam READY com dados completos e fonte confirmada. "
            "Nenhuma campanha, gasto, comissão ou publicação é executada."
        )

    st.markdown("#### Compatibilidade legada · Marketplace / pesquisa de produto")
    st.caption(
        "Este bloco histórico permanece temporariamente para compatibilidade e auditoria. "
        "Dropshipping, afiliados, Shopee, Mercado Livre, TikTok Shop e e-commerce genérico "
        "não são mais o foco principal da nova aba Negócios. "
        "Nenhum produto é chamado de tendência ou mais vendido sem fonte confirmada."
    )
    st.markdown("#### Candidato de produto")
    with st.form("aion_business_new_product", clear_on_submit=True):
        name=st.text_input("Produto")
        channel=st.selectbox("Canal",list(BUSINESS_CHANNELS))
        supplier=st.text_input("Fornecedor / referência")
        ev1,ev2=st.columns(2)
        evidence_source=ev1.text_input("Fonte da pesquisa")
        evidence_truth=ev2.selectbox("Estado da evidência",list(BUSINESS_TRUTH_STATES),index=3)
        evidence_url=st.text_input("URL / referência da fonte")
        trend_note=st.text_area(
            "O que a fonte mostra sobre tendência/demanda",
            max_chars=1200,
            help="Se a fonte não confirmar, use UNKNOWN/INFERENCE/HYPOTHESIS.",
        )
        cprice,ccost=st.columns(2)
        sale_price=cprice.number_input("Preço de venda estimado (R$)",min_value=0.0,value=0.0,step=1.0)
        unit_cost=ccost.number_input("Custo unitário (R$)",min_value=0.0,value=0.0,step=1.0)
        cfee,cship,ctax=st.columns(3)
        fee=cfee.number_input("Taxa plataforma (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5)
        shipping=cship.number_input("Frete/custo logístico (R$)",min_value=0.0,value=0.0,step=1.0)
        tax=ctax.number_input("Impostos estimados (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5)
        other=st.number_input("Outros custos por unidade (R$)",min_value=0.0,value=0.0,step=1.0)
        create_product=st.form_submit_button("Adicionar à pesquisa de produtos",type="primary")
    if create_product:
        try:
            product=new_product_candidate(
                name,
                channel=channel,
                evidence_source=evidence_source,
                evidence_url=evidence_url,
                evidence_truth=evidence_truth,
                trend_note=trend_note,
                supplier=supplier,
                sale_price=sale_price,
                unit_cost=unit_cost,
                platform_fee_pct=fee,
                shipping_cost=shipping,
                tax_pct=tax,
                other_cost=other,
                source=str(access.get("username") or "ADMIN"),
            )
            products=upsert_product(products,product)
            updated=update_business_checkpoint(checkpoint,products=products,dirty=True)
            updated=_record_working_event(
                updated,
                "business_product_added",
                f"Produto adicionado à pesquisa: {product['name']}",
                evidence={
                    "product_id":product["product_id"],
                    "channel":product["channel"],
                    "truth_state":product["research"]["truth_state"],
                },
            )
            _set_working_checkpoint(updated,dirty=True)
            st.success("Produto salvo na memória de trabalho de Negócios.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível salvar o produto: {type(exc).__name__}")

    if products:
        rows=[]
        for product in products:
            econ=product.get("economics") or {}
            trend=trend_assessment(product)
            rows.append({
                "ID":product.get("product_id"),
                "Status":product.get("status"),
                "Produto":product.get("name"),
                "Canal":product.get("channel"),
                "Evidência":(product.get("research") or {}).get("truth_state"),
                "Tendência confirmada":trend.get("can_call_trending"),
                "Lucro/unid. R$":econ.get("net_profit"),
                "Margem %":econ.get("net_margin_pct"),
            })
        st.dataframe(rows,width="stretch",hide_index=True)
        selected_id=st.selectbox(
            "Produto selecionado",
            [str(p.get("product_id")) for p in products],
            key="aion_business_selected_product",
        )
        selected=next((p for p in products if str(p.get("product_id"))==selected_id),None)
        if isinstance(selected,Mapping):
            trend=trend_assessment(selected)
            econ=selected.get("economics") or {}
            st.write(
                f"**Economia unitária:** lucro R$ {float(econ.get('net_profit') or 0):.2f} · "
                f"margem {float(econ.get('net_margin_pct') or 0):.2f}% · "
                f"ROI sobre custo {float(econ.get('roi_on_unit_cost_pct') or 0):.2f}%."
            )
            if trend["can_call_trending"]:
                st.success(f"Tendência confirmada pela fonte registrada: {trend['message']}")
            else:
                st.warning(trend["message"])

            if st.button("✅ Aprovar produto para próxima etapa",key="aion_business_approve"):
                try:
                    approved=approve_product(selected,access)
                    products=upsert_product(products,approved)
                    updated=update_business_checkpoint(checkpoint,products=products,dirty=True)
                    updated=_record_working_event(
                        updated,
                        "business_product_approved",
                        f"Produto aprovado para próxima etapa: {approved['product_id']}",
                        evidence={"product_id":approved["product_id"]},
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight=marketplace_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            st.caption(
                f"Marketplace: {'PRONTO PARA CONECTOR' if preflight['allowed'] else 'BLOQUEADO'} · "
                f"{preflight['reason']}"
            )
    else:
        st.info("Nenhum candidato de produto registrado.")

    st.warning(
        "Publicação em marketplace está "
        + ("HABILITADA POR FLAG, mas ainda exige Guardian e conector real." if flags.get("marketplace_publish") else "DESLIGADA por feature flag.")
    )


def _render_laboratory(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    incident_snapshot: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🧪 Laboratório / Sandbox")
    _render_persona_capabilities("laboratory", {
        "matrix": True,
        "evidence": True,
        "history": True,
        "comparisons": True,
        "setups": True,
        "assets": True,
        "timeframes": True,
        "styles": True,
    })
    st.write(
        "Toda novidade nasce aqui, com isolamento, teste, evidência e rollback antes de qualquer promoção."
    )
    _context_voice(
        "Laboratório",
        (
            "Bem-vindo ao Laboratório AION. Toda novidade passa por Sandbox, teste, evidência e rollback "
            "antes de avançar. Feature flags externas começam desligadas."
        ),
        key="aion_laboratory_voice",
    )
    try:
        render_replay_lab_panel(checkpoint)
    except Exception as exc:
        st.warning("Modo Replay indisponível; nenhum cenário histórico foi fabricado.")
        st.caption(
            f"Diagnóstico seguro: {type(exc).__name__} · treinamento somente · execução real bloqueada."
        )
    try:
        from atlasquant_lab_matrix_panel import render_lab_matrix_panel
        render_lab_matrix_panel()
    except Exception as exc:
        st.warning("Matriz de evidências indisponível; nenhum resultado foi inferido.")
        st.caption(f"Diagnóstico seguro: {type(exc).__name__}")

    learning = checkpoint.get("learning") if isinstance(checkpoint.get("learning"), Mapping) else {}
    episodes = list(learning.get("episodes", []) or [])
    experiments = list(learning.get("experiments", []) or [])
    research_refs = list(learning.get("research_refs", []) or [])
    learning_state = learning_summary(episodes, experiments, research_refs)
    calibration_state = confidence_calibration(episodes)
    error_state = error_pattern_summary(episodes)
    wisdom = checkpoint.get("wisdom") if isinstance(checkpoint.get("wisdom"), Mapping) else {}
    wisdom_entries = list(wisdom.get("entries", []) or [])
    wisdom_state = wisdom_summary(wisdom_entries)

    graph = checkpoint.get("knowledge_graph") if isinstance(checkpoint.get("knowledge_graph"), Mapping) else {}
    graph_state = knowledge_graph_summary(graph)
    eval_lab = checkpoint.get("evaluation_lab") if isinstance(checkpoint.get("evaluation_lab"), Mapping) else {}
    eval_state = evaluation_lab_summary(eval_lab)

    st.markdown("#### 🕸️ Knowledge Graph + Evaluation Lab")
    st.caption(
        "O grafo organiza relações explícitas entre lições, episódios, evidências e versões. "
        "O Evaluation Lab exige evidência e não-regressão antes de uma versão sequer virar candidata à revisão humana."
    )
    kg1,kg2,kg3,kg4 = st.columns(4)
    kg1.metric("Nós de conhecimento", int(graph_state.get("nodes") or 0))
    kg2.metric("Relações", int(graph_state.get("edges") or 0))
    kg3.metric("Suites de avaliação", int(eval_state.get("suites") or 0))
    kg4.metric("Candidatos à revisão", int(eval_state.get("human_review_candidates") or 0))

    if st.button(
        "Sincronizar Knowledge Graph com memória registrada",
        key="aion_graph_sync",
        width="stretch",
    ):
        updated=synchronize_knowledge_graph_checkpoint(checkpoint,dirty=True)
        updated=_record_working_event(
            updated,
            "knowledge_graph_synchronized",
            "Knowledge Graph sincronizado a partir de relações explícitas do Checkpoint.",
            evidence={
                "semantic_inference_automatic":False,
                "causality_inferred_automatically":False,
            },
        )
        _set_working_checkpoint(updated,dirty=True)
        st.success("Grafo sincronizado na memória de trabalho; nenhuma relação sem fonte explícita foi criada.")
        st.rerun()

    with st.expander("Consultar Knowledge Graph", expanded=False):
        graph_query=st.text_input(
            "Buscar nó/relação",
            key="aion_graph_query",
            placeholder="Ex.: Payroll, Guardian, Liquidity",
        )
        if graph_query.strip():
            neighborhood=graph_neighborhood(graph,graph_query,limit=25)
            st.caption(
                f"Nós encontrados: {int(neighborhood.get('matched_nodes') or 0)} · "
                "consulta somente leitura."
            )
            if neighborhood.get("nodes"):
                st.dataframe([
                    {
                        "Tipo":item.get("node_type"),
                        "Nó":item.get("label"),
                        "Verdade":item.get("truth_state"),
                        "Domínio":item.get("domain"),
                        "ID":item.get("node_id"),
                    }
                    for item in neighborhood.get("nodes",[])
                    if isinstance(item,Mapping)
                ],width="stretch",hide_index=True)
            if neighborhood.get("edges"):
                st.dataframe([
                    {
                        "Origem":item.get("source_id"),
                        "Relação":item.get("relation"),
                        "Destino":item.get("target_id"),
                        "Verdade":item.get("truth_state"),
                    }
                    for item in neighborhood.get("edges",[])
                    if isinstance(item,Mapping)
                ],width="stretch",hide_index=True)

    suites=[
        dict(item) for item in list(eval_lab.get("suites",[]) or [])
        if isinstance(item,Mapping)
    ]
    eval_runs=[
        dict(item) for item in list(eval_lab.get("runs",[]) or [])
        if isinstance(item,Mapping)
    ]
    with st.expander("Evaluation Lab · não-regressão", expanded=False):
        st.caption(
            "Uma nova versão não é considerada melhor por opinião. Sem casos, métricas e evidências, "
            "o estado permanece NEED_MORE_EVIDENCE. Promoção automática: NÃO."
        )
        if suites:
            suite_map={
                f"{item.get('name')} · {item.get('suite_id')}":item
                for item in suites
            }
            suite_label=st.selectbox(
                "Suite",
                list(suite_map.keys()),
                key="aion_eval_suite_selected",
            )
            selected_suite=suite_map[suite_label]
            st.dataframe([
                {
                    "Caso":case.get("title"),
                    "Categoria":case.get("category"),
                    "Criticidade":case.get("criticality"),
                    "ID":case.get("case_id"),
                }
                for case in list(selected_suite.get("cases",[]) or [])
                if isinstance(case,Mapping)
            ],width="stretch",hide_index=True)

            with st.form("aion_eval_new_run",clear_on_submit=True):
                baseline_version=st.text_input("Versão atual / baseline",value="AION-CURRENT")
                candidate_version=st.text_input("Versão candidata",placeholder="Ex.: AION-VNEXT")
                create_eval_run=st.form_submit_button("Registrar avaliação planejada")
            if create_eval_run:
                try:
                    run=new_eval_run(
                        selected_suite,
                        baseline_version=baseline_version,
                        candidate_version=candidate_version,
                        case_results=[],
                        baseline_metrics={},
                        candidate_metrics={},
                        evidence_refs=[],
                    )
                    eval_runs=upsert_run(eval_runs,run)
                    lab_updated=dict(eval_lab)
                    lab_updated["runs"]=eval_runs
                    updated=update_evaluation_lab_checkpoint(
                        checkpoint,evaluation_lab=lab_updated,dirty=True,
                    )
                    updated=_record_working_event(
                        updated,
                        "evaluation_run_registered",
                        f"Avaliação planejada registrada: {run['run_id']}",
                        evidence={
                            "run_id":run["run_id"],
                            "baseline":run["baseline_version"],
                            "candidate":run["candidate_version"],
                            "automatic_promotion":False,
                        },
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.success("Avaliação planejada registrada; ainda sem evidência suficiente.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível registrar a avaliação: {type(exc).__name__}")

        if eval_runs:
            st.dataframe([
                {
                    "Run":item.get("run_id"),
                    "Baseline":item.get("baseline_version"),
                    "Candidato":item.get("candidate_version"),
                    "Estado":item.get("state"),
                    "Revisão humana":"SIM" if item.get("requires_human_review",True) else "NÃO",
                }
                for item in reversed(eval_runs[-80:])
            ],width="stretch",hide_index=True)
            run_map={
                f"{item.get('run_id')} · {item.get('candidate_version')}":item
                for item in eval_runs
            }
            selected_run_label=st.selectbox(
                "Avaliação para reprocessar evidências já registradas",
                list(run_map.keys()),
                key="aion_eval_run_selected",
            )
            selected_run=run_map[selected_run_label]
            suite_for_run=next(
                (item for item in suites if str(item.get("suite_id") or "")==str(selected_run.get("suite_id") or "")),
                None,
            )
            if isinstance(suite_for_run,Mapping) and st.button(
                "Avaliar evidências registradas",
                key="aion_eval_run_evaluate",
                width="stretch",
            ):
                try:
                    evaluated=evaluate_run(suite_for_run,selected_run)
                    eval_runs=upsert_run(eval_runs,evaluated)
                    lab_updated=dict(eval_lab)
                    lab_updated["runs"]=eval_runs
                    updated=update_evaluation_lab_checkpoint(
                        checkpoint,evaluation_lab=lab_updated,dirty=True,
                    )
                    updated=_record_working_event(
                        updated,
                        "evaluation_run_evaluated",
                        f"Evaluation Lab processou: {evaluated['run_id']}",
                        evidence={
                            "run_id":evaluated["run_id"],
                            "state":evaluated["state"],
                            "automatic_promotion":False,
                            "production_change_allowed":False,
                        },
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.success(
                        f"Evaluation Lab: {evaluated['state']}. "
                        "Nenhuma promoção ou deploy foi executado."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"A avaliação não pôde ser processada: {type(exc).__name__}")

    st.markdown("#### 🧠 Aprendizado Controlado AION")
    st.caption(
        "Ciclo: registrar previsão → observar resultado → medir erro/acerto → revisar causa → "
        "calibrar confiança → testar Challenger fora da amostra → Shadow Mode → revisão humana. "
        "Nada altera peso, regra ou produção automaticamente."
    )
    l1,l2,l3,l4 = st.columns(4)
    l1.metric("Episódios", int(learning_state.get("episodes") or 0))
    l2.metric("Em aberto", int(learning_state.get("open_episodes") or 0))
    l3.metric("Erros observados", int(learning_state.get("errors") or 0))
    l4.metric(
        "Gap de calibração",
        "—" if learning_state.get("calibration_gap_pct") is None
        else f"{float(learning_state.get('calibration_gap_pct')):.1f}%",
    )
    st.caption(
        f"Calibração: {learning_state.get('calibration_state','INSUFFICIENT')} · "
        f"evidências de pesquisa referenciadas: {int(learning_state.get('research_references') or 0)} · "
        f"candidatos para revisão humana: {int(learning_state.get('human_review_candidates') or 0)}."
    )

    with st.expander("Registrar previsão / decisão para aprender depois", expanded=False):
        with st.form("aion_learning_new_episode", clear_on_submit=True):
            subject = st.text_input("Assunto", placeholder="Ex.: reação do USD ao Payroll")
            forecast_type = st.selectbox(
                "Tipo",
                list(LEARNING_FORECAST_TYPES),
                key="aion_learning_forecast_type",
            )
            prediction = st.text_input("Previsão / categoria", placeholder="Ex.: USD_UP")
            confidence_pct = st.slider(
                "Confiança da previsão (não é probabilidade de lucro)",
                0, 100, 50,
            )
            model_version = st.text_input("Versão do modelo / regra", value="AION")
            context_note = st.text_area("Contexto registrado", max_chars=1200)
            refs_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                placeholder="calendar:event-1, backtest:snapshot-3",
            )
            numeric_prediction = None
            numeric_tolerance = None
            if forecast_type == "NUMERIC":
                n1,n2 = st.columns(2)
                numeric_prediction = n1.number_input(
                    "Valor previsto", value=0.0, step=0.1,
                )
                numeric_tolerance = n2.number_input(
                    "Tolerância para considerar acerto", min_value=0.0, value=0.0, step=0.1,
                )
            create_episode = st.form_submit_button("Registrar episódio", type="primary")
        if create_episode:
            try:
                episode = new_learning_episode(
                    subject,
                    forecast_type=forecast_type,
                    prediction=prediction,
                    confidence_pct=confidence_pct,
                    model_version=model_version,
                    evidence_refs=[x.strip() for x in refs_text.split(",") if x.strip()],
                    context_note=context_note,
                    numeric_prediction=numeric_prediction,
                    numeric_tolerance=numeric_tolerance,
                    source=str(access.get("username") or "ADMIN"),
                )
                episodes = upsert_learning_episode(episodes, episode)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                updated = _record_working_event(
                    updated,
                    "learning_episode_registered",
                    f"Episódio de aprendizado registrado: {episode['subject']}",
                    evidence={
                        "episode_id":episode["episode_id"],
                        "forecast_type":episode["forecast_type"],
                        "automatic_rule_change":False,
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Episódio registrado na memória de trabalho. Salve o Checkpoint Mestre para persistir.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar o episódio: {type(exc).__name__}")

    open_episodes = [
        item for item in episodes
        if isinstance(item, Mapping) and str(item.get("state") or "").upper()=="OPEN"
    ]
    if open_episodes:
        with st.expander("Registrar resultado real / fechar episódio", expanded=False):
            episode_options = {
                f"{item.get('episode_id')} · {item.get('subject')}": item
                for item in open_episodes
            }
            selected_label = st.selectbox(
                "Episódio em aberto",
                list(episode_options.keys()),
                key="aion_learning_settle_episode",
            )
            selected_episode = episode_options[selected_label]
            with st.form("aion_learning_settle_form"):
                actual_outcome = st.text_input(
                    "Resultado real / categoria observada",
                    placeholder="Ex.: USD_DOWN",
                )
                actual_numeric = None
                if str(selected_episode.get("forecast_type") or "")=="NUMERIC":
                    actual_numeric = st.number_input(
                        "Valor real observado", value=0.0, step=0.1,
                    )
                cause = st.selectbox(
                    "Causa do erro, se houver",
                    list(LEARNING_CAUSE_TAGS),
                    index=list(LEARNING_CAUSE_TAGS).index("UNKNOWN"),
                )
                cause_confirmed = st.checkbox(
                    "A causa acima tem evidência confirmada",
                    value=False,
                    help="Sem esta confirmação o AION guarda a causa como hipótese/desconhecida, não como fato.",
                )
                outcome_note = st.text_area("Observação do resultado", max_chars=1200)
                settle_episode = st.form_submit_button("Fechar episódio", type="primary")
            if settle_episode:
                try:
                    settled = settle_learning_episode(
                        selected_episode,
                        actual_outcome=actual_outcome,
                        actual_numeric=actual_numeric,
                        error_cause=cause,
                        error_cause_confirmed=cause_confirmed,
                        outcome_note=outcome_note,
                    )
                    episodes = upsert_learning_episode(episodes, settled)
                    updated = update_learning_checkpoint(
                        checkpoint,
                        episodes=episodes,
                        experiments=experiments,
                        research_refs=research_refs,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "learning_episode_settled",
                        f"Episódio de aprendizado fechado: {settled['subject']}",
                        evidence={
                            "episode_id":settled["episode_id"],
                            "evaluation":settled["evaluation"],
                            "error_cause_truth":settled["error_cause_truth"],
                            "automatic_weight_change":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success("Resultado registrado sem alterar regras ou pesos automaticamente.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível fechar o episódio: {type(exc).__name__}")

    with st.expander("Registrar evidência de Backtest / Paper / Shadow", expanded=False):
        with st.form("aion_learning_research_ref", clear_on_submit=True):
            research_kind = st.selectbox("Tipo de evidência", list(LEARNING_RESEARCH_KINDS))
            research_ref_id = st.text_input(
                "ID / referência", placeholder="Ex.: snapshot-id ou arquivo/relatório",
            )
            research_strategy = st.text_input("Operacional / estratégia")
            research_summary_text = st.text_area("Resumo da evidência", max_chars=1000)
            save_research = st.form_submit_button("Vincular evidência")
        if save_research:
            try:
                ref = new_research_reference(
                    research_kind,
                    research_ref_id,
                    strategy=research_strategy,
                    summary=research_summary_text,
                )
                known_ids = {str(x.get("research_id") or "") for x in research_refs if isinstance(x, Mapping)}
                if ref["research_id"] not in known_ids:
                    research_refs.append(ref)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Evidência vinculada por referência; nenhum resultado de pesquisa alterou o gate ao vivo.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível vincular a evidência: {type(exc).__name__}")

    with st.expander("Champion × Challenger · promoção controlada", expanded=False):
        st.caption(
            "O Challenger nunca substitui o Champion automaticamente. Primeiro precisa de OOS, "
            "não degradação, Shadow Mode e depois revisão humana."
        )
        with st.form("aion_learning_new_experiment", clear_on_submit=True):
            champion_version = st.text_input("Champion atual")
            challenger_version = st.text_input("Challenger")
            rationale = st.text_area("Hipótese de melhoria", max_chars=1200)
            create_experiment = st.form_submit_button("Criar experimento")
        if create_experiment:
            try:
                experiment = new_learning_experiment(
                    champion_version,
                    challenger_version,
                    rationale=rationale,
                )
                experiments = upsert_learning_experiment(experiments, experiment)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Challenger registrado como hipótese. Produção não foi alterada.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível criar o experimento: {type(exc).__name__}")

        if experiments:
            exp_options = {
                f"{item.get('experiment_id')} · {item.get('champion_version')} → {item.get('challenger_version')}": item
                for item in experiments if isinstance(item, Mapping)
            }
            selected_exp_label = st.selectbox(
                "Experimento",
                list(exp_options.keys()),
                key="aion_learning_experiment_selected",
            )
            selected_exp = exp_options[selected_exp_label]
            with st.form("aion_learning_evaluate_experiment"):
                st.markdown("**Métricas fora da amostra / Shadow**")
                c1,c2 = st.columns(2)
                champ_exp = c1.number_input("Champion · expectancy R", value=0.0, step=0.01)
                chall_exp = c2.number_input("Challenger · expectancy R", value=0.0, step=0.01)
                c3,c4 = st.columns(2)
                champ_dd = c3.number_input("Champion · drawdown R", min_value=0.0, value=0.0, step=0.1)
                chall_dd = c4.number_input("Challenger · drawdown R", min_value=0.0, value=0.0, step=0.1)
                c5,c6 = st.columns(2)
                champ_cal = c5.number_input("Champion · erro calibração %", min_value=0.0, value=0.0, step=0.5)
                chall_cal = c6.number_input("Challenger · erro calibração %", min_value=0.0, value=0.0, step=0.5)
                c7,c8 = st.columns(2)
                champ_false = c7.number_input("Champion · falso alerta %", min_value=0.0, value=0.0, step=0.5)
                chall_false = c8.number_input("Challenger · falso alerta %", min_value=0.0, value=0.0, step=0.5)
                oos_samples = st.number_input("Amostras OOS do Challenger", min_value=0, value=0, step=10)
                shadow_eligible = st.checkbox("Shadow elegível para revisão manual", value=False)
                critical_mismatches = st.number_input("Divergências críticas no Shadow", min_value=0, value=0, step=1)
                evaluate_experiment = st.form_submit_button("Avaliar Challenger")
            if evaluate_experiment:
                evaluated = evaluate_learning_experiment(
                    selected_exp,
                    champion_metrics={
                        "expectancy_r":champ_exp,
                        "max_drawdown_r":champ_dd,
                        "calibration_error_pct":champ_cal,
                        "false_alert_rate_pct":champ_false,
                    },
                    challenger_metrics={
                        "oos_samples":oos_samples,
                        "expectancy_r":chall_exp,
                        "max_drawdown_r":chall_dd,
                        "calibration_error_pct":chall_cal,
                        "false_alert_rate_pct":chall_false,
                    },
                    shadow_summary={
                        "eligible_for_manual_review":shadow_eligible,
                        "critical_mismatches":critical_mismatches,
                    },
                )
                experiments = upsert_learning_experiment(experiments, evaluated)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                state = str(evaluated.get("state") or "UNKNOWN")
                if state=="HUMAN_REVIEW_CANDIDATE":
                    st.success("Challenger atingiu critérios mínimos para REVISÃO HUMANA. Promoção automática continua proibida.")
                else:
                    st.warning(f"Challenger permaneceu em {state}. Champion continua oficial.")
                st.rerun()

    if episodes:
        with st.expander("Diário de aprendizado", expanded=False):
            st.dataframe([
                {
                    "ID":item.get("episode_id"),
                    "Estado":item.get("state"),
                    "Assunto":item.get("subject"),
                    "Tipo":item.get("forecast_type"),
                    "Previsão":item.get("prediction"),
                    "Confiança":item.get("forecast_confidence_pct"),
                    "Resultado":item.get("actual_outcome"),
                    "Avaliação":item.get("evaluation"),
                    "Causa":item.get("error_cause"),
                    "Causa confirmada":item.get("error_cause_truth"),
                    "Versão":item.get("model_version"),
                }
                for item in reversed(episodes[-200:]) if isinstance(item, Mapping)
            ], width="stretch", hide_index=True)

    if calibration_state.get("samples"):
        with st.expander("Calibração da confiança", expanded=False):
            st.dataframe([
                {
                    "Faixa":row.get("band"),
                    "Amostras":row.get("samples"),
                    "Confiança média %":row.get("average_confidence_pct"),
                    "Acerto observado %":row.get("observed_accuracy_pct"),
                    "Gap %":row.get("absolute_calibration_gap_pct"),
                }
                for row in list(calibration_state.get("bands") or [])
            ], width="stretch", hide_index=True)
            st.caption(
                "Auto-recalibração de pesos: DESATIVADA. A taxa observada não é probabilidade de lucro futuro."
            )

    confirmed_causes = error_state.get("confirmed_cause_counts") if isinstance(error_state.get("confirmed_cause_counts"), Mapping) else {}
    if confirmed_causes:
        st.caption(
            "Causas de erro confirmadas mais recorrentes: "
            + " · ".join(f"{k}: {v}" for k,v in list(confirmed_causes.items())[:6])
        )
    if int(error_state.get("errors_without_confirmed_cause") or 0):
        st.info(
            f"{int(error_state.get('errors_without_confirmed_cause') or 0)} erro(s) ainda sem causa confirmada. "
            "O AION não inventará causalidade para preencher essa lacuna."
        )

    st.markdown("#### 📚 Diário de Sabedoria AION")
    st.caption(
        "Transforma experiência revisada em conhecimento auditável: o que foi aprendido, "
        "origem, estado de verdade, confiança, aplicação e quando precisa ser revisado. "
        "Sabedoria não altera regra, peso ou produção automaticamente."
    )
    w1,w2,w3,w4 = st.columns(4)
    w1.metric("Lições", int(wisdom_state.get("entries") or 0))
    w2.metric("Ativas", int(wisdom_state.get("active") or 0))
    w3.metric(
        "Confirmadas",
        int((wisdom_state.get("by_truth_state") or {}).get("CONFIRMED") or 0),
    )
    w4.metric("Revisão vencida", int(wisdom_state.get("review_due") or 0))

    with st.expander("Registrar uma lição revisada", expanded=False):
        with st.form("aion_wisdom_new_entry", clear_on_submit=True):
            wisdom_topic = st.text_input("Tema da lição")
            wisdom_domain = st.text_input("Domínio", value="general")
            wisdom_insight = st.text_area("O que foi aprendido", max_chars=1400)
            wisdom_truth = st.selectbox(
                "Estado de verdade",
                list(WISDOM_TRUTH_STATES),
                index=list(WISDOM_TRUTH_STATES).index("HYPOTHESIS"),
            )
            wisdom_confidence = st.slider(
                "Confiança no conhecimento (não é probabilidade de lucro)",
                0, 100, 50,
                key="aion_wisdom_confidence",
            )
            wisdom_refs_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                placeholder="repo:test-123, calendar:cpi-1",
            )
            wisdom_applies_text = st.text_input(
                "Aplica-se a (separado por vírgula)",
                placeholder="USD, macro, CPI",
            )
            wisdom_review_due = st.text_input(
                "Revisar em (ISO opcional)",
                placeholder="2026-12-31T00:00:00+00:00",
            )
            wisdom_validation_note = st.text_area(
                "Nota de validação",
                max_chars=1200,
            )
            save_wisdom = st.form_submit_button("Registrar no Diário de Sabedoria", type="primary")
        if save_wisdom:
            try:
                entry = new_wisdom_entry(
                    wisdom_topic,
                    wisdom_insight,
                    domain=wisdom_domain,
                    truth_state=wisdom_truth,
                    confidence_pct=wisdom_confidence,
                    evidence_refs=[x.strip() for x in wisdom_refs_text.split(",") if x.strip()],
                    applies_to=[x.strip() for x in wisdom_applies_text.split(",") if x.strip()],
                    validation_note=wisdom_validation_note,
                    validated_at=datetime.now(timezone.utc).isoformat(),
                    review_due_at=wisdom_review_due,
                    created_by=str(access.get("username") or "ADMIN"),
                )
                wisdom_entries = upsert_wisdom_entry(wisdom_entries, entry)
                updated = update_wisdom_checkpoint(
                    checkpoint,
                    entries=wisdom_entries,
                    dirty=True,
                )
                updated = _record_working_event(
                    updated,
                    "wisdom_entry_registered",
                    f"Lição registrada no Diário de Sabedoria: {entry['topic']}",
                    evidence={
                        "wisdom_id":entry["wisdom_id"],
                        "truth_state":entry["truth_state"],
                        "manual_review_required":True,
                        "automatic_rule_change":False,
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success(
                    "Lição registrada na memória de trabalho. "
                    "Salve o Checkpoint Mestre para persistir."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar a lição: {type(exc).__name__}")

    settled_for_wisdom = [
        item for item in episodes
        if isinstance(item, Mapping) and str(item.get("state") or "").upper()=="SETTLED"
    ]
    if settled_for_wisdom:
        with st.expander("Propor sabedoria a partir de um episódio fechado", expanded=False):
            wisdom_episode_options = {
                f"{item.get('episode_id')} · {item.get('subject')}": item
                for item in settled_for_wisdom[-200:]
            }
            wisdom_episode_label = st.selectbox(
                "Episódio SETTLED",
                list(wisdom_episode_options.keys()),
                key="aion_wisdom_episode_candidate",
            )
            wisdom_candidate_due = st.text_input(
                "Revisar candidato em (ISO opcional)",
                placeholder="2026-12-31T00:00:00+00:00",
                key="aion_wisdom_candidate_due",
            )
            if st.button(
                "Criar candidato de sabedoria",
                key="aion_wisdom_candidate_create",
                width="stretch",
            ):
                try:
                    candidate = candidate_from_learning_episode(
                        wisdom_episode_options[wisdom_episode_label],
                        created_by=str(access.get("username") or "ADMIN"),
                        review_due_at=wisdom_candidate_due,
                    )
                    wisdom_entries = upsert_wisdom_entry(wisdom_entries, candidate)
                    updated = update_wisdom_checkpoint(
                        checkpoint,
                        entries=wisdom_entries,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "wisdom_candidate_created",
                        f"Candidato de sabedoria criado: {candidate['topic']}",
                        evidence={
                            "wisdom_id":candidate["wisdom_id"],
                            "truth_state":candidate["truth_state"],
                            "source_episode_ids":candidate["source_episode_ids"],
                            "automatic_promotion":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success(
                        "Candidato criado. Ele não foi promovido a CONFIRMED automaticamente."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível criar o candidato: {type(exc).__name__}")

    if wisdom_entries:
        with st.expander("Ver Diário de Sabedoria", expanded=False):
            st.dataframe([
                {
                    "ID":item.get("wisdom_id"),
                    "Estado":item.get("state"),
                    "Tema":item.get("topic"),
                    "Domínio":item.get("domain"),
                    "Verdade":item.get("truth_state"),
                    "Confiança":item.get("confidence_pct"),
                    "Revisão":wisdom_review_state(item),
                    "Revisar em":item.get("review_due_at") or "—",
                    "Origem":", ".join(item.get("source_episode_ids") or []) or "manual",
                    "Evidências":len(item.get("evidence_refs") or []),
                }
                for item in reversed(wisdom_entries[-300:])
                if isinstance(item, Mapping)
            ], width="stretch", hide_index=True)
    st.caption(
        "Confirmação automática: NÃO · alteração de regra/peso: NÃO · "
        "promoção automática: NÃO · trading real: BLOQUEADO."
    )

    st.markdown("#### Feature Flags externas")
    rows = [
        {"feature": key, "enabled": bool(value), "default": "OFF"}
        for key, value in sorted(flags.items())
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.markdown("#### Guardian")
    for action in ("read", "save_checkpoint", "publish_social", "deploy_production", "real_trade"):
        decision = guardian_decision(action, {"role": "ADMIN"}, approved=False, feature_flags=flags)
        st.caption(
            f"{action}: {'PERMITIDO' if decision['allowed'] else 'BLOQUEADO'} · "
            f"{decision['risk']} · {decision['reason']}"
        )

    st.markdown("#### 🛡️ Fortaleza & Soberania")
    external_ai = source_authority("EXTERNAL_AI")
    web_instruction = instruction_boundary(
        "WEB",
        contains_action_instruction=True,
    )
    admin_source = source_authority(
        "ADMIN",
        authenticated_admin=is_admin(access),
    )
    safety_preview = proof_of_safety(
        "deploy_production",
        access,
        approved=False,
        feature_flags=flags,
        source_kind="ADMIN",
        authenticated_admin=is_admin(access),
        scope="Prévia de deploy — nenhuma execução nesta tela.",
        artifacts=[],
        tests=[],
        rollback_plan="",
        uncertainty_pct=100,
        impact="CRITICAL",
        reversible=False,
        external_side_effects=True,
    )
    f1,f2,f3,f4 = st.columns(4)
    f1.metric("Outra IA", "CONTEÚDO" if not external_ai.get("can_issue_action") else "AUTORIDADE")
    f2.metric("Instrução web", str(web_instruction.get("state") or "UNKNOWN"))
    f3.metric("Admin autenticado", str(admin_source.get("authority") or "UNKNOWN"))
    f4.metric("Proof of Safety", str(safety_preview.get("state") or "UNKNOWN"))
    st.caption(
        "Site, documento, e-mail, tool output ou outra IA não ganham autoridade para comandar ferramentas. "
        "A origem é uma barreira determinística fora do modelo; o Guardian continua sendo obrigatório."
    )

    resilience_state = resilience_summary(
        checkpoint.get("resilience")
        if isinstance(checkpoint.get("resilience"), Mapping)
        else {}
    )
    rr1,rr2,rr3,rr4 = st.columns(4)
    rr1.metric("Safe Mode", str(resilience_state.get("safe_mode") or "UNKNOWN"))
    rr2.metric("Delegações ativas", int(resilience_state.get("active_delegations") or 0))
    rr3.metric("Circuitos abertos", int(resilience_state.get("open_circuits") or 0))
    rr4.metric("Isolamento recomendado", int(resilience_state.get("isolate_recommendations") or 0))

    memory_health = memory_reliability_summary(
        checkpoint.get("memory_reliability")
        if isinstance(checkpoint.get("memory_reliability"), Mapping)
        else {}
    )
    st.markdown("#### 🧠 Confiabilidade da memória · Epistemic Core")
    mr1,mr2,mr3,mr4 = st.columns(4)
    mr1.metric("Memórias confirmadas", int(memory_health.get("current_confirmed") or 0))
    mr2.metric("Reverificar", int(memory_health.get("verify_required") or 0))
    mr3.metric("Expiradas", int(memory_health.get("expired") or 0))
    mr4.metric("Conflitos", int(memory_health.get("conflicts") or 0))
    st.caption(
        f"Decision snapshots/replay: {int(memory_health.get('decision_snapshots') or 0)} · "
        "memória nunca autoriza ação, não amplia permissão e lembrança vencida/contraditória "
        "não pode ser promovida silenciosamente a fato atual."
    )

    fabric_raw = (
        checkpoint.get("data_decision_fabric")
        if isinstance(checkpoint.get("data_decision_fabric"), Mapping)
        else {}
    )
    fabric_health = data_decision_fabric_summary(
        fabric_raw,
        derived_events=derive_checkpoint_fabric_events(checkpoint),
    )
    st.markdown("#### 🕸️ Data & Decision Fabric")
    df1,df2,df3,df4 = st.columns(4)
    df1.metric("Eventos ativos", int(fabric_health.get("active_events") or 0))
    df2.metric("Conflitos", int(fabric_health.get("conflicts") or 0))
    df3.metric("Decisões", int(fabric_health.get("decisions") or 0))
    df4.metric("Revisão humana", int(fabric_health.get("human_review_candidates") or 0))
    st.caption(
        "Linguagem transversal: evidência → hipótese → teste → risco → decisão → resultado. "
        "A Fabric não executa ação e não transforma evidência em autorização."
    )

    external_worker_preview = agent_firewall(
        source_kind="EXTERNAL_AI",
        requested_capability="READ_CONTEXT",
        workspace_id="development",
        delegation={
            "state":"ACTIVE",
            "workspace_id":"development",
            "granted_capabilities":["READ_CONTEXT"],
        },
    )
    loop_preview = watchdog(
        "preview-agent",
        heartbeat_age_seconds=5,
        repeated_action_count=5,
        loop_limit=5,
    )
    budget_preview = resource_governor(
        "preview-research",
        call_limit=10,
        calls_used=10,
    )
    circuit_preview = circuit_breaker(
        "preview-provider",
        consecutive_failures=3,
    )
    safe_preview = safe_mode_posture(
        open_circuits=1 if circuit_preview.get("state")=="OPEN" else 0,
        isolate_recommendations=1 if loop_preview.get("state")=="ISOLATE_RECOMMENDED" else 0,
    )
    with st.expander("Authority Kernel · Agent Firewall · Resilience", expanded=False):
        st.caption(
            f"IA externa tentando controlar tool: {external_worker_preview.get('state')} · "
            f"watchdog de loop: {loop_preview.get('state')} · "
            f"resource governor: {budget_preview.get('state')} · "
            f"circuit breaker: {circuit_preview.get('state')} · "
            f"safe mode resultante: {safe_preview.get('mode')}."
        )
        st.caption(
            "Outra IA pode produzir conteúdo como worker delegado, mas não recebe autoridade raiz nem "
            "controle direto de tools. Watchdog/circuit breaker são posturas determinísticas; "
            "kill, delete, deploy, mudança de política e expansão de permissão continuam automação proibida."
        )
    with st.expander("Ver bloqueios da prévia de segurança", expanded=False):
        blockers = list(safety_preview.get("blockers") or [])
        if blockers:
            for item in blockers:
                st.markdown(f"- {item}")
        st.caption(
            "Esta prévia usa approved=False, incerteza alta e nenhum teste/rollback. "
            "Ela demonstra fail-closed e não pode ser reutilizada como autorização."
        )

    st.markdown("#### Segurança / resposta a incidente")
    incident_data=dict(incident_snapshot or {})
    st.caption(
        f"Incidentes consolidados: {int(incident_data.get('total') or 0)} · "
        f"severidade máxima: {incident_data.get('highest_severity','INFO')} · "
        f"rollback automático: NÃO."
    )
    if incident_data.get("has_critical"):
        st.warning(
            "Há incidente crítico consolidado. O Laboratório permanece fail-closed; "
            "nenhuma feature externa é ativada como tentativa de diagnóstico."
        )

    emergency = emergency_cutoff_posture(
        critical_incident=bool(incident_data.get("has_critical", False)),
        policy_integrity_ok=None,
        permission_integrity_ok=None,
        secret_exposure_confirmed=False,
    )
    cyber = cyber_immune_plan(
        [],
        antivirus_or_edr_present=None,
    )
    st.caption(
        f"Kill-switch advisory: {emergency.get('state')} · "
        f"Cyber Immune: {cyber.get('posture')} · "
        "contenção automática: NÃO · antivírus/EDR não é desativado pelo AION."
    )

    st.markdown("#### Roteador de inteligência / orçamento")
    current_budget = normalize_budget((checkpoint.get("aion") or {}).get("model_budget", {}))
    provider = provider_status(feature_flags=flags, env=_provider_env())
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Rota atual", provider.get("state","UNKNOWN"))
    c2.metric("Teto mensal", f"US$ {current_budget['monthly_limit_usd']:.2f}")
    c3.metric("Uso estimado", f"US$ {current_budget['spent_usd_estimate']:.4f}")
    c4.metric("Saldo estimado", f"US$ {current_budget['remaining_usd']:.4f}")
    st.caption(
        "Definir teto não gera cobrança. Mesmo com teto positivo, cada solicitação paga continua "
        "exigindo aprovação explícita e um cliente externo realmente implementado."
    )
    with st.form("aion_model_budget_form"):
        monthly_limit = st.number_input(
            "Teto mensal máximo para IA externa (USD)",
            min_value=0.0,
            value=float(current_budget["monthly_limit_usd"]),
            step=1.0,
        )
        allow_paid = st.checkbox(
            "Permitir solicitações pagas dentro do teto",
            value=bool(current_budget["allow_paid"]),
        )
        save_budget = st.form_submit_button("Salvar política de orçamento")
    if save_budget:
        updated = set_budget_policy(
            checkpoint,
            monthly_limit_usd=monthly_limit,
            allow_paid=allow_paid,
            approved_by=str(access.get("username") or "ADMIN"),
            approved_at=datetime.now(timezone.utc).isoformat(),
        )
        updated = update_operating_checkpoint(updated, dirty=True)
        updated = _record_working_event(
            updated,
            "model_budget_policy_updated",
            "Política de orçamento da IA atualizada pelo administrador.",
            evidence={
                "monthly_limit_usd": monthly_limit,
                "allow_paid": allow_paid,
                "external_feature_enabled": bool(flags.get("external_llm", False)),
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success("Política de orçamento atualizada localmente; salve o Checkpoint Mestre para persistir.")
        st.rerun()

    preview = route_intelligence(
        "análise complexa de arquitetura do AtlasQuant",
        provider_state=provider.get("state"),
        external_feature_enabled=bool(flags.get("external_llm", False)),
        budget=current_budget,
        estimated_request_cost_usd=0.01,
        request_approved=False,
    )
    st.caption(
        f"Teste do roteador: {preview['lane']} · {preview['complexity']} · {preview['reason']}"
    )


def _developer_intelligence_summary(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(snapshot or {})
    counts = item.get("category_counts") if isinstance(item.get("category_counts"), Mapping) else {}
    risks = item.get("risk_counts") if isinstance(item.get("risk_counts"), Mapping) else {}
    return {
        "state": "READY" if str(item.get("snapshot_digest") or "") else "NOT_SCANNED",
        "snapshot_digest": str(item.get("snapshot_digest") or ""),
        "files": int(item.get("file_count") or 0),
        "modules": int(counts.get("MODULE") or 0),
        "tests": int(counts.get("TEST") or 0),
        "workflows": int(counts.get("WORKFLOW") or 0),
        "syntax_errors": int(item.get("syntax_errors") or 0),
        "risk_surfaces": sum(int(value or 0) for value in risks.values()),
        "truncated": bool(item.get("truncated", False)),
        "content_included": bool(item.get("content_included", False)),
        "writes_files": bool(item.get("writes_files", False)),
        "network_called": bool(item.get("network_called", False)),
        "subprocess_called": bool(item.get("subprocess_called", False)),
    }


def _render_developer_intelligence() -> None:
    st.markdown("#### 🧭 Developer Intelligence · mapa estrutural")
    st.caption(
        "Diagnóstico local somente leitura. Abrir a aba não inicia scan. "
        "O scanner não executa módulos, não segue symlink, não lê .env/secrets conhecidos, "
        "não chama rede e não escreve arquivos."
    )

    snapshot = (
        st.session_state.get("aion_developer_repo_snapshot")
        if isinstance(st.session_state.get("aion_developer_repo_snapshot"), Mapping)
        else None
    )
    if st.button(
        "Mapear repositório local",
        key="aion_developer_intelligence_scan",
        help="Lê apenas metadados estruturais e AST de arquivos permitidos. Nenhum código do repositório é executado.",
    ):
        try:
            project_root = Path(__file__).resolve().parent
            snapshot = scan_developer_repository(project_root)
            st.session_state["aion_developer_repo_snapshot"] = snapshot
        except Exception as exc:
            st.error(f"Scan estrutural falhou de forma isolada: {type(exc).__name__}")
            snapshot = None

    summary = _developer_intelligence_summary(snapshot)
    d1,d2,d3,d4,d5 = st.columns(5)
    d1.metric("Snapshot", summary["state"])
    d2.metric("Módulos", summary["modules"])
    d3.metric("Testes", summary["tests"])
    d4.metric("Workflows", summary["workflows"])
    d5.metric("Syntax errors", summary["syntax_errors"])

    if summary["state"] != "READY":
        st.info("Nenhum snapshot estrutural foi criado nesta sessão. O scan continua opt-in.")
        return

    st.caption(
        f"Digest {summary['snapshot_digest']} · arquivos {summary['files']} · "
        f"superfícies de risco {summary['risk_surfaces']} · "
        f"truncado {'SIM' if summary['truncated'] else 'NÃO'}."
    )
    if (
        summary["content_included"]
        or summary["writes_files"]
        or summary["network_called"]
        or summary["subprocess_called"]
    ):
        st.error("Snapshot recusado: invariantes read-only não foram preservadas.")
        return

    risk_counts = snapshot.get("risk_counts") if isinstance(snapshot.get("risk_counts"), Mapping) else {}
    if risk_counts:
        st.dataframe(
            [{"Superfície": key, "Arquivos": int(value or 0)} for key,value in sorted(risk_counts.items())],
            width="stretch",
            hide_index=True,
        )

    with st.expander("Planejar mudança com o mapa atual", expanded=False):
        dev_request = st.text_area(
            "Objetivo técnico",
            key="aion_developer_intelligence_request",
            max_chars=1200,
            placeholder="Ex.: corrigir o painel sem alterar autoridade do Tool Hub.",
        )
        changed_text = st.text_area(
            "Arquivos candidatos — um por linha",
            key="aion_developer_intelligence_changed_paths",
            max_chars=5000,
            placeholder="atlasquant_aion_admin.py\ntest_atlasquant_aion_admin.py",
        )
        branch_label = st.text_input(
            "Branch de trabalho (rótulo)",
            key="aion_developer_intelligence_branch",
            value="working-copy",
        )
        baseline_label = st.text_input(
            "Baseline ref (rótulo)",
            key="aion_developer_intelligence_baseline",
            value=str(snapshot.get("snapshot_digest") or "snapshot-current"),
        )
        if st.button("Montar plano estrutural", key="aion_developer_intelligence_plan"):
            try:
                changed_paths = [line.strip() for line in changed_text.splitlines() if line.strip()]
                plan = build_developer_intelligence_plan(
                    dev_request,
                    snapshot,
                    branch=branch_label,
                    baseline_ref=baseline_label,
                    changed_paths=changed_paths,
                )
                st.session_state["aion_developer_intelligence_plan_result"] = plan
            except Exception as exc:
                st.error(f"Plano estrutural recusado: {type(exc).__name__}")

    plan = (
        st.session_state.get("aion_developer_intelligence_plan_result")
        if isinstance(st.session_state.get("aion_developer_intelligence_plan_result"), Mapping)
        else None
    )
    if not isinstance(plan, Mapping):
        return

    p1,p2,p3 = st.columns(3)
    p1.metric("Arquivos impactados", len(list(plan.get("impacted_files") or [])))
    p2.metric("Testes prováveis", len(list(plan.get("recommended_tests") or [])))
    p3.metric("Sem teste provável", len(list(plan.get("unmatched_code") or [])))
    st.caption(
        f"Plano {plan.get('plan_id')} · análise somente leitura · "
        "coverage é heurística, não prova de correção."
    )
    if plan.get("risk_tags"):
        st.markdown("**Superfícies sensíveis:** " + " · ".join(str(x) for x in list(plan.get("risk_tags") or [])))
    if plan.get("recommended_tests"):
        st.markdown("**Testes sugeridos:**")
        for item in list(plan.get("recommended_tests") or [])[:30]:
            st.markdown(f"- {item}")
    if plan.get("unmatched_code"):
        st.warning(
            "Arquivos Python sem teste provável: "
            + ", ".join(str(x) for x in list(plan.get("unmatched_code") or [])[:20])
        )
    st.caption(
        "Este plano não edita, não commita, não faz merge, não faz deploy e não habilita produção/trading."
    )

    if st.button(
        "Preparar pacote Developer Engine + Dev Fusion",
        key="aion_developer_intelligence_package",
    ):
        try:
            package = build_developer_package(
                plan.get("request"),
                snapshot,
                branch=plan.get("branch"),
                baseline_ref=plan.get("baseline_ref"),
                candidate_ref=plan.get("branch"),
                changed_paths=list(plan.get("impacted_files") or []),
                requested_by="AION_ADMIN_SESSION",
            )
            st.session_state["aion_developer_package_result"] = package
        except Exception as exc:
            st.error(f"Pacote de desenvolvimento recusado: {type(exc).__name__}")

    package = (
        st.session_state.get("aion_developer_package_result")
        if isinstance(st.session_state.get("aion_developer_package_result"), Mapping)
        else None
    )
    if not isinstance(package, Mapping):
        return

    workflow = package.get("developer_workflow") if isinstance(package.get("developer_workflow"), Mapping) else {}
    twin = package.get("digital_twin") if isinstance(package.get("digital_twin"), Mapping) else {}
    fusion = package.get("dev_fusion") if isinstance(package.get("dev_fusion"), Mapping) else {}
    strategy = package.get("test_strategy") if isinstance(package.get("test_strategy"), Mapping) else {}

    st.markdown("##### Pacote Developer Engine + Dev Fusion")
    x1,x2,x3,x4 = st.columns(4)
    x1.metric("Pacote", str(package.get("state") or "UNKNOWN"))
    x2.metric("Workflow", str(workflow.get("status") or "UNKNOWN"))
    x3.metric("Digital Twin", str(twin.get("state") or "UNKNOWN"))
    x4.metric("Dev Fusion", str(fusion.get("state") or "UNKNOWN"))
    st.caption(
        f"{package.get('package_id')} · workflow {workflow.get('workflow_id')} · "
        f"twin {twin.get('twin_id')} · pipeline {fusion.get('pipeline_id')}."
    )

    gates = [dict(item) for item in list(package.get("gates") or []) if isinstance(item, Mapping)]
    if gates:
        st.dataframe(
            [{
                "Gate": item.get("gate"),
                "Estado": item.get("state"),
                "Regra": item.get("detail"),
            } for item in gates],
            width="stretch",
            hide_index=True,
        )

    required_tests = list(strategy.get("required_test_candidates") or [])
    if required_tests:
        st.markdown("**Candidatos de teste exigidos pelo pacote:**")
        for item in required_tests[:40]:
            st.markdown(f"- `{item}`")
    if package.get("gaps"):
        st.warning(
            "Gaps para revisão: "
            + " · ".join(str(x) for x in list(package.get("gaps") or []))
        )
    st.caption(
        "O pacote fica apenas na sessão: não persiste Checkpoint, não executa testes, "
        "não edita arquivos e não aprova PLAN/BUILD/REVIEW/RELEASE automaticamente."
    )

    with st.expander("Diagnosticar falha de teste/log", expanded=False):
        failure_text = st.text_area(
            "Trecho de falha",
            key="aion_developer_failure_text",
            max_chars=120000,
            placeholder="Cole traceback, FAILED test_... ou exceção. O diagnóstico é sanitizado.",
        )
        if st.button("Diagnosticar falha", key="aion_developer_failure_diagnose"):
            try:
                diagnostic = diagnose_developer_failure(snapshot, failure_text)
                st.session_state["aion_developer_failure_diagnostic"] = diagnostic
            except Exception as exc:
                st.error(f"Diagnóstico recusado: {type(exc).__name__}")

    diagnostic = (
        st.session_state.get("aion_developer_failure_diagnostic")
        if isinstance(st.session_state.get("aion_developer_failure_diagnostic"), Mapping)
        else None
    )
    if not isinstance(diagnostic, Mapping):
        return

    st.markdown("##### Diagnóstico de falha · fatos vs hipótese")
    y1,y2,y3 = st.columns(3)
    y1.metric("Evidência", str(diagnostic.get("state") or "UNKNOWN"))
    y2.metric("Exceção", str(diagnostic.get("exception_type") or "UNKNOWN_FAILURE"))
    y3.metric("Causa", "UNKNOWN" if not diagnostic.get("cause_confirmed") else "CONFIRMED")
    st.caption(
        f"{diagnostic.get('diagnostic_id')} · log digest {diagnostic.get('log_digest')} · "
        "log bruto não é armazenado no diagnóstico."
    )

    facts = [
        dict(item)
        for item in list(diagnostic.get("confirmed_facts") or [])
        if isinstance(item, Mapping)
    ]
    if facts:
        st.markdown("**Fatos confirmados pelo log:**")
        st.dataframe(
            [{
                "Tipo": item.get("kind"),
                "Valor": item.get("value"),
                "Verdade": item.get("truth_status"),
            } for item in facts],
            width="stretch",
            hide_index=True,
        )

    hypotheses = [
        dict(item)
        for item in list(diagnostic.get("hypotheses") or [])
        if isinstance(item, Mapping)
    ]
    if hypotheses:
        st.markdown("**HIPÓTESE — não confirmada:**")
        for item in hypotheses:
            st.markdown(
                f"- {item.get('label')} · {item.get('rationale')} "
                f"· truth={item.get('truth_status')}"
            )

    if diagnostic.get("recommended_tests"):
        st.markdown("**Testes candidatos para reprodução:**")
        for item in list(diagnostic.get("recommended_tests") or [])[:40]:
            st.markdown(f"- `{item}`")

    if diagnostic.get("state") == "FAILURE_EVIDENCE":
        if st.button(
            "Registrar falha no Developer Workflow da sessão",
            key="aion_developer_failure_record",
        ):
            try:
                current_package = deepcopy(dict(package))
                current_workflow = (
                    current_package.get("developer_workflow")
                    if isinstance(current_package.get("developer_workflow"), Mapping)
                    else {}
                )
                current_package["developer_workflow"] = record_developer_failure_attempt(
                    current_workflow,
                    diagnostic,
                    command_label="evidência de falha informada ao AION",
                )
                current_package["last_diagnostic_id"] = diagnostic.get("diagnostic_id")
                st.session_state["aion_developer_package_result"] = current_package
                package = current_package
                st.success(
                    "Falha registrada somente no workflow da sessão; nenhum patch foi aplicado."
                )
            except Exception as exc:
                st.error(f"Registro da falha recusado: {type(exc).__name__}")

    st.caption(
        "Diagnóstico não executa teste, não confirma causa raiz, não cria patch, "
        "não commita, não faz merge e não faz deploy."
    )

    if diagnostic.get("state") == "FAILURE_EVIDENCE":
        if st.button(
            "Preparar plano de correção rastreável",
            key="aion_developer_correction_plan",
        ):
            try:
                correction = build_developer_correction_plan(
                    snapshot,
                    diagnostic,
                    package,
                )
                st.session_state["aion_developer_correction_result"] = correction
            except Exception as exc:
                st.error(f"Plano de correção recusado: {type(exc).__name__}")

    correction = (
        st.session_state.get("aion_developer_correction_result")
        if isinstance(st.session_state.get("aion_developer_correction_result"), Mapping)
        else None
    )
    if not isinstance(correction, Mapping):
        return

    st.markdown("##### Plano de correção rastreável")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estado", str(correction.get("state") or "UNKNOWN"))
    c2.metric("Causa raiz", str(correction.get("root_cause_truth_status") or "UNKNOWN"))
    c3.metric("Arquivos alvo", len(list(correction.get("target_files") or [])))
    c4.metric("Testes candidatos", len(list(correction.get("test_candidates") or [])))
    lineage = correction.get("lineage") if isinstance(correction.get("lineage"), Mapping) else {}
    st.caption(
        f"{correction.get('correction_id')} · snapshot {lineage.get('snapshot_digest')} · "
        f"diagnóstico {lineage.get('diagnostic_id')} · pacote {lineage.get('package_id')}."
    )
    st.markdown(f"**Objetivo de correção:** {correction.get('objective')}")

    if correction.get("target_files"):
        st.markdown("**Escopo permitido:**")
        for item in list(correction.get("target_files") or []):
            st.markdown(f"- `{item}`")
    if correction.get("hypotheses"):
        st.markdown("**Hipóteses ainda UNKNOWN:**")
        for item in list(correction.get("hypotheses") or []):
            if isinstance(item, Mapping):
                st.markdown(
                    f"- {item.get('label')} · truth={item.get('truth_status')} · "
                    f"{item.get('rationale')}"
                )
    if correction.get("evidence_required"):
        st.markdown("**Evidências exigidas antes de concluir:**")
        for item in list(correction.get("evidence_required") or []):
            st.markdown(f"- {item}")

    builder = correction.get("builder_packet") if isinstance(correction.get("builder_packet"), Mapping) else {}
    reviewer = correction.get("reviewer_packet") if isinstance(correction.get("reviewer_packet"), Mapping) else {}
    breaker = correction.get("breaker_packet") if isinstance(correction.get("breaker_packet"), Mapping) else {}
    role_rows = [
        {
            "Papel": "Builder",
            "Estado": builder.get("state"),
            "Independência": "aguarda atribuição humana",
            "Executa ação": builder.get("executes_action"),
        },
        {
            "Papel": "Reviewer",
            "Estado": reviewer.get("state"),
            "Independência": "obrigatória vs Builder",
            "Executa ação": reviewer.get("executes_action"),
        },
        {
            "Papel": "Breaker",
            "Estado": breaker.get("state"),
            "Independência": "obrigatória vs Builder/Reviewer",
            "Executa ação": breaker.get("executes_action"),
        },
    ]
    st.dataframe(role_rows, width="stretch", hide_index=True)

    if correction.get("gaps"):
        st.warning(
            "Gaps do plano: "
            + " · ".join(str(x) for x in list(correction.get("gaps") or []))
        )
    st.caption(
        "Este plano não gera patch, não altera arquivo, não executa teste e não confirma causa raiz. "
        "A implementação continua aguardando decisão humana e evidência."
    )

    with st.expander("Evidence Promotion Gate · causa raiz", expanded=False):
        hypothesis_labels = [
            str(item.get("label") or "")
            for item in list(correction.get("hypotheses") or [])
            if isinstance(item, Mapping) and str(item.get("label") or "")
        ]
        test_candidates = [str(x) for x in list(correction.get("test_candidates") or []) if str(x)]
        target_files = [str(x) for x in list(correction.get("target_files") or []) if str(x)]

        gate_hypothesis = st.selectbox(
            "Hipótese avaliada",
            hypothesis_labels or ["CAUSE_NOT_YET_CONFIRMED"],
            key="aion_developer_gate_hypothesis",
        )
        gate_test = st.selectbox(
            "Teste de reprodução",
            test_candidates or ["NO_TEST_CANDIDATE"],
            key="aion_developer_gate_test",
        )
        g1,g2 = st.columns(2)
        with g1:
            before_state = st.selectbox(
                "Estado antes",
                ["FAIL","UNKNOWN","PASS"],
                key="aion_developer_gate_before",
            )
        with g2:
            after_state = st.selectbox(
                "Estado depois",
                ["PASS","UNKNOWN","FAIL"],
                key="aion_developer_gate_after",
            )
        changed_scope = st.multiselect(
            "Arquivos alterados na tentativa",
            target_files,
            default=target_files,
            key="aion_developer_gate_changed_files",
        )
        intervention_summary = st.text_area(
            "Resumo da intervenção observada",
            key="aion_developer_gate_intervention",
            max_chars=1600,
            placeholder="Descreva o que mudou entre a evidência FAIL e PASS sem declarar causa além do que foi observado.",
        )
        gate_refs_text = st.text_area(
            "Referências de evidência — uma por linha",
            key="aion_developer_gate_refs",
            max_chars=5000,
            placeholder="run:before\nrun:after",
        )
        scope_preserved = st.checkbox(
            "Confirmo que a tentativa permaneceu dentro do escopo permitido",
            key="aion_developer_gate_scope_preserved",
            value=False,
        )
        if st.button(
            "Avaliar evidência para revisão humana",
            key="aion_developer_gate_evaluate",
        ):
            try:
                lineage = correction.get("lineage") if isinstance(correction.get("lineage"), Mapping) else {}
                gate = evaluate_developer_evidence_promotion(
                    correction,
                    hypothesis_label=gate_hypothesis,
                    test_id=gate_test,
                    before_state=before_state,
                    after_state=after_state,
                    changed_files=changed_scope,
                    evidence_refs=[line.strip() for line in gate_refs_text.splitlines() if line.strip()],
                    intervention_summary=intervention_summary,
                    scope_preserved=scope_preserved,
                    snapshot_digest=lineage.get("snapshot_digest"),
                    diagnostic_id=lineage.get("diagnostic_id"),
                )
                st.session_state["aion_developer_evidence_gate_result"] = gate
            except Exception as exc:
                st.error(f"Evidence gate recusado: {type(exc).__name__}")

    gate = (
        st.session_state.get("aion_developer_evidence_gate_result")
        if isinstance(st.session_state.get("aion_developer_evidence_gate_result"), Mapping)
        else None
    )
    if not isinstance(gate, Mapping):
        return

    st.markdown("##### Evidence Promotion Gate")
    e1,e2,e3 = st.columns(3)
    e1.metric("Gate", str(gate.get("state") or "UNKNOWN"))
    gate_hyp = gate.get("hypothesis") if isinstance(gate.get("hypothesis"), Mapping) else {}
    e2.metric("Verdade atual", str(gate_hyp.get("current_truth_status") or "UNKNOWN"))
    e3.metric("Promoção aplicada", "SIM" if gate_hyp.get("promotion_applied") else "NÃO")
    st.caption(
        f"{gate.get('gate_id')} · promoção automática: NÃO · revisão humana obrigatória."
    )
    if gate.get("blockers"):
        st.warning(
            "Evidência insuficiente: "
            + " · ".join(str(x) for x in list(gate.get("blockers") or []))
        )
    elif gate.get("state") == "READY_FOR_HUMAN_CAUSE_REVIEW":
        st.success(
            "Evidência suficiente para revisão humana. A causa ainda continua UNKNOWN até confirmação explícita."
        )

        with st.expander("Revisão humana da causa", expanded=False):
            reviewer_actor = st.text_input(
                "Identificação do revisor humano",
                key="aion_developer_cause_reviewer",
                max_chars=160,
            )
            review_refs_text = st.text_area(
                "Referências da revisão humana — uma por linha",
                key="aion_developer_cause_review_refs",
                max_chars=4000,
            )
            reviewed = st.checkbox(
                "Revisei a evidência e aprovo a promoção desta hipótese de causa",
                key="aion_developer_cause_review_approved",
                value=False,
            )
            if st.button(
                "Confirmar causa após revisão humana",
                key="aion_developer_cause_confirm",
            ):
                try:
                    confirmed = confirm_developer_root_cause(
                        correction,
                        gate,
                        approved=reviewed,
                        reviewer_actor=reviewer_actor,
                        review_evidence_refs=[
                            line.strip()
                            for line in review_refs_text.splitlines()
                            if line.strip()
                        ],
                    )
                    st.session_state["aion_developer_correction_result"] = confirmed
                    correction = confirmed
                    st.success(
                        "Causa promovida somente no registro da sessão após revisão humana explícita."
                    )
                except Exception as exc:
                    st.error(f"Confirmação recusada: {type(exc).__name__}")

    st.caption(
        "O Evidence Promotion Gate não executa testes nem aplica patch. "
        "Mesmo a confirmação humana permanece session-only e não autoriza IMPLEMENT, merge ou deploy."
    )

    if correction.get("root_cause_confirmed") is True:
        if st.button(
            "Preparar envelope de implementação · nível 2",
            key="aion_developer_implementation_envelope",
        ):
            try:
                implementation = build_developer_implementation_envelope(
                    snapshot,
                    package,
                    correction,
                )
                st.session_state["aion_developer_implementation_result"] = implementation
            except Exception as exc:
                st.error(f"Envelope de implementação recusado: {type(exc).__name__}")

    implementation = (
        st.session_state.get("aion_developer_implementation_result")
        if isinstance(st.session_state.get("aion_developer_implementation_result"), Mapping)
        else None
    )
    if not isinstance(implementation, Mapping):
        return

    st.markdown("##### Implementation Readiness Envelope")
    i1,i2,i3,i4 = st.columns(4)
    i1.metric("Estado", str(implementation.get("state") or "UNKNOWN"))
    i2.metric("Nível pedido", int(implementation.get("requested_trust_level") or 0))
    trust = implementation.get("trust_policy") if isinstance(implementation.get("trust_policy"), Mapping) else {}
    i3.metric("Máx. autônomo", int(trust.get("max_autonomous_level") or 0))
    i4.metric("Execução autorizada", "SIM" if implementation.get("execution_authorized") else "NÃO")
    st.caption(
        f"{implementation.get('envelope_id')} · nível 2 = branch isolada · "
        "aprovação humana obrigatória."
    )

    impl_scope = implementation.get("scope") if isinstance(implementation.get("scope"), Mapping) else {}
    if impl_scope.get("editable_files"):
        st.markdown("**Escopo editável máximo proposto:**")
        for item in list(impl_scope.get("editable_files") or []):
            st.markdown(f"- `{item}`")
    test_contract = (
        implementation.get("test_contract")
        if isinstance(implementation.get("test_contract"), Mapping)
        else {}
    )
    if test_contract.get("mandatory_gates"):
        st.markdown("**Gates obrigatórios depois de qualquer implementação:**")
        for item in list(test_contract.get("mandatory_gates") or []):
            st.markdown(f"- {item}")
    if implementation.get("forbidden_changes"):
        st.markdown("**Mudanças proibidas pelo envelope:**")
        for item in list(implementation.get("forbidden_changes") or []):
            st.markdown(f"- {item}")

    if implementation.get("state") == "WAITING_HUMAN_IMPLEMENTATION_APPROVAL":
        with st.expander("Prontidão da implementação · rollback e papéis", expanded=False):
            rollback_plan = st.text_area(
                "Rollback específico desta mudança",
                key="aion_developer_implementation_rollback",
                max_chars=2400,
            )
            r1,r2,r3 = st.columns(3)
            with r1:
                builder_actor = st.text_input("Builder", key="aion_developer_implementation_builder", max_chars=160)
                builder_principal_id = st.text_input(
                    "Builder principal id",
                    key="aion_developer_implementation_builder_principal",
                    max_chars=80,
                )
            with r2:
                reviewer_actor = st.text_input("Reviewer independente", key="aion_developer_implementation_reviewer", max_chars=160)
                reviewer_principal_id = st.text_input(
                    "Reviewer principal id",
                    key="aion_developer_implementation_reviewer_principal",
                    max_chars=80,
                )
            with r3:
                breaker_actor = st.text_input("Breaker independente", key="aion_developer_implementation_breaker", max_chars=160)
                breaker_principal_id = st.text_input(
                    "Breaker principal id",
                    key="aion_developer_implementation_breaker_principal",
                    max_chars=80,
                )
            readiness_refs_text = st.text_area(
                "Evidências de prontidão — uma por linha",
                key="aion_developer_implementation_readiness_refs",
                max_chars=4000,
            )
            if st.button("Registrar prontidão da implementação", key="aion_developer_implementation_readiness"):
                try:
                    ready = prepare_developer_implementation_readiness(
                        implementation,
                        rollback_plan=rollback_plan,
                        builder_actor=builder_actor,
                        reviewer_actor=reviewer_actor,
                        breaker_actor=breaker_actor,
                        builder_principal_id=builder_principal_id,
                        reviewer_principal_id=reviewer_principal_id,
                        breaker_principal_id=breaker_principal_id,
                        readiness_refs=[line.strip() for line in readiness_refs_text.splitlines() if line.strip()],
                    )
                    st.session_state["aion_developer_implementation_result"] = ready
                    implementation = ready
                    st.success("Prontidão registrada somente na sessão. Execução continua não autorizada.")
                except Exception as exc:
                    st.error(f"Prontidão recusada: {type(exc).__name__}")

    if implementation.get("state") == "READY_FOR_HUMAN_IMPLEMENTATION_APPROVAL":
        readiness = implementation.get("readiness") if isinstance(implementation.get("readiness"), Mapping) else {}
        rollback_contract = implementation.get("rollback_contract") if isinstance(implementation.get("rollback_contract"), Mapping) else {}
        st.caption(
            f"Builder={readiness.get('builder_actor')} ({readiness.get('builder_principal_id')}) · "
            f"Reviewer={readiness.get('reviewer_actor')} ({readiness.get('reviewer_principal_id')}) · "
            f"Breaker={readiness.get('breaker_actor')} ({readiness.get('breaker_principal_id')}) · rollback específico: "
            f"{'SIM' if rollback_contract.get('recorded_for_this_change') else 'NÃO'}."
        )
        with st.expander("Aprovação humana · branch isolada", expanded=False):
            impl_actor = st.text_input(
                "Identificação do aprovador humano",
                key="aion_developer_implementation_approver",
                max_chars=160,
            )
            impl_principal = st.text_input(
                "Approver principal id",
                key="aion_developer_implementation_approver_principal",
                max_chars=80,
            )
            impl_refs_text = st.text_area(
                "Referências da aprovação — uma por linha",
                key="aion_developer_implementation_refs",
                max_chars=4000,
            )
            impl_approved = st.checkbox(
                "Autorizo apenas a implementação em branch isolada dentro deste escopo",
                key="aion_developer_implementation_approved",
                value=False,
            )
            if st.button(
                "Registrar autorização de implementação na sessão",
                key="aion_developer_implementation_confirm",
            ):
                try:
                    authorized = approve_developer_implementation(
                        implementation,
                        approved=impl_approved,
                        approver_actor=impl_actor,
                        approver_principal_id=impl_principal,
                        approval_refs=[line.strip() for line in impl_refs_text.splitlines() if line.strip()],
                    )
                    st.session_state["aion_developer_implementation_result"] = authorized
                    implementation = authorized
                    st.success(
                        "Autorização de nível 2 registrada somente na sessão. "
                        "Nenhum arquivo foi editado e execution_authorized continua False."
                    )
                except Exception as exc:
                    st.error(f"Autorização recusada: {type(exc).__name__}")

    if implementation.get("state") == "IMPLEMENTATION_AUTHORIZED_SESSION_ONLY":
        st.info(
            "Implementação em branch está autorizada no registro da sessão, mas não existe executor ligado a este envelope. "
            "Merge em main, deploy e produção continuam bloqueados."
        )

    st.caption(
        "Implementation authorized não significa execution authorized. "
        "Este envelope não grava arquivo, não commita e não chama Tool Hub."
    )

    if implementation.get("state") == "IMPLEMENTATION_AUTHORIZED_SESSION_ONLY":
        impl_scope = implementation.get("scope") if isinstance(implementation.get("scope"), Mapping) else {}
        editable_files = [str(x) for x in list(impl_scope.get("editable_files") or []) if str(x)]
        plan_meta = package.get("plan") if isinstance(package.get("plan"), Mapping) else {}
        with st.expander("Builder Sandbox Request · branch isolada", expanded=False):
            sandbox_branch = st.text_input(
                "Branch isolada",
                key="aion_developer_builder_branch",
                value=str(plan_meta.get("branch") or "cursor/aion-builder-sandbox"),
                max_chars=240,
            )
            sandbox_baseline = st.text_input(
                "Baseline ref",
                key="aion_developer_builder_baseline",
                value=str(plan_meta.get("baseline_ref") or "main@baseline"),
                max_chars=240,
            )
            sandbox_candidate = st.text_input(
                "Candidate ref",
                key="aion_developer_builder_candidate",
                value=str(
                    (
                        implementation.get("revision_contract")
                        if isinstance(implementation.get("revision_contract"), Mapping)
                        else {}
                    ).get("candidate_ref")
                    or f"{str(plan_meta.get('branch') or 'cursor/aion-builder-sandbox')}@candidate"
                ),
                max_chars=240,
            )
            sandbox_files = st.multiselect(
                "Arquivos solicitados ao Builder",
                editable_files,
                default=editable_files,
                key="aion_developer_builder_files",
            )
            if st.button(
                "Preparar Builder Sandbox Request",
                key="aion_developer_builder_prepare",
            ):
                try:
                    builder_request = build_developer_builder_sandbox_request(
                        snapshot,
                        implementation,
                        branch=sandbox_branch,
                        baseline_ref=sandbox_baseline,
                        candidate_ref=sandbox_candidate,
                        requested_files=sandbox_files,
                    )
                    st.session_state["aion_developer_builder_request"] = builder_request
                except Exception as exc:
                    st.error(f"Builder Sandbox Request recusado: {type(exc).__name__}")

    builder_request = (
        st.session_state.get("aion_developer_builder_request")
        if isinstance(st.session_state.get("aion_developer_builder_request"), Mapping)
        else None
    )
    if isinstance(builder_request, Mapping):
        st.markdown("##### Builder Sandbox Request")
        b1,b2,b3,b4 = st.columns(4)
        b1.metric("Estado", str(builder_request.get("state") or "UNKNOWN"))
        branch_contract = (
            builder_request.get("branch_contract")
            if isinstance(builder_request.get("branch_contract"), Mapping)
            else {}
        )
        b2.metric("Branch", str(branch_contract.get("branch") or ""))
        b3.metric("Executor", "LIGADO" if builder_request.get("executor_attached") else "NÃO LIGADO")
        b4.metric("Execução", "AUTORIZADA" if builder_request.get("execution_authorized") else "BLOQUEADA")
        st.caption(
            f"{builder_request.get('request_id')} · main permitido: NÃO · "
            "scope expansion: NÃO · force push: NÃO."
        )
        if builder_request.get("blockers"):
            st.warning(
                "Request bloqueado: "
                + " · ".join(str(x) for x in list(builder_request.get("blockers") or []))
            )
        else:
            st.success(
                "Solicitação de sandbox preparada. Nenhum executor de escrita foi ligado."
            )
        request_scope = (
            builder_request.get("scope")
            if isinstance(builder_request.get("scope"), Mapping)
            else {}
        )
        if request_scope.get("requested_files"):
            st.markdown("**Escopo solicitado ao Builder:**")
            for item in list(request_scope.get("requested_files") or []):
                st.markdown(f"- `{item}`")
        st.caption(
            "Builder Sandbox Request é planejamento: patch_generated=False, writes_files=False, "
            "automatic_commit=False, automatic_merge=False e automatic_deploy=False."
        )

        if builder_request.get("state") == "READY_FOR_BUILDER_SANDBOX":
            with st.expander("Sandbox Preflight · contrato declarativo", expanded=False):
                st.caption(
                    "Isto descreve as condições exigidas para um futuro sandbox; "
                    "não prova que um ambiente real já foi criado."
                )
                preflight_environment_id = st.text_input(
                    "ID lógico do ambiente isolado",
                    value="aion-builder-design-only",
                    key="aion_developer_sandbox_environment_id",
                    max_chars=160,
                )
                if st.button(
                    "Preparar contrato declarativo de sandbox",
                    key="aion_developer_sandbox_preflight_prepare",
                ):
                    try:
                        preflight = build_developer_sandbox_preflight(
                            builder_request,
                            environment_kind="ISOLATED_WORKTREE",
                            environment_id=preflight_environment_id,
                            isolated_worktree=True,
                            repository_root_bound=True,
                            network_disabled=True,
                            secrets_mounted=False,
                            command_policy=DEVELOPER_SANDBOX_COMMAND_POLICY,
                        )
                        st.session_state["aion_developer_sandbox_preflight"] = preflight
                    except Exception as exc:
                        st.error(f"Sandbox preflight recusado: {type(exc).__name__}")

    preflight = (
        st.session_state.get("aion_developer_sandbox_preflight")
        if isinstance(st.session_state.get("aion_developer_sandbox_preflight"), Mapping)
        else None
    )
    if isinstance(preflight, Mapping):
        st.markdown("##### Sandbox Preflight · design only")
        p1,p2,p3 = st.columns(3)
        p1.metric("Estado", str(preflight.get("state") or "UNKNOWN"))
        p2.metric("Executor", "LIGADO" if preflight.get("executor_attached") else "NÃO LIGADO")
        p3.metric("Execução", "AUTORIZADA" if preflight.get("execution_authorized") else "BLOQUEADA")
        st.caption(
            "Preflight declarativo: não executa comandos, não cria worktree e não comprova isolamento real."
        )

    if (
        isinstance(builder_request, Mapping)
        and isinstance(preflight, Mapping)
        and preflight.get("state") == "READY_FOR_EXECUTOR_DESIGN_REVIEW"
    ):
        with st.expander("Patch Validator · diff read-only", expanded=False):
            st.caption(
                "Cole somente um unified diff que você pretende revisar. "
                "O formulário limpa o texto após envio; o resultado não armazena o patch bruto."
            )
            with st.form("aion_developer_patch_validation_form", clear_on_submit=True):
                patch_text = st.text_area(
                    "Unified diff não confiável",
                    key="aion_developer_patch_text",
                    max_chars=500000,
                    height=220,
                    placeholder="diff --git a/arquivo.py b/arquivo.py ...",
                )
                validate_patch_submit = st.form_submit_button(
                    "Validar patch sem aplicar",
                    type="primary",
                )
            if validate_patch_submit:
                try:
                    branch_contract = (
                        builder_request.get("branch_contract")
                        if isinstance(builder_request.get("branch_contract"), Mapping)
                        else {}
                    )
                    patch_validation = validate_developer_patch(
                        builder_request,
                        preflight,
                        patch_text,
                        baseline_ref=branch_contract.get("baseline_ref"),
                        candidate_ref=branch_contract.get("candidate_ref"),
                    )
                    st.session_state["aion_developer_patch_validation"] = patch_validation
                except Exception as exc:
                    st.error(f"Patch recusado: {type(exc).__name__}")

    patch_validation = (
        st.session_state.get("aion_developer_patch_validation")
        if isinstance(st.session_state.get("aion_developer_patch_validation"), Mapping)
        else None
    )
    if isinstance(patch_validation, Mapping):
        st.markdown("##### Patch Validation · somente leitura")
        v1,v2,v3,v4 = st.columns(4)
        v1.metric("Estado", str(patch_validation.get("state") or "UNKNOWN"))
        v2.metric("Arquivos", int(patch_validation.get("file_count") or 0))
        v3.metric("Linhas alteradas", int(patch_validation.get("changed_lines") or 0))
        v4.metric("Patch aplicado", "SIM" if patch_validation.get("patch_applied") else "NÃO")
        if patch_validation.get("blockers"):
            st.warning(
                "Patch bloqueado: "
                + " · ".join(str(x) for x in list(patch_validation.get("blockers") or []))
            )
        else:
            st.success(
                "Diff compatível com o escopo para revisão humana. "
                "Isto não autoriza aplicar, testar, commitar, mergear ou publicar."
            )
        if patch_validation.get("files"):
            st.dataframe(
                [
                    {
                        "Arquivo": row.get("path"),
                        "Operação": row.get("operation"),
                        "+": row.get("added_lines"),
                        "-": row.get("deleted_lines"),
                        "Blockers": " · ".join(str(x) for x in list(row.get("blockers") or [])),
                    }
                    for row in list(patch_validation.get("files") or [])
                    if isinstance(row, Mapping)
                ],
                width="stretch",
                hide_index=True,
            )
        st.caption(
            f"{patch_validation.get('patch_digest')} · patch_text_included=False · "
            "execution_authorized=False · writes_files=False."
        )

        if patch_validation.get("state") == "READY_FOR_PATCH_REVIEW":
            with st.expander("Runner Contract Simulator · somente desenho", expanded=False):
                st.caption(
                    "Este formulário não executa comandos. Ele apenas verifica se existe informação "
                    "suficiente para descrever um runner isolado e revisável."
                )
                st.caption(
                    "content_binding_verified não é prova. O runner exige um Content "
                    "Attestation Contract, e um checkbox não o substitui."
                )
                human_patch_reviewed = st.checkbox(
                    "O patch exato foi revisado por uma pessoa independente",
                    key="aion_developer_runner_patch_reviewed",
                    value=False,
                )
                human_patch_reviewer = st.text_input(
                    "Revisor humano do patch",
                    key="aion_developer_runner_patch_reviewer",
                    max_chars=160,
                )
                runner_review_refs = st.text_area(
                    "Referências da revisão do patch — uma por linha",
                    key="aion_developer_runner_patch_review_refs",
                    max_chars=4000,
                )
                if st.button(
                    "Preparar Runner Contract Simulator",
                    key="aion_developer_runner_prepare",
                ):
                    try:
                        runner_contract = build_developer_runner_contract(
                            builder_request,
                            preflight,
                            patch_validation,
                            content_attestation=None,
                            human_patch_reviewed=human_patch_reviewed,
                            human_patch_reviewer=human_patch_reviewer,
                            human_patch_review_refs=[
                                line.strip()
                                for line in runner_review_refs.splitlines()
                                if line.strip()
                            ],
                        )
                        st.session_state["aion_developer_runner_contract"] = runner_contract
                    except Exception as exc:
                        st.error(f"Runner Contract recusado: {type(exc).__name__}")

    runner_contract = (
        st.session_state.get("aion_developer_runner_contract")
        if isinstance(st.session_state.get("aion_developer_runner_contract"), Mapping)
        else None
    )
    if isinstance(runner_contract, Mapping):
        st.markdown("##### Runner Contract Simulator · não executável")
        rc1,rc2,rc3,rc4 = st.columns(4)
        rc1.metric("Estado", str(runner_contract.get("state") or "UNKNOWN"))
        rc2.metric("Executor", "LIGADO" if runner_contract.get("executor_attached") else "NÃO LIGADO")
        rc3.metric("Execução", "AUTORIZADA" if runner_contract.get("execution_authorized") else "BLOQUEADA")
        rc4.metric("Comandos executados", "SIM" if runner_contract.get("commands_executed") else "NÃO")

        if runner_contract.get("blockers"):
            st.warning(
                "Runner design bloqueado: "
                + " · ".join(str(x) for x in list(runner_contract.get("blockers") or []))
            )
        else:
            st.success(
                "Contrato suficiente apenas para revisão do desenho do runner. "
                "Nenhum executor foi conectado."
            )

        if runner_contract.get("command_plan"):
            st.markdown("**Plano de comandos — somente dados:**")
            st.dataframe(
                [
                    {
                        "Etapa": row.get("step"),
                        "Executável": row.get("executable"),
                        "ARGV": " ".join(str(x) for x in list(row.get("argv") or [])),
                        "Shell": row.get("shell"),
                        "Rede": row.get("network"),
                        "Escreve repo": row.get("writes_repo"),
                    }
                    for row in list(runner_contract.get("command_plan") or [])
                    if isinstance(row, Mapping)
                ],
                width="stretch",
                hide_index=True,
            )
        st.caption(
            f"{runner_contract.get('runner_contract_id')} · command_plan_is_data_only=True · "
            "shell_allowed=False · network_allowed=False · secrets_allowed=False · "
            "repo_write_allowed=False · execution_authorized=False."
        )
        st.info(
            "Enquanto revision_content_verified continuar falso no Patch Validator, "
            "o runner permanece bloqueado por desenho. Isso é intencional."
        )

        if runner_contract.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW":
            if st.button(
                "Validar Command Allowlist Contract",
                key="aion_developer_command_policy_prepare",
            ):
                try:
                    stored_attestation = st.session_state.get("aion_developer_content_attestation")
                    command_policy = build_developer_command_policy_contract(
                        runner_contract,
                        builder_request=builder_request,
                        preflight=preflight,
                        patch_validation=patch_validation,
                        content_attestation=(
                            stored_attestation if isinstance(stored_attestation, Mapping) else None
                        ),
                    )
                    st.session_state["aion_developer_command_policy"] = command_policy
                except Exception as exc:
                    st.error(f"Command Allowlist recusada: {type(exc).__name__}")

    command_policy = (
        st.session_state.get("aion_developer_command_policy")
        if isinstance(st.session_state.get("aion_developer_command_policy"), Mapping)
        else None
    )
    if isinstance(command_policy, Mapping):
        st.markdown("##### Command Allowlist Contract · somente dados")
        cp1,cp2,cp3,cp4 = st.columns(4)
        cp1.metric("Estado", str(command_policy.get("state") or "UNKNOWN"))
        cp2.metric("Exec pinning", "OK" if command_policy.get("executable_pinning_verified") else "PENDENTE")
        cp3.metric("OS sandbox", "OK" if command_policy.get("os_sandbox_verified") else "PENDENTE")
        cp4.metric("Execução", "AUTORIZADA" if command_policy.get("execution_authorized") else "BLOQUEADA")

        if command_policy.get("blockers"):
            st.warning(
                "Allowlist bloqueada: "
                + " · ".join(str(x) for x in list(command_policy.get("blockers") or []))
            )
        else:
            st.success(
                "Templates argv exatos conferem. Ainda falta pinning dos executáveis "
                "e prova do isolamento de sistema operacional."
            )

        if command_policy.get("hazards"):
            st.markdown("**Riscos que continuam explícitos:**")
            for item in list(command_policy.get("hazards") or []):
                st.markdown(f"- {item}")

        if command_policy.get("required_before_future_execution"):
            st.markdown("**Obrigatório antes de qualquer execução futura:**")
            for item in list(command_policy.get("required_before_future_execution") or []):
                st.markdown(f"- {item}")

        st.caption(
            f"{command_policy.get('command_policy_id')} · EXACT_ARGV_TEMPLATES · "
            "command_policy_is_data_only=True · execution_authorized=False · "
            "executor_attached=False · commands_executed=False."
        )


def _render_development(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    source_checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 🛠️ AION Desenvolvedor")
    _render_persona_capabilities("developer", {
        "code": True,
        "logs": bool(runtime_result),
        "tests": isinstance((checkpoint.get("operating") or {}).get("events"), list),
        "errors": bool(runtime_result),
        "patch_plan": True,
        "rollback": True,
    })
    _context_voice(
        "Desenvolvimento",
        (
            "Bem-vindo ao AION Desenvolvedor. As missões de código seguem branch ou Sandbox, testes, "
            "checkpoint, revisão e Guardian. Mudanças críticas não são publicadas silenciosamente."
        ),
        key="aion_development_voice",
    )
    _render_developer_intelligence()
    with st.expander("Política de confiança e rollback do AION Desenvolvedor"):
        policy = developer_trust_policy()
        for row in policy["levels"]:
            st.markdown(f"- **Nível {row['level']} · {row['name']}:** {row['may']} Portão humano: {row['human_gate']}.")
        st.markdown("**Nunca, em nenhum nível:**")
        for item in policy["forbidden"]:
            st.markdown(f"- {item}")
        st.markdown("**Rollback:**")
        for item in policy["rollback"]:
            st.markdown(f"- {item}")
    objective = st.text_area(
        "Missão de desenvolvimento",
        key="aion_dev_mission",
        placeholder="Ex.: revisar a interface do Administrador e corrigir contraste sem alterar o motor.",
    )
    if st.button("Montar missão segura", key="aion_dev_plan"):
        st.session_state["aion_dev_plan_result"] = mission_plan(objective)
    plan = st.session_state.get("aion_dev_plan_result")
    if isinstance(plan, Mapping):
        st.write(f"**Missão:** {plan.get('mission_id')} · domínio {plan.get('domain')}")
        for idx, step in enumerate(plan.get("steps", []), start=1):
            st.markdown(f"{idx}. {step}")

    st.markdown("#### Missões persistentes")
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    mission_summary = continuity_summary(missions, handoffs)
    mc1,mc2,mc3,mc4 = st.columns(4)
    mc1.metric("Total", mission_summary["total_missions"])
    mc2.metric("Ativas", mission_summary["active_missions"])
    mc3.metric("Bloqueadas", mission_summary["blocked_missions"])
    mc4.metric("Concluídas", mission_summary["done_missions"])

    with st.form("aion_persistent_mission_form", clear_on_submit=True):
        mission_title = st.text_input("Título da missão persistente")
        mission_domain = st.selectbox(
            "Área da missão",
            ["central","trading","studio","business","laboratory","secretary","development","subscriptions","promotions"],
            index=6,
        )
        mission_objective = st.text_area("Objetivo / escopo", max_chars=1600)
        mission_next = st.text_area("Próxima ação registrada", max_chars=1600)
        create_mission = st.form_submit_button("Registrar missão no Checkpoint", type="primary")

    if create_mission:
        try:
            mission = new_mission(
                mission_title,
                domain=mission_domain,
                objective=mission_objective,
                next_action=mission_next,
                source=str(access.get("username") or "ADMIN"),
            )
            missions = upsert_mission(missions, mission)
            updated = update_continuity_checkpoint(
                checkpoint,
                missions=missions,
                handoffs=handoffs,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "mission_registered",
                f"Missão persistente registrada: {mission['title']}",
                evidence={
                    "mission_id":mission["mission_id"],
                    "domain":mission["domain"],
                    "status":mission["status"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Missão registrada na memória de trabalho do AION.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível registrar a missão: {type(exc).__name__}")

    if missions:
        st.dataframe(
            [{
                "ID":item.get("mission_id"),
                "Status":item.get("status"),
                "Área":item.get("domain"),
                "Missão":item.get("title"),
                "Próxima ação":item.get("next_action"),
                "Atualizada":item.get("updated_at"),
            } for item in reversed(missions[-80:])],
            width="stretch",
            hide_index=True,
        )
        mission_ids=[str(item.get("mission_id") or "") for item in missions]
        selected_mission_id=st.selectbox(
            "Missão selecionada",
            mission_ids,
            key="aion_persistent_mission_selected",
        )
        selected_mission=next(
            (item for item in missions if str(item.get("mission_id") or "")==selected_mission_id),
            None,
        )
        if isinstance(selected_mission, Mapping):
            status_index = list(MISSION_STATUSES).index(
                str(selected_mission.get("status") or "PLANNED")
                if str(selected_mission.get("status") or "PLANNED") in MISSION_STATUSES
                else "PLANNED"
            )
            next_status = st.selectbox(
                "Novo estado da missão",
                list(MISSION_STATUSES),
                index=status_index,
                key="aion_persistent_mission_status",
            )
            mission_outcome = st.text_area(
                "Resultado / conclusão registrada",
                value=str(selected_mission.get("outcome") or ""),
                key="aion_persistent_mission_outcome",
                max_chars=1600,
            )
            mission_blocker = st.text_area(
                "Bloqueio registrado",
                value=str(selected_mission.get("blocker") or ""),
                key="aion_persistent_mission_blocker",
                max_chars=1600,
            )
            mission_next_action = st.text_area(
                "Próxima ação",
                value=str(selected_mission.get("next_action") or ""),
                key="aion_persistent_mission_next",
                max_chars=1600,
            )
            evidence_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                value=", ".join(list(selected_mission.get("evidence_refs") or [])),
                key="aion_persistent_mission_evidence",
            )
            previous_status = str(selected_mission.get("status") or "PLANNED")
            approval_explicit = False
            unblock_text = ""
            if previous_status == "WAITING_APPROVAL" and next_status == "IN_PROGRESS":
                if "aion_persistent_mission_approve" not in st.session_state:
                    st.session_state["aion_persistent_mission_approve"] = False
                approval_explicit = bool(st.checkbox(
                    "Aprovo explicitamente a retomada desta missão",
                    key="aion_persistent_mission_approve",
                ))
            if previous_status == "BLOCKED" and next_status == "IN_PROGRESS":
                if "aion_persistent_mission_unblock" not in st.session_state:
                    st.session_state["aion_persistent_mission_unblock"] = ""
                unblock_text = str(st.text_input(
                    "Motivo do desbloqueio",
                    key="aion_persistent_mission_unblock",
                ) or "")
            if st.button(
                "Atualizar missão persistente",
                key="aion_persistent_mission_update",
                width="stretch",
            ):
                try:
                    evidence_refs=[x.strip() for x in evidence_text.split(",") if x.strip()]
                    prepared = prepare_mission_transition(
                        previous_status,
                        next_status,
                        approved=approval_explicit,
                        unblock_reason=unblock_text,
                        actor=str(access.get("username") or access.get("role") or "ADMIN"),
                        changed_at=datetime.now(timezone.utc).isoformat(),
                        evidence_refs=evidence_refs,
                        mission_id=selected_mission_id,
                    )
                    missions = transition_mission(
                        missions,
                        selected_mission_id,
                        next_status,
                        outcome=mission_outcome,
                        blocker=mission_blocker,
                        next_action=mission_next_action,
                        evidence_refs=prepared["evidence_refs"],
                        changed_at=prepared["changed_at"],
                        approved=prepared["approved"],
                        unblock_reason=prepared["unblock_reason"],
                    )
                    updated = update_continuity_checkpoint(
                        checkpoint,
                        missions=missions,
                        handoffs=handoffs,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "mission_updated",
                        f"Missão persistente atualizada: {selected_mission_id}",
                        evidence={
                            "mission_id":selected_mission_id,
                            "status":next_status,
                            "actor":prepared["actor"],
                            "approved":prepared["approved"],
                            "unblock_reason":prepared["unblock_reason"],
                            "changed_at":prepared["changed_at"],
                            "automatic_execution":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success("Missão atualizada localmente no Checkpoint.")
                    st.rerun()
                except Exception as exc:
                    st.error(
                        f"Não foi possível atualizar a missão: {type(exc).__name__}: {exc}"
                    )

    st.markdown("#### 🔌 Tool Hub / MCP + Tarefas Duráveis")
    tool_hub = checkpoint.get("tool_hub") if isinstance(checkpoint.get("tool_hub"), Mapping) else {}
    portable_core = checkpoint.get("portable_core") if isinstance(checkpoint.get("portable_core"), Mapping) else {}
    durable_section = checkpoint.get("durable_tasks") if isinstance(checkpoint.get("durable_tasks"), Mapping) else {}
    durable_records = list(durable_section.get("records", []) or [])
    hub_state = tool_hub_summary(tool_hub, portable_core)
    durable_state = durable_tasks_summary(durable_records)

    th1,th2,th3,th4 = st.columns(4)
    th1.metric("Ferramentas registradas", int(hub_state.get("tools") or 0))
    th2.metric("Locais prontas", int(hub_state.get("local_ready") or 0))
    th3.metric("Tarefas retomáveis", int(durable_state.get("resumable") or 0))
    th4.metric("Aguardando aprovação", int(durable_state.get("waiting_approval") or 0))
    st.caption(
        "Tool Hub organiza NATIVE/API/MCP/FILE/WEBHOOK, mas não chama ferramenta nesta tela. "
        "Retomar uma tarefa restaura contexto/cursor; não executa o próximo passo automaticamente."
    )
    local_catalog = local_allowlist()
    local_ids = {item["tool_id"] for item in local_catalog}
    registered = normalize_tool_hub(tool_hub)["tools"]
    phase_tools = [
        item for item in registered
        if item["tool_id"] in local_ids
        and item["state"] == "LOCAL_READY"
        and not item["connector_id"]
        and item["kind"] in {"READ", "SEARCH", "DRAFT"}
    ]
    kind_counts = {kind: sum(1 for item in phase_tools if item["kind"] == kind) for kind in ("READ", "SEARCH", "DRAFT")}
    last_local_tool = str(st.session_state.get("aion_local_tool_last_id") or "").strip()
    st.markdown("##### Tool Hub local")
    lc1, lc2, lc3 = st.columns(3)
    lc1.metric("Registradas", len(registered))
    lc2.metric("Local ready", int(hub_state.get("local_ready") or 0))
    lc3.metric("Executáveis nesta fase", len(phase_tools))
    st.caption(
        "READ {read} · SEARCH {search} · DRAFT {draft}. "
        "Último tool_id: {last}. Efeitos externos: nenhum. "
        "Esta seção não executa ferramenta.".format(
            read=kind_counts["READ"],
            search=kind_counts["SEARCH"],
            draft=kind_counts["DRAFT"],
            last=last_local_tool or "nenhum",
        )
    )


    tools = [
        dict(item) for item in list(tool_hub.get("tools", []) or [])
        if isinstance(item, Mapping)
    ]
    if tools:
        with st.expander("Catálogo do Tool Hub", expanded=False):
            st.dataframe([
                {
                    "Tool":item.get("tool_id"),
                    "Workspace":item.get("workspace_id"),
                    "Conector":item.get("connector_id") or "local",
                    "Tipo":item.get("kind"),
                    "Estado":item.get("state"),
                    "Efeito externo":"SIM" if item.get("external_side_effects") else "NÃO",
                }
                for item in tools
            ], width="stretch", hide_index=True)
            tool_ids=[str(item.get("tool_id") or "") for item in tools if str(item.get("tool_id") or "")]
            if tool_ids:
                selected_tool=st.selectbox(
                    "Ferramenta para pré-voo (não executa)",
                    tool_ids,
                    key="aion_tool_hub_preview_tool",
                )
                if st.button("Ver pré-voo do Tool Hub", key="aion_tool_hub_preview"):
                    preview=plan_tool_call(
                        selected_tool,
                        hub=tool_hub,
                        portable_core=portable_core,
                        access=access,
                        source_kind="ADMIN",
                        authenticated_admin=is_admin(access),
                        approved=False,
                        feature_flags=flags,
                        scope="Pré-voo consultivo na Central de Desenvolvimento.",
                        uncertainty_pct=10,
                        impact="LOW",
                        reversible=True,
                    )
                    st.session_state["aion_tool_hub_preview_result"]=preview
                preview=st.session_state.get("aion_tool_hub_preview_result")
                if isinstance(preview, Mapping):
                    st.caption(
                        f"Estado: {preview.get('state')} · tool_called: {preview.get('tool_called',False)} · "
                        f"connector_called: {preview.get('connector_called',False)}."
                    )
                    for blocker in list(preview.get("blockers") or [])[:8]:
                        st.markdown(f"- {blocker}")

    with st.expander("Registrar tarefa durável", expanded=False):
        with st.form("aion_durable_task_new", clear_on_submit=True):
            durable_title=st.text_input("Título da tarefa durável")
            durable_objective=st.text_area("Objetivo", max_chars=1400)
            durable_steps_text=st.text_area(
                "Passos — um por linha",
                value="Especificar\nImplementar em Sandbox\nRodar testes\nRevisar evidências",
                max_chars=3000,
            )
            create_durable=st.form_submit_button("Registrar tarefa durável", type="primary")
        if create_durable:
            try:
                step_titles=[x.strip() for x in durable_steps_text.splitlines() if x.strip()]
                step_rows=[
                    {
                        "step_id":f"S{idx:03d}",
                        "title":title,
                        "state":"PENDING",
                        "guardian_action":"read",
                        "requires_approval":False,
                    }
                    for idx,title in enumerate(step_titles,start=1)
                ]
                durable=new_durable_task(
                    durable_title,
                    objective=durable_objective,
                    domain="development",
                    steps=step_rows,
                    checkpoint_digest=checkpoint_source_digest(source_checkpoint),
                    source=str(access.get("username") or "ADMIN"),
                )
                durable_records=upsert_durable_task(durable_records,durable)
                updated=update_durable_tasks_checkpoint(
                    checkpoint,
                    records=durable_records,
                    dirty=True,
                )
                updated=_record_working_event(
                    updated,
                    "durable_task_registered",
                    f"Tarefa durável registrada: {durable['title']}",
                    evidence={
                        "durable_task_id":durable["durable_task_id"],
                        "steps":len(durable["steps"]),
                        "automatic_resume_executes":False,
                    },
                )
                _set_working_checkpoint(updated,dirty=True)
                st.success("Tarefa durável registrada no Checkpoint de trabalho.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar a tarefa durável: {type(exc).__name__}")

    if durable_records:
        with st.expander("Retomar tarefa durável", expanded=False):
            durable_options={
                f"{item.get('durable_task_id')} · {item.get('title')}":item
                for item in durable_records
                if isinstance(item,Mapping)
            }
            durable_label=st.selectbox(
                "Tarefa",
                list(durable_options.keys()),
                key="aion_durable_resume_selected",
            )
            selected_durable=durable_options[durable_label]
            if st.button("Preparar retomada",key="aion_durable_prepare_resume"):
                resume=prepare_resume(
                    selected_durable,
                    expected_revision=selected_durable.get("revision"),
                    checkpoint_digest=checkpoint_source_digest(source_checkpoint),
                )
                st.session_state["aion_durable_resume_preview"]=resume
            resume=st.session_state.get("aion_durable_resume_preview")
            if isinstance(resume,Mapping):
                st.write(
                    f"**Retomada:** {resume.get('state')} · cursor {resume.get('cursor')} · "
                    f"revisão {resume.get('revision')}"
                )
                next_step=resume.get("next_step")
                if isinstance(next_step,Mapping):
                    st.info(
                        f"Próximo passo registrado: **{next_step.get('title')}** · "
                        f"estado {next_step.get('state')}."
                    )
                for blocker in list(resume.get("blockers") or [])[:8]:
                    st.warning(str(blocker))
                st.caption("Retomada restaura estado; execução automática: NÃO.")
            if st.button("Registrar evento de retomada",key="aion_durable_record_resume"):
                try:
                    if not isinstance(resume,Mapping) or resume.get("durable_task_id")!=selected_durable.get("durable_task_id"):
                        raise ValueError("Prepare a retomada da tarefa selecionada primeiro.")
                    resumed=record_resume(
                        selected_durable,
                        expected_revision=resume.get("revision"),
                        checkpoint_digest=checkpoint_source_digest(source_checkpoint),
                    )
                    durable_records=upsert_durable_task(durable_records,resumed)
                    updated=update_durable_tasks_checkpoint(
                        checkpoint,
                        records=durable_records,
                        dirty=True,
                    )
                    updated=_record_working_event(
                        updated,
                        "durable_task_resumed",
                        f"Contexto de tarefa durável retomado: {resumed['durable_task_id']}",
                        evidence={
                            "durable_task_id":resumed["durable_task_id"],
                            "resume_generation":resumed["resume_generation"],
                            "automatic_execution":False,
                        },
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.success("Retomada registrada como estado; nenhum passo foi executado.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível registrar a retomada: {type(exc).__name__}")

    st.markdown("#### 🧬 Digital Twin + Dev Fusion + Release Confidence")
    digital_section = checkpoint.get("digital_twins") if isinstance(checkpoint.get("digital_twins"), Mapping) else {}
    twin_records = list(digital_section.get("records", []) or [])
    fusion_section = checkpoint.get("dev_fusion") if isinstance(checkpoint.get("dev_fusion"), Mapping) else {}
    fusion_pipelines = list(fusion_section.get("pipelines", []) or [])
    confidence_section = checkpoint.get("release_confidence") if isinstance(checkpoint.get("release_confidence"), Mapping) else {}
    confidence_records = list(confidence_section.get("records", []) or [])
    twin_state = digital_twin_summary(twin_records)
    fusion_state = dev_fusion_summary(fusion_pipelines)
    confidence_state = release_confidence_summary(confidence_records)

    df1,df2,df3,df4 = st.columns(4)
    df1.metric("Digital Twins", int(twin_state.get("twins") or 0))
    df2.metric("Twins prontos p/ avaliação", int(twin_state.get("ready_for_evaluation") or 0))
    df3.metric("Dev Fusion · revisão humana", int(fusion_state.get("human_review_candidates") or 0))
    df4.metric("Release Confidence · revisão", int(confidence_state.get("human_review_ready") or 0))
    st.caption(
        "Digital Twin simula e registra evidência. Dev Fusion separa Builder, Reviewer e Breaker. "
        "Release Confidence mede cobertura de evidência; não é probabilidade e nunca autoriza merge/deploy."
    )

    with st.expander("Criar Digital Twin", expanded=False):
        with st.form("aion_digital_twin_new", clear_on_submit=True):
            twin_title = st.text_input("Título da mudança")
            twin_baseline = st.text_input("Baseline", placeholder="Ex.: main@sha")
            twin_candidate = st.text_input("Candidato", placeholder="Ex.: branch@sha")
            twin_scope_text = st.text_area("Escopo — um item por linha", max_chars=2500)
            twin_dependencies_text = st.text_area("Dependências — uma por linha", max_chars=2500)
            twin_impacts_text = st.text_area("Impactos esperados — um por linha", max_chars=2500)
            twin_rollback = st.text_area("Plano de rollback", max_chars=1800)
            create_twin = st.form_submit_button("Registrar Digital Twin")
        if create_twin:
            try:
                twin = new_digital_twin(
                    twin_title,
                    baseline_ref=twin_baseline,
                    candidate_ref=twin_candidate,
                    scope=[x.strip() for x in twin_scope_text.splitlines() if x.strip()],
                    dependencies=[x.strip() for x in twin_dependencies_text.splitlines() if x.strip()],
                    expected_impacts=[x.strip() for x in twin_impacts_text.splitlines() if x.strip()],
                    rollback_plan=twin_rollback,
                    created_by=str(access.get("username") or "ADMIN"),
                )
                twin_records = upsert_digital_twin(twin_records, twin)
                updated = update_digital_twins_checkpoint(checkpoint, records=twin_records, dirty=True)
                updated = _record_working_event(
                    updated,
                    "digital_twin_registered",
                    f"Digital Twin registrado: {twin['twin_id']}",
                    evidence={"twin_id":twin["twin_id"],"production_touched":False},
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Digital Twin registrado. Produção não foi tocada.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar o Digital Twin: {type(exc).__name__}")

    selected_twin = None
    if twin_records:
        twin_options = {
            f"{item.get('twin_id')} · {item.get('title')} · {item.get('state')}":item
            for item in twin_records if isinstance(item, Mapping)
        }
        twin_label = st.selectbox("Digital Twin ativo", list(twin_options.keys()), key="aion_dev_twin_selected")
        selected_twin = twin_options[twin_label]
        st.caption(
            f"Baseline: {selected_twin.get('baseline_ref')} · Candidato: {selected_twin.get('candidate_ref')} · "
            f"Estado: {selected_twin.get('state')}."
        )
        for blocker in list(selected_twin.get("blockers") or [])[:8]:
            st.warning(str(blocker))

        with st.expander("Registrar observação do Digital Twin", expanded=False):
            with st.form("aion_digital_twin_observation", clear_on_submit=True):
                obs_area = st.text_input("Área", value="tests")
                obs_claim = st.text_area("Observação / claim", max_chars=900)
                obs_impact = st.selectbox("Impacto", ["LOW","MEDIUM","HIGH","CRITICAL"], index=1)
                obs_baseline = st.text_input("Valor baseline")
                obs_candidate = st.text_input("Valor candidato")
                obs_uncertainty = st.number_input("Incerteza %", min_value=0.0, max_value=100.0, value=10.0, step=1.0)
                obs_evidence = st.text_area("Referências de evidência — uma por linha", max_chars=2200)
                obs_critical = st.checkbox("Esta evidência confirma bloqueio crítico", value=False)
                save_observation = st.form_submit_button("Registrar observação")
            if save_observation:
                try:
                    changed = record_twin_observation(
                        selected_twin,
                        area=obs_area,
                        claim=obs_claim,
                        impact=obs_impact,
                        baseline_value=obs_baseline,
                        candidate_value=obs_candidate,
                        uncertainty_pct=obs_uncertainty,
                        evidence_refs=[x.strip() for x in obs_evidence.splitlines() if x.strip()],
                        critical_blocker=bool(obs_critical),
                    )
                    twin_records = upsert_digital_twin(twin_records, changed)
                    updated = update_digital_twins_checkpoint(checkpoint, records=twin_records, dirty=True)
                    _set_working_checkpoint(updated, dirty=True)
                    st.success(f"Observação registrada. Twin: {changed['state']}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível registrar a observação: {type(exc).__name__}")

        if st.button("Criar pipeline Dev Fusion deste Twin", key="aion_dev_fusion_create"):
            try:
                pipeline = new_dev_fusion_pipeline(
                    f"Pipeline · {selected_twin.get('title')}",
                    twin_id=selected_twin.get("twin_id"),
                    baseline_ref=selected_twin.get("baseline_ref"),
                    candidate_ref=selected_twin.get("candidate_ref"),
                    created_by=str(access.get("username") or "ADMIN"),
                )
                fusion_pipelines = upsert_pipeline(fusion_pipelines, pipeline)
                updated = update_dev_fusion_checkpoint(checkpoint, pipelines=fusion_pipelines, dirty=True)
                _set_working_checkpoint(updated, dirty=True)
                st.success("Pipeline Dev Fusion registrado; nenhuma ferramenta foi executada.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível criar o pipeline: {type(exc).__name__}")

    selected_pipeline = None
    if fusion_pipelines:
        pipeline_options = {
            f"{item.get('pipeline_id')} · {item.get('candidate_ref')} · {item.get('state')}":item
            for item in fusion_pipelines if isinstance(item, Mapping)
        }
        pipeline_label = st.selectbox("Pipeline Dev Fusion", list(pipeline_options.keys()), key="aion_dev_fusion_selected")
        selected_pipeline = pipeline_options[pipeline_label]
        st.caption(
            f"Estado: {selected_pipeline.get('state')} · merge automático: NÃO · deploy automático: NÃO."
        )
        with st.expander("Registrar evidência de etapa Dev Fusion", expanded=False):
            with st.form("aion_dev_fusion_stage", clear_on_submit=True):
                fusion_stage = st.selectbox("Etapa", list(DEV_FUSION_STAGES))
                fusion_stage_state = st.selectbox("Estado", ["RUNNING","PASS","FAIL","BLOCKED","WAITING_HUMAN"])
                fusion_actor = st.text_input("Ator / agente responsável", placeholder="Ex.: reviewer-independent")
                fusion_evidence = st.text_area("Evidências — uma por linha", max_chars=2400)
                fusion_summary_text = st.text_area("Resumo da etapa", max_chars=1200)
                fusion_critical = st.number_input("Achados críticos", min_value=0, value=0, step=1)
                eval_run_ref = st.text_input("Evaluation Run ID (somente etapa EVALUATE)")
                save_fusion_stage = st.form_submit_button("Registrar etapa")
            if save_fusion_stage:
                try:
                    changed = record_dev_fusion_stage(
                        selected_pipeline,
                        fusion_stage,
                        state=fusion_stage_state,
                        actor_ref=fusion_actor,
                        evidence_refs=[x.strip() for x in fusion_evidence.splitlines() if x.strip()],
                        summary=fusion_summary_text,
                        critical_findings=fusion_critical,
                        evaluation_run_id=eval_run_ref,
                    )
                    fusion_pipelines = upsert_pipeline(fusion_pipelines, changed)
                    updated = update_dev_fusion_checkpoint(checkpoint, pipelines=fusion_pipelines, dirty=True)
                    _set_working_checkpoint(updated, dirty=True)
                    st.success(f"Etapa registrada. Pipeline: {changed['state']}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Etapa recusada em modo seguro: {type(exc).__name__}")

        if st.button("Calcular Release Confidence consultivo", key="aion_release_confidence_preview"):
            pipeline = selected_pipeline
            twin = next(
                (x for x in twin_records if isinstance(x,Mapping) and x.get("twin_id")==pipeline.get("twin_id")),
                None,
            )
            eval_lab = checkpoint.get("evaluation_lab") if isinstance(checkpoint.get("evaluation_lab"), Mapping) else {}
            eval_run = next(
                (
                    x for x in list(eval_lab.get("runs",[]) or [])
                    if isinstance(x,Mapping) and x.get("run_id")==pipeline.get("evaluation_run_id")
                ),
                None,
            )
            twin_refs = [
                ref
                for obs in list((twin or {}).get("observations",[]) or [])
                if isinstance(obs,Mapping)
                for ref in list(obs.get("evidence_refs",[]) or [])
            ]
            fusion_refs = [
                ref
                for stage in list(pipeline.get("stages",[]) or [])
                if isinstance(stage,Mapping)
                for ref in list(stage.get("evidence_refs",[]) or [])
            ]
            eval_refs = list((eval_run or {}).get("evidence_refs",[]) or []) if isinstance(eval_run,Mapping) else []
            dimensions = [
                evidence_dimension(
                    "DIGITAL_TWIN",
                    confirmed=bool(twin and twin.get("state")=="READY_FOR_EVALUATION"),
                    evidence_refs=twin_refs,
                    blocker=bool(twin and twin.get("state")=="BLOCKED"),
                    detail="Digital Twin deve estar pronto para avaliação.",
                ),
                evidence_dimension(
                    "DEV_FUSION",
                    confirmed=bool(pipeline.get("state") in {"HUMAN_REVIEW_CANDIDATE","DONE"}),
                    evidence_refs=fusion_refs,
                    blocker=bool(pipeline.get("state")=="BLOCKED"),
                    detail="Builder, Reviewer, Breaker e Evaluation precisam de evidência independente.",
                ),
                evidence_dimension(
                    "EVALUATION",
                    confirmed=bool(isinstance(eval_run,Mapping) and eval_run.get("state")=="HUMAN_REVIEW_CANDIDATE"),
                    evidence_refs=eval_refs,
                    blocker=bool(isinstance(eval_run,Mapping) and eval_run.get("state")=="REJECTED_FOR_NOW"),
                    detail="Evaluation Lab precisa chegar apenas a HUMAN_REVIEW_CANDIDATE.",
                ),
                evidence_dimension("QUALITY",confirmed=False,evidence_refs=[],detail="CI verificado ainda não foi anexado a este snapshot."),
                evidence_dimension("RELEASE_GATE",confirmed=False,evidence_refs=[],detail="Release Gate de produção não é inferido nesta tela."),
                evidence_dimension(
                    "ROLLBACK",
                    confirmed=False,
                    evidence_refs=[],
                    detail="Plano existe no Twin, mas prova de rollback ensaiado ainda precisa de evidência.",
                ),
            ]
            confidence = release_confidence(
                candidate_ref=pipeline.get("candidate_ref"),
                dimensions=dimensions,
            )
            confidence_records = [
                x for x in confidence_records
                if not (isinstance(x,Mapping) and x.get("candidate_ref")==confidence.get("candidate_ref"))
            ] + [confidence]
            updated = update_release_confidence_checkpoint(
                checkpoint,
                records=confidence_records,
                dirty=True,
            )
            _set_working_checkpoint(updated, dirty=True)
            st.session_state["aion_release_confidence_preview_result"] = confidence
            st.rerun()

    confidence_preview = st.session_state.get("aion_release_confidence_preview_result")
    if isinstance(confidence_preview, Mapping):
        st.write(
            f"**Release Confidence:** {confidence_preview.get('state')} · "
            f"cobertura de evidência {confidence_preview.get('evidence_coverage_pct')}%."
        )
        st.caption("Cobertura de evidência não é probabilidade de sucesso e não autoriza merge/deploy.")
        for row in list(confidence_preview.get("dimensions") or []):
            if isinstance(row,Mapping):
                st.markdown(
                    f"- {row.get('dimension')}: "
                    f"{'CONFIRMADA' if row.get('confirmed') else 'PENDENTE'}"
                    + (" · BLOQUEIO" if row.get("blocker") else "")
                )

    st.markdown("#### Checkpoint Mestre")
    cfg = _runtime_config()
    runtime_cfg_state = runtime_configuration_status(cfg)
    st.caption(
        f"Proveniência ativa: {runtime_result.get('source') or runtime_result.get('status')}. "
        f"Digest local: {checkpoint_digest(checkpoint)}."
    )
    rp1,rp2,rp3 = st.columns(3)
    rp1.metric("Runtime · leitura", "PRONTA" if runtime_cfg_state.get("read_ready") else "BLOQUEADA")
    rp2.metric("Runtime · escrita", "PRONTA" if runtime_cfg_state.get("write_ready") else "SEM CREDENCIAL")
    rp3.metric("Modo", str(runtime_cfg_state.get("mode") or "UNAVAILABLE"))
    st.caption(
        "Leitura pública do Checkpoint pode funcionar sem token. Escrita continua exigindo credencial "
        "e aprovação explícita; nenhum segredo é exibido nesta tela."
    )
    conflict = bool(st.session_state.get(_WORKING_CONFLICT_KEY, False))
    if conflict:
        st.error(
            "Conflito detectado: o Checkpoint Mestre do runtime mudou enquanto existem alterações locais. "
            "O AION não vai sobrescrever a versão nova automaticamente."
        )
        if st.button("↩️ Descartar alterações locais e recarregar runtime", key="aion_reload_runtime_checkpoint"):
            _set_working_checkpoint(source_checkpoint, dirty=False)
            st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(source_checkpoint)
            st.session_state[_WORKING_CONFLICT_KEY] = False
            st.rerun()

    persistence_preflight = runtime_write_preflight(runtime_result)
    persisted_arm_required = False
    if persisted_arming_transition_required is not None:
        try:
            persisted_arm_required = bool(
                persisted_arming_transition_required(
                    checkpoint,
                    source_checkpoint,
                )
            )
        except Exception:
            persisted_arm_required = True

    persistence_blocked = bool(
        conflict
        or not persistence_preflight.get("allowed")
        or persisted_arm_required
    )
    if not persistence_preflight.get("allowed"):
        st.caption(
            "Persistência bloqueada em modo seguro: "
            f"{persistence_preflight.get('reason','estado runtime não confirmado')}."
        )

    if persisted_arm_required:
        st.warning(
            "Este Checkpoint contém uma nova transição para Global Worker ARMED. "
            "O save genérico está BLOQUEADO. Use a Persisted Arming Ceremony abaixo."
        )
        st.markdown("##### 🔐 Persisted Arming Ceremony")

        if st.button(
            "🔎 Verificar feature flag antes da persistência",
            key="aion_global_persist_check_flag",
            disabled=read_repository_feature_flag is None,
            width="stretch",
        ):
            try:
                evidence = read_repository_feature_flag(cfg)
                st.session_state[_AION_GLOBAL_PERSIST_FLAG_EVIDENCE_KEY] = evidence
                if (
                    evidence.get("status") == "CONFIRMED"
                    and evidence.get("safe_for_arming_persistence") is True
                ):
                    st.success(
                        "Feature flag comprovada como "
                        + str(evidence.get("state") or "UNKNOWN")
                        + ". Nenhuma variável foi alterada."
                    )
                else:
                    st.error(
                        "Persistência continua bloqueada: não foi possível provar "
                        "que a feature flag está desligada."
                    )
            except Exception as exc:
                st.error(
                    "Leitura da feature flag falhou em modo seguro: "
                    + type(exc).__name__
                    + "."
                )

        persist_flag_evidence = st.session_state.get(
            _AION_GLOBAL_PERSIST_FLAG_EVIDENCE_KEY
        )
        flag_safe = bool(
            isinstance(persist_flag_evidence, Mapping)
            and persist_flag_evidence.get("status") == "CONFIRMED"
            and persist_flag_evidence.get("safe_for_arming_persistence") is True
        )
        if isinstance(persist_flag_evidence, Mapping):
            pf1, pf2 = st.columns(2)
            pf1.metric(
                "Feature flag",
                str(persist_flag_evidence.get("state") or "UNKNOWN"),
            )
            pf2.metric(
                "Seguro para persistir",
                "SIM" if flag_safe else "NÃO",
            )

        persist_ttl = int(st.number_input(
            "TTL da autorização de persistência (segundos)",
            min_value=300,
            max_value=1800,
            value=600,
            step=300,
            key="aion_global_persist_ttl",
        ))

        if st.button(
            "🧾 Gerar plano de persistência ARMED",
            key="aion_global_persist_plan",
            disabled=not bool(
                flag_safe and prepare_persisted_arming_plan is not None
            ),
            width="stretch",
        ):
            try:
                planned_persistence = prepare_persisted_arming_plan(
                    access,
                    checkpoint,
                    runtime_result,
                    persist_flag_evidence,
                    ttl_seconds=persist_ttl,
                )
                if planned_persistence.get("status") == "PERSISTENCE_PLAN_READY":
                    st.session_state[_AION_GLOBAL_PERSIST_PLAN_KEY] = (
                        planned_persistence.get("plan")
                    )
                    st.session_state.pop(
                        _AION_GLOBAL_PERSIST_APPROVAL_KEY,
                        None,
                    )
                    st.success(
                        "Plano de persistência criado somente na sessão. "
                        "Nenhuma escrita foi feita."
                    )
                else:
                    st.warning(
                        "Plano de persistência bloqueado: "
                        + str(
                            planned_persistence.get("reason")
                            or planned_persistence.get("status")
                            or "UNKNOWN"
                        )
                    )
            except Exception as exc:
                st.error(
                    "Plano de persistência bloqueado: "
                    + type(exc).__name__
                    + "."
                )

        persist_plan = st.session_state.get(_AION_GLOBAL_PERSIST_PLAN_KEY)
        if isinstance(persist_plan, Mapping):
            st.caption(
                "Persistence plan: "
                + str(persist_plan.get("plan_digest") or "")[:24]
                + "… · runtime SHA "
                + str(persist_plan.get("source_runtime_sha") or "")[:12]
                + "… · expira em "
                + str(persist_plan.get("expires_at") or "UNKNOWN")
            )
            st.caption(
                "Rollback source digest: "
                + str(
                    (
                        persist_plan.get("rollback")
                        if isinstance(persist_plan.get("rollback"), Mapping)
                        else {}
                    ).get("source_runtime_checkpoint_digest")
                    or ""
                )[:24]
                + "…"
            )

            persist_phrase = st.text_input(
                'Digite exatamente "PERSISTIR WORKER GLOBAL ARMADO"',
                value="",
                key="aion_global_persist_confirmation_phrase",
            )
            persist_confirm = st.checkbox(
                "Confirmo que revisei o STAGED_ARMED, SHA do runtime, rollback "
                "e quero autorizar a persistência real do estado ARMED.",
                value=False,
                key="aion_global_persist_confirm",
            )
            if st.button(
                "✅ Criar autorização de persistência",
                key="aion_global_persist_approve",
                disabled=not bool(
                    persist_confirm and approve_persisted_arming_plan is not None
                ),
                width="stretch",
            ):
                try:
                    approved_persistence = approve_persisted_arming_plan(
                        access,
                        persist_plan,
                        confirmation=True,
                        confirmation_phrase=persist_phrase,
                    )
                    if approved_persistence.get("status") == "APPROVED_FOR_PERSISTENCE":
                        st.session_state[_AION_GLOBAL_PERSIST_APPROVAL_KEY] = (
                            approved_persistence.get("approval")
                        )
                        st.success(
                            "Autorização de persistência criada na sessão. "
                            "Ainda nenhuma escrita foi executada."
                        )
                    else:
                        st.warning(
                            "Autorização de persistência bloqueada: "
                            + str(
                                approved_persistence.get("reason")
                                or approved_persistence.get("status")
                                or "UNKNOWN"
                            )
                        )
                except Exception as exc:
                    st.error(
                        "Autorização de persistência bloqueada: "
                        + type(exc).__name__
                        + "."
                    )

        persist_approval = st.session_state.get(
            _AION_GLOBAL_PERSIST_APPROVAL_KEY
        )
        persist_approval_valid = False
        if (
            isinstance(persist_approval, Mapping)
            and validate_persisted_arming_approval is not None
        ):
            try:
                approval_check = validate_persisted_arming_approval(
                    access,
                    checkpoint,
                    runtime_result,
                    persist_approval,
                )
                persist_approval_valid = approval_check.get("state") == "APPROVED"
            except Exception:
                persist_approval_valid = False

        final_persist_confirm = st.checkbox(
            "SEGUNDA CONFIRMAÇÃO: autorizo agora a escrita real do ARMED "
            "no Checkpoint Mestre. A feature flag deve continuar desligada.",
            value=False,
            key="aion_global_persist_final_confirm",
        )
        if st.button(
            "🚨 Persistir ARMED no Checkpoint Mestre",
            key="aion_global_persist_execute",
            disabled=not bool(
                persist_approval_valid
                and final_persist_confirm
                and persist_staged_global_arming is not None
                and not conflict
            ),
            width="stretch",
        ):
            decision = guardian_decision(
                "save_checkpoint",
                access,
                approved=True,
                feature_flags=flags,
            )
            if not decision["allowed"]:
                st.error(decision["reason"])
            else:
                try:
                    persist_result = persist_staged_global_arming(
                        access,
                        checkpoint,
                        runtime_result,
                        persist_approval,
                        cfg,
                        confirmation=True,
                    )
                    if (
                        persist_result.get("status") == "CONFIRMED"
                        and persist_result.get("saved")
                        and persist_result.get("verified")
                    ):
                        saved_checkpoint = ensure_operating_checkpoint(
                            persist_result.get("checkpoint")
                        )
                        saved_checkpoint["operating"]["dirty"] = False
                        _set_working_checkpoint(saved_checkpoint, dirty=False)
                        st.session_state[_WORKING_SOURCE_KEY] = (
                            checkpoint_source_digest(saved_checkpoint)
                        )
                        for key in (
                            _AION_GLOBAL_PERSIST_FLAG_EVIDENCE_KEY,
                            _AION_GLOBAL_PERSIST_PLAN_KEY,
                            _AION_GLOBAL_PERSIST_APPROVAL_KEY,
                        ):
                            st.session_state.pop(key, None)
                        st.success(
                            "Global Worker ARMED persistido, relido e confirmado. "
                            "Feature flag permanece separada e não foi alterada."
                        )
                        st.session_state["aion_checkpoint_save_result"] = persist_result
                        st.rerun()
                    elif persist_result.get("status") == "ROLLED_BACK":
                        st.error(
                            "A persistência foi revertida automaticamente porque a "
                            "feature flag deixou de estar comprovadamente desligada."
                        )
                        _set_working_checkpoint(source_checkpoint, dirty=False)
                        st.session_state[_WORKING_SOURCE_KEY] = (
                            checkpoint_source_digest(source_checkpoint)
                        )
                        st.rerun()
                    else:
                        st.error(
                            "Persistência ARMED não foi concluída. Estado: "
                            + str(persist_result.get("status") or "UNKNOWN")
                            + " · motivo: "
                            + str(persist_result.get("reason") or "não informado")
                            + "."
                        )
                except Exception as exc:
                    st.error(
                        "Persistência ARMED bloqueada em modo seguro: "
                        + type(exc).__name__
                        + "."
                    )

    persisted_runtime_checkpoint = (
        runtime_result.get("checkpoint")
        if isinstance(runtime_result.get("checkpoint"), Mapping)
        else {}
    )
    persisted_global_worker = (
        persisted_runtime_checkpoint.get("aion_global_worker_v1")
        if isinstance(persisted_runtime_checkpoint, Mapping)
        and isinstance(
            persisted_runtime_checkpoint.get("aion_global_worker_v1"),
            Mapping,
        )
        else {}
    )
    persisted_global_armed = bool(
        str(persisted_global_worker.get("state") or "").upper() == "ARMED"
        and persisted_global_worker.get("kill_switch") is False
    )

    if persisted_global_armed and not persisted_arm_required:
        st.markdown("##### ⚡ Global Worker Activation Ceremony")
        st.warning(
            "Ativar a feature flag permite que o pulso GitHub Actions já existente "
            "acorde o Worker Global. Isso NÃO prova heartbeat, receipt ou autonomia "
            "operacional. O primeiro resultado válido será somente "
            "ACTIVATED_PENDING_LIVE_EVIDENCE."
        )

        if st.button(
            "🔎 Verificar readiness atual para ativação",
            key="aion_global_activation_check_readiness",
            disabled=collect_activation_readiness_evidence is None,
            width="stretch",
        ):
            try:
                live_readiness = collect_activation_readiness_evidence(
                    cfg,
                    runtime_result,
                )
                st.session_state[_AION_GLOBAL_ACTIVATION_READINESS_KEY] = (
                    live_readiness
                )
                st.session_state.pop(_AION_GLOBAL_ACTIVATION_PLAN_KEY, None)
                st.session_state.pop(_AION_GLOBAL_ACTIVATION_APPROVAL_KEY, None)

                gate_flag_evidence = (
                    live_readiness.get("flag_evidence")
                    if isinstance(
                        live_readiness.get("flag_evidence"),
                        Mapping,
                    )
                    else {}
                )
                if (
                    assess_post_incident_reactivation_gate is not None
                    and reconcile_global_worker_incident_center is not None
                    and verify_global_worker_live_activation is not None
                    and supervise_global_worker is not None
                ):
                    try:
                        gate_live_report = verify_global_worker_live_activation(
                            access,
                            runtime_result,
                            gate_flag_evidence,
                            activation_result=None,
                        )
                        gate_supervision = supervise_global_worker(
                            gate_live_report,
                            gate_flag_evidence,
                        )
                        gate_incident_snapshot = (
                            reconcile_global_worker_incident_center(
                                {},
                                gate_supervision,
                                runtime_result,
                            )
                        )
                        st.session_state[
                            _AION_GLOBAL_REACTIVATION_GATE_KEY
                        ] = assess_post_incident_reactivation_gate(
                            runtime_result,
                            gate_incident_snapshot,
                            live_readiness,
                            gate_flag_evidence,
                        )
                    except Exception as gate_exc:
                        st.session_state[
                            _AION_GLOBAL_REACTIVATION_GATE_KEY
                        ] = {
                            "status": "REACTIVATION_GATE_BLOCKED",
                            "gate_required": True,
                            "gate_ready": False,
                            "activation_plan_allowed": False,
                            "reason": type(gate_exc).__name__,
                            "reactivation_authorized": False,
                        }
                else:
                    st.session_state[
                        _AION_GLOBAL_REACTIVATION_GATE_KEY
                    ] = {
                        "status": "REACTIVATION_GATE_BLOCKED",
                        "gate_required": True,
                        "gate_ready": False,
                        "activation_plan_allowed": False,
                        "reason": "POST_INCIDENT_GATE_UNAVAILABLE",
                        "reactivation_authorized": False,
                    }

                if (
                    live_readiness.get("status") == "PASS"
                    and live_readiness.get("activation_stage")
                    == "READY_FOR_FLAG_ENABLE"
                ):
                    st.success(
                        "Readiness atual: READY_FOR_FLAG_ENABLE. "
                        "Nenhuma variável foi alterada."
                    )
                else:
                    st.error(
                        "Ativação continua bloqueada: "
                        + str(
                            live_readiness.get("activation_stage")
                            or live_readiness.get("status")
                            or "UNKNOWN"
                        )
                        + "."
                    )
            except Exception as exc:
                st.error(
                    "Readiness de ativação falhou em modo seguro: "
                    + type(exc).__name__
                    + "."
                )

        activation_readiness = st.session_state.get(
            _AION_GLOBAL_ACTIVATION_READINESS_KEY
        )
        reactivation_gate = st.session_state.get(
            _AION_GLOBAL_REACTIVATION_GATE_KEY
        )
        reactivation_gate_allows_plan = bool(
            isinstance(reactivation_gate, Mapping)
            and reactivation_gate.get("activation_plan_allowed") is True
            and reactivation_gate.get("gate_ready") is True
        )
        activation_ready = bool(
            isinstance(activation_readiness, Mapping)
            and activation_readiness.get("status") == "PASS"
            and activation_readiness.get("activation_stage")
            == "READY_FOR_FLAG_ENABLE"
            and not list(activation_readiness.get("blockers") or [])
            and reactivation_gate_allows_plan
        )
        activation_flag_evidence = (
            activation_readiness.get("flag_evidence")
            if isinstance(activation_readiness, Mapping)
            and isinstance(activation_readiness.get("flag_evidence"), Mapping)
            else {}
        )
        if isinstance(activation_readiness, Mapping):
            ar1, ar2, ar3, ar4 = st.columns(4)
            ar1.metric(
                "Activation stage",
                str(
                    activation_readiness.get("activation_stage")
                    or "UNKNOWN"
                ),
            )
            ar2.metric(
                "Feature flag",
                str(
                    (
                        activation_readiness.get("feature_flag")
                        if isinstance(
                            activation_readiness.get("feature_flag"),
                            Mapping,
                        )
                        else {}
                    ).get("state")
                    or "UNKNOWN"
                ),
            )
            ar3.metric(
                "Pulse",
                str(
                    (
                        activation_readiness.get("pulse")
                        if isinstance(activation_readiness.get("pulse"), Mapping)
                        else {}
                    ).get("state")
                    or "UNKNOWN"
                ),
            )
            ar4.metric(
                "Shadow",
                str(
                    (
                        activation_readiness.get("shadow_protocol")
                        if isinstance(
                            activation_readiness.get("shadow_protocol"),
                            Mapping,
                        )
                        else {}
                    ).get("state")
                    or "UNKNOWN"
                ),
            )

        if isinstance(reactivation_gate, Mapping):
            rg1, rg2, rg3 = st.columns(3)
            rg1.metric(
                "Post-incident gate",
                str(reactivation_gate.get("status") or "UNKNOWN"),
            )
            rg2.metric(
                "Histórico durável",
                str(reactivation_gate.get("durable_closure_records") or 0),
            )
            rg3.metric(
                "Plano permitido",
                "SIM"
                if reactivation_gate.get("activation_plan_allowed")
                else "NÃO",
            )
            if reactivation_gate.get("gate_required"):
                if reactivation_gate.get("gate_ready"):
                    st.success(
                        "Gate pós-incidente verde para geração do plano. "
                        "Isso NÃO autoriza reativação; a cerimônia de ativação "
                        "continua separada."
                    )
                else:
                    st.error(
                        "Reativação bloqueada pelo gate pós-incidente: "
                        + str(
                            reactivation_gate.get("reason")
                            or "evidência não reconciliada"
                        )
                        + "."
                    )
            else:
                st.caption(
                    "Nenhum histórico durável de incidente exige gate pós-incidente "
                    "neste runtime."
                )

        activation_ttl = int(st.number_input(
            "TTL da autorização de ativação (segundos)",
            min_value=300,
            max_value=1800,
            value=600,
            step=300,
            key="aion_global_activation_ttl",
        ))
        if st.button(
            "🧾 Gerar plano de ativação",
            key="aion_global_activation_plan",
            disabled=not bool(
                activation_ready
                and prepare_global_worker_activation_plan is not None
            ),
            width="stretch",
        ):
            try:
                activation_plan_result = prepare_global_worker_activation_plan(
                    access,
                    runtime_result,
                    activation_readiness,
                    activation_flag_evidence,
                    reactivation_gate=reactivation_gate,
                    ttl_seconds=activation_ttl,
                )
                if (
                    activation_plan_result.get("status")
                    == "ACTIVATION_PLAN_READY"
                ):
                    st.session_state[_AION_GLOBAL_ACTIVATION_PLAN_KEY] = (
                        activation_plan_result.get("plan")
                    )
                    st.session_state.pop(
                        _AION_GLOBAL_ACTIVATION_APPROVAL_KEY,
                        None,
                    )
                    st.success(
                        "Plano de ativação criado somente na sessão. "
                        "A feature flag continua inalterada."
                    )
                else:
                    st.warning(
                        "Plano de ativação bloqueado: "
                        + str(
                            activation_plan_result.get("reason")
                            or activation_plan_result.get("status")
                            or "UNKNOWN"
                        )
                    )
            except Exception as exc:
                st.error(
                    "Plano de ativação bloqueado: "
                    + type(exc).__name__
                    + "."
                )

        activation_plan = st.session_state.get(
            _AION_GLOBAL_ACTIVATION_PLAN_KEY
        )
        if isinstance(activation_plan, Mapping):
            st.caption(
                "Activation plan: "
                + str(activation_plan.get("plan_digest") or "")[:24]
                + "… · runtime SHA "
                + str(activation_plan.get("runtime_sha") or "")[:12]
                + "… · expira em "
                + str(activation_plan.get("expires_at") or "UNKNOWN")
            )
            st.caption(
                "A ativação não executa tick diretamente. "
                "Após a flag, heartbeat + receipt reais ainda serão exigidos."
            )
            activation_phrase = st.text_input(
                'Digite exatamente "ATIVAR WORKER GLOBAL"',
                value="",
                key="aion_global_activation_confirmation_phrase",
            )
            activation_confirm = st.checkbox(
                "Confirmo que revisei runtime ARMED, readiness, TTL e budgets "
                "e quero autorizar somente a habilitação da feature flag.",
                value=False,
                key="aion_global_activation_confirm",
            )
            if st.button(
                "✅ Criar autorização de ativação",
                key="aion_global_activation_approve",
                disabled=not bool(
                    activation_confirm
                    and approve_global_worker_activation_plan is not None
                ),
                width="stretch",
            ):
                try:
                    approved_activation = approve_global_worker_activation_plan(
                        access,
                        activation_plan,
                        confirmation=True,
                        confirmation_phrase=activation_phrase,
                    )
                    if (
                        approved_activation.get("status")
                        == "APPROVED_FOR_ACTIVATION"
                    ):
                        st.session_state[
                            _AION_GLOBAL_ACTIVATION_APPROVAL_KEY
                        ] = approved_activation.get("approval")
                        st.success(
                            "Autorização temporária criada. "
                            "A feature flag ainda NÃO foi alterada."
                        )
                    else:
                        st.warning(
                            "Autorização de ativação bloqueada: "
                            + str(
                                approved_activation.get("reason")
                                or approved_activation.get("status")
                                or "UNKNOWN"
                            )
                        )
                except Exception as exc:
                    st.error(
                        "Autorização de ativação bloqueada: "
                        + type(exc).__name__
                        + "."
                    )

        activation_approval = st.session_state.get(
            _AION_GLOBAL_ACTIVATION_APPROVAL_KEY
        )
        activation_approval_valid = False
        if (
            isinstance(activation_approval, Mapping)
            and validate_global_worker_activation_approval is not None
        ):
            try:
                activation_check = validate_global_worker_activation_approval(
                    access,
                    runtime_result,
                    activation_approval,
                )
                activation_approval_valid = (
                    activation_check.get("state") == "APPROVED"
                )
            except Exception:
                activation_approval_valid = False

        final_activation_confirm = st.checkbox(
            "CONFIRMAÇÃO FINAL: autorizo habilitar agora a feature flag do "
            "Worker Global. Isso não autoriza trading, pagamentos, publicação, "
            "deploy ou merge.",
            value=False,
            key="aion_global_activation_final_confirm",
        )
        if st.button(
            "⚡ Habilitar Worker Global (feature flag)",
            key="aion_global_activation_execute",
            disabled=not bool(
                activation_approval_valid
                and final_activation_confirm
                and activate_global_worker_feature_flag is not None
                and not conflict
            ),
            width="stretch",
        ):
            fresh_reactivation_gate = reactivation_gate
            final_gate_ready = True
            if bool(
                (activation_approval or {}).get(
                    "post_incident_gate_required"
                )
            ):
                final_gate_ready = False
                try:
                    final_gate_runtime = load_runtime_checkpoint(cfg)
                    final_gate_flag = read_repository_feature_flag(cfg)
                    final_gate_live = verify_global_worker_live_activation(
                        access,
                        final_gate_runtime,
                        final_gate_flag,
                        activation_result=None,
                    )
                    final_gate_supervision = supervise_global_worker(
                        final_gate_live,
                        final_gate_flag,
                    )
                    final_gate_snapshot = (
                        reconcile_global_worker_incident_center(
                            {},
                            final_gate_supervision,
                            final_gate_runtime,
                        )
                    )
                    fresh_reactivation_gate = (
                        assess_post_incident_reactivation_gate(
                            final_gate_runtime,
                            final_gate_snapshot,
                            activation_readiness,
                            final_gate_flag,
                        )
                    )
                    final_gate_ready = bool(
                        fresh_reactivation_gate.get("status")
                        == "REACTIVATION_GATE_READY"
                        and fresh_reactivation_gate.get("gate_ready") is True
                        and fresh_reactivation_gate.get(
                            "activation_plan_allowed"
                        )
                        is True
                    )
                except Exception as gate_exc:
                    fresh_reactivation_gate = {
                        "status": "REACTIVATION_GATE_BLOCKED",
                        "reason": type(gate_exc).__name__,
                        "gate_ready": False,
                        "activation_plan_allowed": False,
                    }
                    final_gate_ready = False

            if not final_gate_ready:
                st.error(
                    "Ativação bloqueada: o gate pós-incidente fresco não está "
                    "verde. Nenhuma feature flag foi alterada."
                )
            else:
                decision = guardian_decision(
                "write_runtime",
                access,
                approved=True,
                feature_flags=flags,
                )
                if not decision["allowed"]:
                    st.error(decision["reason"])
                else:
                    try:
                        activation_result = activate_global_worker_feature_flag(
                            access,
                            runtime_result,
                            activation_approval,
                            cfg,
                            confirmation=True,
                            reactivation_gate=fresh_reactivation_gate,
                        )
                        st.session_state[
                            _AION_GLOBAL_ACTIVATION_RESULT_KEY
                        ] = activation_result
                        status = str(
                            activation_result.get("status") or "UNKNOWN"
                        )
                        if status == "ACTIVATED_PENDING_LIVE_EVIDENCE":
                            st.success(
                                "Feature flag habilitada e relida. "
                                "Estado: ACTIVATED_PENDING_LIVE_EVIDENCE. "
                                "Ainda não há prova de heartbeat/receipt do Worker."
                            )
                        elif status == "ACTIVATION_ROLLED_BACK":
                            st.error(
                                "A ativação foi revertida automaticamente por "
                                "divergência de runtime ou verificação da flag."
                            )
                        else:
                            st.error(
                                "Ativação não confirmada. Estado: "
                                + status
                                + " · motivo: "
                                + str(
                                    activation_result.get("reason")
                                    or "não informado"
                                )
                                + "."
                            )
                    except Exception as exc:
                        st.error(
                            "Ativação bloqueada em modo seguro: "
                            + type(exc).__name__
                            + "."
                        )

        last_activation = st.session_state.get(
            _AION_GLOBAL_ACTIVATION_RESULT_KEY
        )
        if isinstance(last_activation, Mapping):
            st.caption(
                "Última tentativa de ativação: "
                + str(last_activation.get("status") or "UNKNOWN")
                + " · heartbeat confirmado: "
                + (
                    "SIM"
                    if last_activation.get("live_heartbeat_confirmed")
                    else "NÃO"
                )
                + " · trading real: NÃO."
            )

        st.markdown("##### 📡 Verificação operacional ao vivo")
        st.caption(
            "ENABLED não significa LIVE. Esta verificação é somente leitura e exige "
            "heartbeat/tick compartilhado posterior à ativação. Receipt GLOBAL_WORKER "
            "é mostrado quando houve trabalho devido; um tick idle válido também prova "
            "que o runner acordou."
        )
        if st.button(
            "📡 Verificar Worker Global ao vivo",
            key="aion_global_live_verify",
            disabled=not bool(
                verify_global_worker_live_activation is not None
                and read_repository_feature_flag is not None
            ),
            width="stretch",
        ):
            try:
                fresh_flag = read_repository_feature_flag(cfg)
                fresh_runtime = load_runtime_checkpoint(cfg)
                live_report = verify_global_worker_live_activation(
                    access,
                    fresh_runtime,
                    fresh_flag,
                    activation_result=(
                        last_activation
                        if isinstance(last_activation, Mapping)
                        else None
                    ),
                )
                st.session_state[_AION_GLOBAL_LIVE_VERIFICATION_KEY] = (
                    live_report
                )
                if supervise_global_worker is not None:
                    supervision_report = supervise_global_worker(
                        live_report,
                        fresh_flag,
                    )
                    st.session_state[_AION_GLOBAL_SUPERVISION_KEY] = (
                        supervision_report
                    )
                    if append_supervision_history is not None:
                        existing_supervision_history = st.session_state.get(
                            _AION_GLOBAL_SUPERVISION_HISTORY_KEY,
                            [],
                        )
                        st.session_state[
                            _AION_GLOBAL_SUPERVISION_HISTORY_KEY
                        ] = append_supervision_history(
                            existing_supervision_history,
                            supervision_report,
                            max_entries=50,
                        )
            except Exception as exc:
                st.session_state[_AION_GLOBAL_LIVE_VERIFICATION_KEY] = {
                    "status": "BLOCKED",
                    "reason": type(exc).__name__,
                    "live_confirmed": False,
                }
                st.session_state.pop(_AION_GLOBAL_SUPERVISION_KEY, None)

        live_report = st.session_state.get(
            _AION_GLOBAL_LIVE_VERIFICATION_KEY
        )
        if isinstance(live_report, Mapping):
            lv1, lv2, lv3, lv4 = st.columns(4)
            lv1.metric(
                "Live status",
                str(live_report.get("status") or "UNKNOWN"),
            )
            lv2.metric(
                "Heartbeat",
                "SIM" if live_report.get("heartbeat_confirmed") else "NÃO",
            )
            lv3.metric(
                "Tick",
                "SIM" if live_report.get("tick_confirmed") else "NÃO",
            )
            lv4.metric(
                "Receipt work",
                "SIM" if live_report.get("work_receipt_confirmed") else "NÃO",
            )
            st.caption(
                "Runtime: "
                + str(live_report.get("last_runtime_id") or "não confirmado")
                + " · último heartbeat: "
                + str(live_report.get("last_heartbeat_at") or "não confirmado")
                + " · último tick: "
                + str(live_report.get("last_tick_at") or "não confirmado")
                + " · efeitos externos/trading: NÃO."
            )
            if live_report.get("live_confirmed"):
                st.success(
                    "Worker Global LIVE confirmado por evidência compartilhada."
                )
            elif str(live_report.get("status") or "") == "LIVE_EVIDENCE_TIMEOUT":
                st.error(
                    "Timeout sem heartbeat compartilhado após ativação. "
                    "Não considerar o Worker operacional; use o safety stop."
                )
            elif str(live_report.get("status") or "").startswith("BLOCKED"):
                st.error(
                    "Verificação live bloqueada: "
                    + str(live_report.get("reason") or "evidência inválida")
                    + "."
                )
            else:
                st.info(
                    "Ainda aguardando evidência live compartilhada. "
                    "A feature flag, por si só, não confirma operação."
                )

        supervision_report = st.session_state.get(
            _AION_GLOBAL_SUPERVISION_KEY
        )
        if isinstance(supervision_report, Mapping):
            st.markdown("##### 🛡️ Supervisão operacional")
            sp1, sp2, sp3 = st.columns(3)
            sp1.metric(
                "Postura",
                str(supervision_report.get("posture") or "UNKNOWN"),
            )
            sp2.metric(
                "Severidade",
                str(supervision_report.get("severity") or "UNKNOWN"),
            )
            sp3.metric(
                "Safety-stop recomendado",
                "SIM"
                if supervision_report.get("safety_stop_recommended")
                else "NÃO",
            )
            if supervision_report.get("incident_open"):
                st.warning(
                    "Incidente operacional aberto por evidência do Worker Global. "
                    "A supervisão NÃO executa contenção automática."
                )
            else:
                st.caption(
                    "Nenhum incidente operacional aberto neste snapshot."
                )
            recovery_steps = list(
                supervision_report.get("recovery_steps") or []
            )
            if recovery_steps:
                with st.expander("Checklist de recuperação do Worker Global"):
                    for step in recovery_steps:
                        st.markdown("- " + str(step))
            st.caption(
                "Supervisão: somente leitura · contenção automática: NÃO · "
                "alteração automática da feature flag: NÃO · trading real: NÃO."
            )
            supervision_history = st.session_state.get(
                _AION_GLOBAL_SUPERVISION_HISTORY_KEY,
                [],
            )
            if supervision_history:
                with st.expander("Histórico de supervisão do Worker Global"):
                    history_summary = (
                        supervision_history_summary(supervision_history)
                        if supervision_history_summary is not None
                        else {}
                    )
                    st.caption(
                        "Observações na sessão: "
                        + str(history_summary.get("observations") or len(supervision_history))
                        + " · incidentes: "
                        + str(history_summary.get("incidents") or 0)
                        + " · críticos: "
                        + str(history_summary.get("critical_incidents") or 0)
                        + " · persistência externa: NÃO."
                    )
                    for event in list(supervision_history)[-5:][::-1]:
                        if not isinstance(event, Mapping):
                            continue
                        st.markdown(
                            "- **"
                            + str(event.get("severity") or "UNKNOWN")
                            + "** · "
                            + str(event.get("posture") or "UNKNOWN")
                            + " · "
                            + str(event.get("live_status") or "UNKNOWN")
                            + " · "
                            + str(event.get("observed_at") or "sem horário")
                        )

            with st.expander("🧪 Drill de recuperação do Worker Global"):
                st.caption(
                    "SIMULAÇÃO SOMENTE. O drill ensaia resposta a incidente, mas "
                    "não desativa flag, não altera Checkpoint, não executa tick e "
                    "não confirma recuperação real."
                )
                drill_plan = (
                    prepare_global_worker_recovery_drill(supervision_report)
                    if prepare_global_worker_recovery_drill is not None
                    else {}
                )
                drill_ready = str(drill_plan.get("status") or "") == "DRILL_READY"
                if drill_ready:
                    st.caption(
                        "Cenário: "
                        + str(drill_plan.get("scenario") or "UNKNOWN")
                        + " · severidade: "
                        + str(drill_plan.get("severity") or "UNKNOWN")
                        + " · safety-stop recomendado: "
                        + (
                            "SIM"
                            if drill_plan.get("safety_stop_recommended")
                            else "NÃO"
                        )
                    )
                    drill_phrase = st.text_input(
                        'Digite exatamente "SIMULAR RECUPERACAO WORKER GLOBAL"',
                        value="",
                        key="aion_global_recovery_drill_phrase",
                    )
                    drill_confirm = st.checkbox(
                        "Confirmo que este exercício é apenas uma simulação.",
                        value=False,
                        key="aion_global_recovery_drill_confirm",
                    )
                    if st.button(
                        "🧪 Executar drill simulado de recuperação",
                        key="aion_global_recovery_drill_execute",
                        disabled=not bool(
                            drill_confirm
                            and simulate_global_worker_recovery_drill is not None
                        ),
                        width="stretch",
                    ):
                        st.session_state[_AION_GLOBAL_RECOVERY_DRILL_KEY] = (
                            simulate_global_worker_recovery_drill(
                                supervision_report,
                                confirmation=drill_confirm,
                                confirmation_phrase=drill_phrase,
                            )
                        )
                else:
                    st.caption(
                        "Nenhum incidente suportado está aberto neste snapshot; "
                        "o drill não é necessário."
                    )

                drill_result = st.session_state.get(
                    _AION_GLOBAL_RECOVERY_DRILL_KEY
                )
                if isinstance(drill_result, Mapping):
                    drill_view = (
                        recovery_drill_summary(drill_result)
                        if recovery_drill_summary is not None
                        else drill_result
                    )
                    st.caption(
                        "Drill: "
                        + str(drill_view.get("status") or "UNKNOWN")
                        + " · recuperação real: NÃO"
                        + " · reativação autorizada: NÃO"
                        + " · flag alterada: NÃO"
                        + " · runtime alterado: NÃO."
                    )
                    if drill_result.get("drill_completed"):
                        st.success(
                            "Drill concluído em memória. Nenhuma ação real foi executada."
                        )
                        for stage in list(drill_result.get("stages") or []):
                            if not isinstance(stage, Mapping):
                                continue
                            st.markdown(
                                "- **"
                                + str(stage.get("stage") or "UNKNOWN")
                                + "** → "
                                + str(stage.get("expected") or "")
                                + " · execução real: NÃO"
                            )
                    elif str(drill_result.get("status") or "") == "CONFIRMATION_REQUIRED":
                        st.warning(
                            "A frase exata de confirmação da simulação é obrigatória."
                        )

            with st.expander("🧾 Evidência de recuperação / fechamento"):
                st.caption(
                    "Esta etapa nunca encerra o incidente automaticamente. Ela exige "
                    "remediação confirmada + evidência atual fresca e, no máximo, "
                    "marca o caso como pronto para revisão humana."
                )
                rem_root = st.checkbox(
                    "Causa raiz identificada.",
                    value=False,
                    key="aion_global_remediation_root_cause",
                )
                rem_fix = st.checkbox(
                    "Ação corretiva verificada.",
                    value=False,
                    key="aion_global_remediation_fix_verified",
                )
                rem_regression = st.checkbox(
                    "Teste de regressão passou.",
                    value=False,
                    key="aion_global_remediation_regression",
                )
                rem_preserved = st.checkbox(
                    "Evidência original do incidente foi preservada.",
                    value=False,
                    key="aion_global_remediation_evidence_preserved",
                )
                rem_reviewer = st.checkbox(
                    "Revisor humano confirma a evidência de remediação.",
                    value=False,
                    key="aion_global_remediation_reviewer",
                )
                rem_phrase = st.text_input(
                    'Digite exatamente "CONFIRMAR EVIDENCIA DE REMEDIACAO WORKER GLOBAL"',
                    value="",
                    key="aion_global_remediation_phrase",
                )
                if st.button(
                    "🧾 Confirmar evidência de remediação",
                    key="aion_global_remediation_confirm",
                    disabled=prepare_remediation_evidence is None,
                    width="stretch",
                ):
                    st.session_state[_AION_GLOBAL_REMEDIATION_EVIDENCE_KEY] = (
                        prepare_remediation_evidence(
                            supervision_report,
                            root_cause_identified=rem_root,
                            corrective_action_verified=rem_fix,
                            regression_check_passed=rem_regression,
                            evidence_preserved=rem_preserved,
                            reviewer_confirmed=rem_reviewer,
                            confirmation_phrase=rem_phrase,
                        )
                    )

                remediation_evidence = st.session_state.get(
                    _AION_GLOBAL_REMEDIATION_EVIDENCE_KEY
                )
                if isinstance(remediation_evidence, Mapping):
                    st.caption(
                        "Remediação: "
                        + str(remediation_evidence.get("status") or "UNKNOWN")
                        + " · incidente encerrado automaticamente: NÃO"
                        + " · reativação autorizada: NÃO"
                        + " · persistência externa: NÃO."
                    )

                    if st.button(
                        "🔎 Avaliar prontidão para fechamento",
                        key="aion_global_closure_assess",
                        disabled=not bool(
                            assess_incident_closure_readiness is not None
                            and verify_global_worker_live_activation is not None
                            and read_repository_feature_flag is not None
                        ),
                        width="stretch",
                    ):
                        try:
                            closure_flag = read_repository_feature_flag(cfg)
                            closure_runtime = load_runtime_checkpoint(cfg)
                            closure_live = verify_global_worker_live_activation(
                                access,
                                closure_runtime,
                                closure_flag,
                                activation_result=(
                                    last_activation
                                    if isinstance(last_activation, Mapping)
                                    else None
                                ),
                            )
                            st.session_state[_AION_GLOBAL_CLOSURE_ASSESSMENT_KEY] = (
                                assess_incident_closure_readiness(
                                    supervision_report,
                                    closure_live,
                                    closure_flag,
                                    remediation_evidence,
                                )
                            )
                        except Exception as exc:
                            st.session_state[
                                _AION_GLOBAL_CLOSURE_ASSESSMENT_KEY
                            ] = {
                                "status": "CLOSURE_BLOCKED",
                                "reason": type(exc).__name__,
                                "closure_review_ready": False,
                                "incident_closed": False,
                                "automatic_closure": False,
                            }

                closure_assessment = st.session_state.get(
                    _AION_GLOBAL_CLOSURE_ASSESSMENT_KEY
                )
                if isinstance(closure_assessment, Mapping):
                    closure_record = (
                        closure_review_record(closure_assessment)
                        if closure_review_record is not None
                        else {}
                    )
                    if closure_assessment.get("closure_review_ready"):
                        st.success(
                            "Evidência suficiente: caso pronto para revisão humana "
                            "de fechamento. O incidente ainda NÃO foi encerrado."
                        )
                    else:
                        st.warning(
                            "Fechamento ainda bloqueado: "
                            + str(
                                closure_assessment.get("reason")
                                or "evidência insuficiente"
                            )
                            + "."
                        )
                    st.caption(
                        "Status: "
                        + str(closure_assessment.get("status") or "UNKNOWN")
                        + " · pronto para revisão humana: "
                        + (
                            "SIM"
                            if closure_assessment.get("closure_review_ready")
                            else "NÃO"
                        )
                        + " · incidente encerrado automaticamente: NÃO"
                        + " · reativação autorizada: NÃO"
                        + " · trading real: NÃO."
                    )
                    blockers = list(closure_assessment.get("blockers") or [])
                    if blockers:
                        st.caption(
                            "Blockers: " + ", ".join(str(x) for x in blockers)
                        )
                    if closure_record.get("closure_package_digest"):
                        st.caption(
                            "Closure package digest: "
                            + str(closure_record.get("closure_package_digest"))
                        )

                    with st.expander(
                        "✅ Cerimônia humana de fechamento do incidente"
                    ):
                        ceremony_plan = (
                            prepare_human_incident_closure(closure_assessment)
                            if prepare_human_incident_closure is not None
                            else {}
                        )
                        ceremony_ready = (
                            str(ceremony_plan.get("status") or "")
                            == "CEREMONY_READY"
                        )
                        st.caption(
                            "A cerimônia registra somente a decisão humana nesta "
                            "sessão. fechamento autoritativo persistido: NÃO · "
                            "reativação autorizada: NÃO."
                        )
                        if ceremony_ready:
                            closure_evidence_ack = st.checkbox(
                                "Confirmo que revisei o pacote de evidências "
                                "vinculado a este incidente.",
                                value=False,
                                key="aion_global_human_closure_evidence_ack",
                            )
                            closure_human_confirm = st.checkbox(
                                "Confirmo a decisão humana de encerrar este "
                                "incidente com base nas evidências apresentadas.",
                                value=False,
                                key="aion_global_human_closure_confirm",
                            )
                            closure_reactivation_ack = st.checkbox(
                                "Confirmo que qualquer reativação do Worker Global "
                                "exige uma cerimônia separada e futura.",
                                value=False,
                                key="aion_global_human_closure_reactivation_ack",
                            )
                            closure_note = st.text_area(
                                "Nota do operador (opcional)",
                                value="",
                                key="aion_global_human_closure_note",
                                height=80,
                            )
                            closure_phrase = st.text_input(
                                'Digite exatamente "ENCERRAR INCIDENTE WORKER GLOBAL"',
                                value="",
                                key="aion_global_human_closure_phrase",
                            )
                            if st.button(
                                "✅ Registrar decisão humana de fechamento",
                                key="aion_global_human_closure_execute",
                                disabled=record_human_incident_closure is None,
                                width="stretch",
                            ):
                                st.session_state[
                                    _AION_GLOBAL_HUMAN_CLOSURE_RECORD_KEY
                                ] = record_human_incident_closure(
                                    closure_assessment,
                                    human_confirmation=closure_human_confirm,
                                    evidence_acknowledged=closure_evidence_ack,
                                    reactivation_separation_acknowledged=(
                                        closure_reactivation_ack
                                    ),
                                    confirmation_phrase=closure_phrase,
                                    operator_note=closure_note,
                                )
                        else:
                            st.caption(
                                "Cerimônia bloqueada até existir "
                                "CLOSURE_REVIEW_READY com evidência vinculada."
                            )

                        human_closure_record = st.session_state.get(
                            _AION_GLOBAL_HUMAN_CLOSURE_RECORD_KEY
                        )
                        if isinstance(human_closure_record, Mapping):
                            human_closure_view = (
                                human_closure_summary(human_closure_record)
                                if human_closure_summary is not None
                                else human_closure_record
                            )
                            if human_closure_record.get(
                                "human_closure_decision_recorded"
                            ):
                                st.success(
                                    "decisão humana registrada: SIM. "
                                    "O registro é session-only."
                                )
                            elif str(
                                human_closure_record.get("status") or ""
                            ) == "CONFIRMATION_REQUIRED":
                                st.warning(
                                    "Cerimônia incompleta: "
                                    + str(
                                        human_closure_record.get("reason")
                                        or "confirmações obrigatórias ausentes"
                                    )
                                    + "."
                                )
                            st.caption(
                                "Status: "
                                + str(
                                    human_closure_view.get("status")
                                    or "UNKNOWN"
                                )
                                + " · fechamento autoritativo persistido: NÃO"
                                + " · reativação autorizada: NÃO"
                                + " · flag alterada: NÃO"
                                + " · runtime alterado: NÃO"
                                + " · trading real: NÃO."
                            )
                            if human_closure_view.get("closure_record_id"):
                                st.caption(
                                    "Closure record: "
                                    + str(
                                        human_closure_view.get(
                                            "closure_record_id"
                                        )
                                    )
                                )

                    with st.expander("💾 Persistência durável do fechamento"):
                        durable_human_record = st.session_state.get(
                            _AION_GLOBAL_HUMAN_CLOSURE_RECORD_KEY
                        )
                        durable_human_ready = bool(
                            isinstance(durable_human_record, Mapping)
                            and durable_human_record.get(
                                "human_closure_decision_recorded"
                            )
                            is True
                        )
                        st.caption(
                            "Esta etapa persiste somente o registro humano de "
                            "fechamento no Checkpoint compartilhado. Ela NÃO altera "
                            "a feature flag, NÃO muda o estado do Worker e NÃO "
                            "autoriza reativação."
                        )

                        if st.button(
                            "🔎 Ler feature flag para persistência do fechamento",
                            key="aion_global_durable_closure_check_flag",
                            disabled=read_repository_feature_flag is None,
                            width="stretch",
                        ):
                            try:
                                durable_flag_evidence = (
                                    read_repository_feature_flag(cfg)
                                )
                                st.session_state[
                                    _AION_GLOBAL_DURABLE_CLOSURE_FLAG_EVIDENCE_KEY
                                ] = durable_flag_evidence
                                if (
                                    durable_flag_evidence.get("status")
                                    == "CONFIRMED"
                                    and str(
                                        durable_flag_evidence.get("state")
                                        or ""
                                    )
                                    in {"UNSET", "DISABLED", "ENABLED"}
                                ):
                                    st.success(
                                        "Feature flag lida como "
                                        + str(
                                            durable_flag_evidence.get(
                                                "state"
                                            )
                                            or "UNKNOWN"
                                        )
                                        + ". Nenhuma variável foi alterada."
                                    )
                                else:
                                    st.error(
                                        "Persistência bloqueada: estado "
                                        "autoritativo da feature flag não foi "
                                        "confirmado."
                                    )
                            except Exception as exc:
                                st.error(
                                    "Leitura da feature flag falhou em modo "
                                    "seguro: "
                                    + type(exc).__name__
                                    + "."
                                )

                        durable_flag_evidence = st.session_state.get(
                            _AION_GLOBAL_DURABLE_CLOSURE_FLAG_EVIDENCE_KEY
                        )
                        durable_flag_ready = bool(
                            isinstance(durable_flag_evidence, Mapping)
                            and durable_flag_evidence.get("status")
                            == "CONFIRMED"
                            and str(
                                durable_flag_evidence.get("state") or ""
                            )
                            in {"UNSET", "DISABLED", "ENABLED"}
                        )
                        if isinstance(durable_flag_evidence, Mapping):
                            dc1, dc2 = st.columns(2)
                            dc1.metric(
                                "Feature flag",
                                str(
                                    durable_flag_evidence.get("state")
                                    or "UNKNOWN"
                                ),
                            )
                            dc2.metric(
                                "Estado confirmado",
                                "SIM" if durable_flag_ready else "NÃO",
                            )

                        durable_ttl = int(
                            st.number_input(
                                "TTL da autorização de persistência do "
                                "fechamento (segundos)",
                                min_value=300,
                                max_value=1800,
                                value=600,
                                step=300,
                                key="aion_global_durable_closure_ttl",
                            )
                        )

                        if st.button(
                            "🧾 Gerar plano de persistência do fechamento",
                            key="aion_global_durable_closure_plan",
                            disabled=not bool(
                                durable_human_ready
                                and durable_flag_ready
                                and prepare_durable_closure_plan is not None
                            ),
                            width="stretch",
                        ):
                            try:
                                durable_plan_result = (
                                    prepare_durable_closure_plan(
                                        access,
                                        durable_human_record,
                                        runtime_result,
                                        durable_flag_evidence,
                                        ttl_seconds=durable_ttl,
                                    )
                                )
                                if (
                                    durable_plan_result.get("status")
                                    == "DURABLE_CLOSURE_PLAN_READY"
                                ):
                                    st.session_state[
                                        _AION_GLOBAL_DURABLE_CLOSURE_PLAN_KEY
                                    ] = durable_plan_result.get("plan")
                                    st.session_state.pop(
                                        _AION_GLOBAL_DURABLE_CLOSURE_APPROVAL_KEY,
                                        None,
                                    )
                                    st.success(
                                        "Plano criado somente na sessão. "
                                        "Nenhuma escrita foi executada."
                                    )
                                elif (
                                    durable_plan_result.get("status")
                                    == "ALREADY_PERSISTED"
                                ):
                                    st.info(
                                        "Este registro humano já está persistido "
                                        "com o mesmo digest."
                                    )
                                else:
                                    st.warning(
                                        "Plano bloqueado: "
                                        + str(
                                            durable_plan_result.get("reason")
                                            or durable_plan_result.get("status")
                                            or "UNKNOWN"
                                        )
                                    )
                            except Exception as exc:
                                st.error(
                                    "Plano bloqueado em modo seguro: "
                                    + type(exc).__name__
                                    + "."
                                )

                        durable_plan = st.session_state.get(
                            _AION_GLOBAL_DURABLE_CLOSURE_PLAN_KEY
                        )
                        if isinstance(durable_plan, Mapping):
                            st.caption(
                                "Durable closure plan: "
                                + str(
                                    durable_plan.get("plan_digest") or ""
                                )[:24]
                                + "… · runtime SHA "
                                + str(
                                    durable_plan.get("source_runtime_sha") or ""
                                )[:12]
                                + "… · flag vinculada "
                                + str(
                                    durable_plan.get("feature_flag_state")
                                    or "UNKNOWN"
                                )
                                + "."
                            )
                            durable_phrase = st.text_input(
                                'Digite exatamente "PERSISTIR FECHAMENTO INCIDENTE WORKER GLOBAL"',
                                value="",
                                key="aion_global_durable_closure_phrase",
                            )
                            durable_confirm = st.checkbox(
                                "Confirmo que revisei o closure record, runtime "
                                "SHA, estado do Worker, feature flag e rollback.",
                                value=False,
                                key="aion_global_durable_closure_confirm",
                            )
                            if st.button(
                                "✅ Criar autorização de persistência do fechamento",
                                key="aion_global_durable_closure_approve",
                                disabled=not bool(
                                    durable_confirm
                                    and approve_durable_closure_plan is not None
                                ),
                                width="stretch",
                            ):
                                try:
                                    durable_approved = (
                                        approve_durable_closure_plan(
                                            access,
                                            durable_plan,
                                            confirmation=True,
                                            confirmation_phrase=durable_phrase,
                                        )
                                    )
                                    if (
                                        durable_approved.get("status")
                                        == "APPROVED_FOR_DURABLE_CLOSURE_PERSISTENCE"
                                    ):
                                        st.session_state[
                                            _AION_GLOBAL_DURABLE_CLOSURE_APPROVAL_KEY
                                        ] = durable_approved.get("approval")
                                        st.success(
                                            "Autorização curta criada na sessão. "
                                            "Ainda nenhuma escrita foi executada."
                                        )
                                    else:
                                        st.warning(
                                            "Autorização bloqueada: "
                                            + str(
                                                durable_approved.get("reason")
                                                or durable_approved.get("status")
                                                or "UNKNOWN"
                                            )
                                        )
                                except Exception as exc:
                                    st.error(
                                        "Autorização bloqueada: "
                                        + type(exc).__name__
                                        + "."
                                    )

                        durable_approval = st.session_state.get(
                            _AION_GLOBAL_DURABLE_CLOSURE_APPROVAL_KEY
                        )
                        durable_approval_valid = False
                        if (
                            isinstance(durable_approval, Mapping)
                            and isinstance(durable_human_record, Mapping)
                            and validate_durable_closure_approval is not None
                        ):
                            try:
                                durable_approval_check = (
                                    validate_durable_closure_approval(
                                        access,
                                        durable_human_record,
                                        runtime_result,
                                        durable_approval,
                                    )
                                )
                                durable_approval_valid = (
                                    durable_approval_check.get("state")
                                    == "APPROVED"
                                )
                            except Exception:
                                durable_approval_valid = False

                        durable_final_confirm = st.checkbox(
                            "SEGUNDA CONFIRMAÇÃO: autorizo agora somente a "
                            "persistência real do registro humano de fechamento. "
                            "A feature flag e o estado do Worker devem permanecer "
                            "inalterados.",
                            value=False,
                            key="aion_global_durable_closure_final_confirm",
                        )
                        if st.button(
                            "🚨 Persistir registro humano de fechamento",
                            key="aion_global_durable_closure_execute",
                            disabled=not bool(
                                durable_approval_valid
                                and durable_final_confirm
                                and persist_human_incident_closure_record
                                is not None
                                and not conflict
                            ),
                            width="stretch",
                        ):
                            decision = guardian_decision(
                                "save_checkpoint",
                                access,
                                approved=True,
                                feature_flags=flags,
                            )
                            if not decision["allowed"]:
                                st.error(decision["reason"])
                            else:
                                try:
                                    durable_result = (
                                        persist_human_incident_closure_record(
                                            access,
                                            durable_human_record,
                                            runtime_result,
                                            durable_approval,
                                            cfg,
                                            confirmation=True,
                                        )
                                    )
                                    st.session_state[
                                        _AION_GLOBAL_DURABLE_CLOSURE_RESULT_KEY
                                    ] = durable_result
                                    if (
                                        durable_result.get("status")
                                        == "CONFIRMED"
                                        and durable_result.get("saved")
                                        and durable_result.get("verified")
                                    ):
                                        saved_checkpoint = (
                                            ensure_operating_checkpoint(
                                                durable_result.get("checkpoint")
                                            )
                                        )
                                        saved_checkpoint["operating"][
                                            "dirty"
                                        ] = False
                                        _set_working_checkpoint(
                                            saved_checkpoint,
                                            dirty=False,
                                        )
                                        st.session_state[
                                            _WORKING_SOURCE_KEY
                                        ] = checkpoint_source_digest(
                                            saved_checkpoint
                                        )
                                        for key in (
                                            _AION_GLOBAL_DURABLE_CLOSURE_FLAG_EVIDENCE_KEY,
                                            _AION_GLOBAL_DURABLE_CLOSURE_PLAN_KEY,
                                            _AION_GLOBAL_DURABLE_CLOSURE_APPROVAL_KEY,
                                        ):
                                            st.session_state.pop(key, None)
                                        st.success(
                                            "Registro humano de fechamento "
                                            "persistido, relido e confirmado. "
                                            "Feature flag e Worker permaneceram "
                                            "separados."
                                        )
                                        st.rerun()
                                    elif (
                                        durable_result.get("status")
                                        == "ROLLED_BACK"
                                    ):
                                        st.error(
                                            "A persistência foi revertida "
                                            "automaticamente porque uma invariante "
                                            "pós-escrita mudou."
                                        )
                                        rollback_source = (
                                            runtime_result.get("checkpoint")
                                            if isinstance(
                                                runtime_result.get(
                                                    "checkpoint"
                                                ),
                                                Mapping,
                                            )
                                            else {}
                                        )
                                        restored = ensure_operating_checkpoint(
                                            rollback_source
                                        )
                                        restored["operating"]["dirty"] = False
                                        _set_working_checkpoint(
                                            restored,
                                            dirty=False,
                                        )
                                        st.session_state[
                                            _WORKING_SOURCE_KEY
                                        ] = checkpoint_source_digest(restored)
                                        st.rerun()
                                    else:
                                        st.error(
                                            "Persistência do fechamento não foi "
                                            "concluída. Estado: "
                                            + str(
                                                durable_result.get("status")
                                                or "UNKNOWN"
                                            )
                                            + " · motivo: "
                                            + str(
                                                durable_result.get("reason")
                                                or "não informado"
                                            )
                                            + "."
                                        )
                                except Exception as exc:
                                    st.error(
                                        "Persistência do fechamento falhou em "
                                        "modo seguro: "
                                        + type(exc).__name__
                                        + "."
                                    )

                        durable_result = st.session_state.get(
                            _AION_GLOBAL_DURABLE_CLOSURE_RESULT_KEY
                        )
                        if isinstance(durable_result, Mapping):
                            st.caption(
                                "Persistência durável: "
                                + str(
                                    durable_result.get("status") or "UNKNOWN"
                                )
                                + " · registro compartilhado persistido: "
                                + (
                                    "SIM"
                                    if durable_result.get(
                                        "shared_closure_record_persisted"
                                    )
                                    else "NÃO"
                                )
                                + " · Incident Center alterado: NÃO"
                                + " · feature flag alterada: NÃO"
                                + " · Worker alterado: NÃO"
                                + " · reativação autorizada: NÃO"
                                + " · trading real: NÃO."
                            )

        with st.expander("🛑 Desativação de segurança da feature flag"):
            st.caption(
                "Desativar a flag impede novos wake-ups do Worker Global pelo "
                "pulso agendado. Não altera o Checkpoint nem executa tick."
            )
            deactivate_phrase = st.text_input(
                'Digite exatamente "DESATIVAR WORKER GLOBAL"',
                value="",
                key="aion_global_deactivation_phrase",
            )
            deactivate_confirm = st.checkbox(
                "Confirmo a desativação da feature flag do Worker Global.",
                value=False,
                key="aion_global_deactivation_confirm",
            )
            if st.button(
                "🛑 Desativar feature flag do Worker Global",
                key="aion_global_deactivation_execute",
                disabled=not bool(
                    deactivate_confirm
                    and deactivate_global_worker_feature_flag is not None
                ),
                width="stretch",
            ):
                decision = guardian_decision(
                    "write_runtime",
                    access,
                    approved=True,
                    feature_flags=flags,
                )
                if not decision["allowed"]:
                    st.error(decision["reason"])
                else:
                    try:
                        deactivate_result = (
                            deactivate_global_worker_feature_flag(
                                access,
                                cfg,
                                confirmation=True,
                                confirmation_phrase=deactivate_phrase,
                            )
                        )
                        if deactivate_result.get("status") in {
                            "DISABLED",
                            "ALREADY_DISABLED",
                        }:
                            st.success(
                                "Feature flag do Worker Global confirmada como "
                                + str(
                                    deactivate_result.get(
                                        "feature_flag_state"
                                    )
                                    or "DISABLED"
                                )
                                + "."
                            )
                        else:
                            st.error(
                                "Desativação não confirmada. Estado: "
                                + str(
                                    deactivate_result.get("status")
                                    or "UNKNOWN"
                                )
                                + "."
                            )
                    except Exception as exc:
                        st.error(
                            "Desativação bloqueada em modo seguro: "
                            + type(exc).__name__
                            + "."
                        )

    if st.button(
        "💾 Salvar Checkpoint Mestre no runtime",
        key="aion_save_checkpoint",
        disabled=persistence_blocked,
        help=(
            "A escrita ocorre apenas no branch de runtime, exige estado seguro do runtime "
            "e este clique conta como aprovação explícita. "
            "Transições novas para Global Worker ARMED usam uma cerimônia separada."
        ),
    ):
        decision = guardian_decision(
            "save_checkpoint",
            access,
            approved=True,
            feature_flags=flags,
        )
        if not decision["allowed"]:
            st.error(decision["reason"])
        else:
            result = save_runtime_checkpoint(
                deepcopy(checkpoint),
                cfg,
                approved=True,
                expected_sha=str(persistence_preflight.get("expected_sha") or ""),
            )
            if result.get("saved") and result.get("verified"):
                saved_checkpoint = ensure_operating_checkpoint(result.get("checkpoint"))
                saved_checkpoint["operating"]["dirty"] = False
                _set_working_checkpoint(saved_checkpoint, dirty=False)
                st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(saved_checkpoint)
                st.success("Checkpoint Mestre salvo, relido e confirmado no runtime.")
                st.session_state["aion_checkpoint_save_result"] = result
            else:
                st.warning(
                    "Checkpoint não foi confirmado como persistido. "
                    f"Estado: {result.get('status')} · motivo: {result.get('reason','não informado')}. "
                    "As alterações locais continuam marcadas como pendentes."
                )

    st.divider()
    st.markdown("#### Recuperação / Rollback do Checkpoint")
    st.caption(
        "Usa o histórico versionado do Checkpoint no branch de runtime. "
        "Listar e pré-visualizar são somente leitura. Restaurar exige revisão íntegra, "
        "SHA atual, confirmação explícita e Guardian."
    )

    if st.button(
        "🔎 Carregar histórico de recuperação",
        key="aion_checkpoint_history_load",
        width="stretch",
    ):
        st.session_state["aion_checkpoint_history"] = list_checkpoint_revisions(
            cfg,
            limit=12,
        )
        st.session_state.pop("aion_recovery_candidate", None)

    history = st.session_state.get("aion_checkpoint_history")
    if isinstance(history, Mapping):
        history_status = str(history.get("status") or "UNKNOWN")
        items = [
            dict(item)
            for item in list(history.get("items", []) or [])
            if isinstance(item, Mapping)
        ]
        if history_status == "CONFIRMED":
            if items:
                st.dataframe(
                    [{
                        "Revisão": item.get("short_revision"),
                        "Data": item.get("created_at"),
                        "Mensagem": item.get("message"),
                    } for item in items],
                    width="stretch",
                    hide_index=True,
                )
                revisions = [str(item.get("revision") or "") for item in items]
                labels = {
                    str(item.get("revision") or ""):
                    f"{item.get('short_revision')} · {item.get('created_at') or 'sem data'} · {item.get('message') or 'sem mensagem'}"
                    for item in items
                }
                selected_revision = st.selectbox(
                    "Revisão para pré-visualizar",
                    revisions,
                    format_func=lambda value: labels.get(value, value),
                    key="aion_recovery_revision",
                )
                if st.button(
                    "👁️ Pré-visualizar revisão",
                    key="aion_recovery_preview",
                ):
                    st.session_state["aion_recovery_candidate"] = load_checkpoint_revision(
                        selected_revision,
                        cfg,
                    )
            else:
                st.info("Nenhuma revisão histórica do Checkpoint foi retornada.")
        else:
            st.warning(
                "Histórico de recuperação não confirmado. "
                f"Estado: {history_status} · motivo: {history.get('reason','não informado')}."
            )

    candidate = st.session_state.get("aion_recovery_candidate")
    if isinstance(candidate, Mapping):
        candidate_status = str(candidate.get("status") or "UNKNOWN")
        if candidate_status != "CONFIRMED":
            st.warning(
                "A revisão selecionada não pôde ser confirmada. "
                f"Estado: {candidate_status} · motivo: {candidate.get('reason','não informado')}."
            )
        else:
            integrity = (
                candidate.get("integrity")
                if isinstance(candidate.get("integrity"), Mapping)
                else {}
            )
            preview_preflight = recovery_preflight(runtime_result, candidate)
            rc1,rc2,rc3 = st.columns(3)
            rc1.metric("Revisão", str(candidate.get("revision") or "")[:10])
            rc2.metric("Integridade", str(integrity.get("state") or "UNKNOWN"))
            rc3.metric("Digest", str(candidate.get("digest") or "")[:16])

            local_dirty = bool(st.session_state.get(_WORKING_DIRTY_KEY, False))
            if local_dirty:
                st.warning(
                    "Há alterações locais ainda não persistidas. "
                    "Salve ou descarte essas alterações antes de restaurar uma revisão histórica."
                )
            elif not preview_preflight.get("allowed"):
                st.warning(
                    "Restauração bloqueada em modo seguro: "
                    f"{preview_preflight.get('reason','preflight não confirmado')}."
                )
            else:
                st.warning(
                    "A restauração substituirá o Checkpoint runtime atual por esta revisão histórica "
                    "através de escrita condicional no SHA atual. Não existe restauração automática."
                )
                confirm_restore = st.checkbox(
                    "Confirmo que revisei esta versão e quero restaurar o Checkpoint Mestre",
                    value=False,
                    key="aion_recovery_explicit_approval",
                )
                if st.button(
                    "↩️ Restaurar revisão selecionada",
                    key="aion_recovery_restore",
                    type="primary",
                    disabled=not bool(confirm_restore),
                    width="stretch",
                ):
                    decision = guardian_decision(
                        "restore_checkpoint",
                        access,
                        approved=True,
                        feature_flags=flags,
                    )
                    if not decision["allowed"]:
                        st.error(decision["reason"])
                    else:
                        result = restore_checkpoint_revision(
                            candidate,
                            runtime_result,
                            cfg,
                            approved=True,
                        )
                        if result.get("saved") and result.get("verified"):
                            restored = ensure_operating_checkpoint(result.get("checkpoint"))
                            restored["operating"]["dirty"] = False
                            _set_working_checkpoint(restored, dirty=False)
                            st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(restored)
                            st.session_state[_WORKING_CONFLICT_KEY] = False
                            st.session_state["aion_checkpoint_recovery_result"] = result
                            st.session_state.pop("aion_recovery_candidate", None)
                            st.success(
                                "Checkpoint restaurado, relido e verificado. "
                                "O evento de recuperação foi registrado na auditoria."
                            )
                            st.rerun()
                        else:
                            st.error(
                                "A recuperação não foi confirmada. "
                                f"Estado: {result.get('status')} · motivo: {result.get('reason','não informado')}."
                            )

    st.markdown("#### Camada de Verdade")
    for item in TRUTH_RULES:
        st.markdown(f"- {item}")


def _render_promotions(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    account_entitlement_audit: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🎟️ Promoções")
    st.caption(
        "Campanhas e códigos ficam persistidos no Checkpoint Mestre. "
        "O código completo é mostrado somente na criação; o checkpoint guarda apenas hash + últimos 4 caracteres."
    )
    _context_voice(
        "Promoções",
        (
            "Bem-vindo a Promoções. Aqui preparamos períodos gratuitos, cupons e descontos "
            "com limite de uso e auditoria. Criar ou aprovar um código não concede acesso automaticamente."
        ),
        key="aion_promotions_voice",
    )

    promo = checkpoint.get("promotions") if isinstance(checkpoint.get("promotions"), Mapping) else {}
    campaigns = list(promo.get("campaigns", []) or [])
    redemptions = list(promo.get("redemptions", []) or [])
    summary = promotions_summary(campaigns, redemptions)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Campanhas", summary["campaigns"])
    c2.metric("Aprovadas", summary["approved"])
    c3.metric("Ativas confirmadas", summary["active"])
    c4.metric("Resgates confirmados", summary["confirmed_redemptions"])

    st.markdown("#### Criar campanha")
    benefit_labels = {
        "TRIAL_DAYS": "Período grátis (dias)",
        "PERCENT_OFF": "Desconto percentual",
        "FIXED_DISCOUNT": "Desconto fixo",
    }
    with st.form("aion_promo_campaign_form", clear_on_submit=True):
        name = st.text_input("Nome da campanha")
        benefit_type = st.selectbox(
            "Tipo de benefício",
            list(PROMO_BENEFIT_TYPES),
            format_func=lambda x: benefit_labels.get(x, x),
        )
        if benefit_type == "TRIAL_DAYS":
            benefit_value = st.number_input("Dias grátis", min_value=1, max_value=365, value=7, step=1)
        elif benefit_type == "PERCENT_OFF":
            benefit_value = st.number_input("Desconto (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
        else:
            benefit_value = st.number_input("Desconto fixo", min_value=0.01, value=10.0, step=1.0)
        max_uses = st.number_input("Limite máximo de usos", min_value=1, max_value=1000000, value=100, step=1)
        starts_at = st.text_input("Início ISO opcional", placeholder="2026-10-01T00:00:00-04:00")
        expires_at = st.text_input("Expiração ISO opcional", placeholder="2026-10-31T23:59:59-04:00")
        create_campaign = st.form_submit_button("Gerar campanha e código", type="primary")

    if create_campaign:
        try:
            campaign, plain_code = new_campaign(
                name,
                benefit_type=benefit_type,
                benefit_value=benefit_value,
                max_uses=max_uses,
                starts_at=starts_at,
                expires_at=expires_at,
                source=str(access.get("username") or "ADMIN"),
            )
            campaigns = upsert_campaign(campaigns, campaign)
            updated = update_promotions_checkpoint(
                checkpoint,
                campaigns=campaigns,
                redemptions=redemptions,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "promotion_campaign_created",
                f"Campanha criada: {campaign['name']}",
                evidence={
                    "campaign_id": campaign["campaign_id"],
                    "benefit_type": campaign["benefit"]["type"],
                    "max_uses": campaign["limits"]["max_uses"],
                    "code_last4": campaign["code"]["last4"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.session_state["aion_last_plain_promo_code"] = {
                "campaign_id": campaign["campaign_id"],
                "code": plain_code,
            }
            st.success("Campanha criada. Copie o código abaixo agora; ele não será persistido em texto puro.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a campanha: {type(exc).__name__}")

    last_code = st.session_state.get("aion_last_plain_promo_code")
    if isinstance(last_code, Mapping):
        st.markdown("#### Código recém-gerado · exibição única da sessão")
        st.code(str(last_code.get("code") or ""))
        st.caption(
            f"Campanha {last_code.get('campaign_id')}. "
            "O Checkpoint Mestre armazena somente o hash do código; perder este texto exige criar outro código/campanha."
        )
        if st.button("Ocultar código da sessão", key="aion_hide_plain_promo_code"):
            st.session_state.pop("aion_last_plain_promo_code", None)
            st.rerun()

    if campaigns:
        rows = []
        for campaign in campaigns:
            benefit = campaign.get("benefit") or {}
            rows.append({
                "ID": campaign.get("campaign_id"),
                "Status": campaign.get("status"),
                "Campanha": campaign.get("name"),
                "Benefício": f"{benefit.get('type')} · {benefit.get('value')}",
                "Código": "••••" + str((campaign.get("code") or {}).get("last4") or ""),
                "Usos": f"{(campaign.get('limits') or {}).get('confirmed_uses',0)}/{(campaign.get('limits') or {}).get('max_uses',0)}",
                "Aprovada": bool((campaign.get("approval") or {}).get("approved",False)),
                "Ativa confirmada": bool((campaign.get("provider_activation") or {}).get("confirmed",False)),
            })
        st.dataframe(rows, width="stretch", hide_index=True)
        selected_id = st.selectbox(
            "Campanha selecionada",
            [str(c.get("campaign_id")) for c in campaigns],
            key="aion_selected_promo_campaign",
        )
        selected = next((c for c in campaigns if str(c.get("campaign_id")) == selected_id), None)
        if isinstance(selected, Mapping):
            benefit = selected.get("benefit") or {}
            st.write(
                f"**{selected.get('name')}** · {benefit.get('type')} = {benefit.get('value')} · "
                f"status **{selected.get('status')}**."
            )
            if st.button("✅ Aprovar campanha", key="aion_promo_approve"):
                try:
                    approved = approve_campaign(selected, access)
                    campaigns = upsert_campaign(campaigns, approved)
                    updated = update_promotions_checkpoint(
                        checkpoint,
                        campaigns=campaigns,
                        redemptions=redemptions,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "promotion_campaign_approved",
                        f"Campanha aprovada: {approved['campaign_id']}",
                        evidence={"campaign_id":approved["campaign_id"]},
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight = activation_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            st.caption(
                f"Ativação comercial: {'ELEGÍVEL PARA CONECTOR' if preflight['allowed'] else 'BLOQUEADA'} · "
                f"{preflight['reason']}"
            )
            if bool((selected.get("approval") or {}).get("approved",False)) and flags.get("promotion_activation"):
                st.info(
                    "A feature flag de promoção está ligada, mas esta tela ainda não ativa acesso real. "
                    "Status ACTIVE só será aceito quando um provedor/registro de assinaturas devolver evidência confirmada."
                )
    else:
        st.info("Nenhuma campanha registrada.")

    st.warning(
        "Ativação real de promoção está "
        + (
            "HABILITADA POR FLAG, mas ainda exige Guardian e provedor/registro real."
            if flags.get("promotion_activation")
            else "DESLIGADA por feature flag."
        )
    )




def _render_entitlements(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    account_entitlement_audit: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🔐 Assinaturas & Entitlements")
    st.caption(
        "Área comercial de direitos de acesso. Entitlement é separado do login, do perfil USER/SALES/ADMIN, "
        "do pagamento, do cupom e de Promoções. Criar ou aprovar uma solicitação NÃO altera conta nem libera acesso."
    )
    _context_voice(
        "Assinaturas",
        (
            "Bem-vindo a Assinaturas e Entitlements. Aqui o AION separa o direito comercial de acesso "
            "de login, perfil, pagamento e cupom. Nenhuma solicitação libera acesso automaticamente."
        ),
        key="aion_entitlements_voice",
    )
    entitlement_block = (
        checkpoint.get("entitlements")
        if isinstance(checkpoint.get("entitlements"), Mapping)
        else {}
    )
    entitlements = list(entitlement_block.get("records", []) or [])
    ent_summary = entitlement_summary(entitlements)

    e1,e2,e3,e4 = st.columns(4)
    e1.metric("Solicitações", ent_summary["records"])
    e2.metric("Aprovadas", ent_summary["approved"])
    e3.metric("Ativas confirmadas", ent_summary["active_confirmed"])
    e4.metric("Efetivas agora", ent_summary["effective_now"])

    with st.form("aion_entitlement_request_form", clear_on_submit=True):
        subject_ref = st.text_input(
            "Referência do cliente/conta",
            placeholder="ex.: cliente.01 ou customer_ref",
        )
        scope = st.text_input(
            "Escopo do direito",
            value="APP_ACCESS",
            help="Identificador técnico, sem definir preço ou plano comercial.",
        )
        source_kind = st.selectbox(
            "Origem da solicitação",
            list(ENTITLEMENT_SOURCE_KINDS),
        )
        source_ref = st.text_input(
            "Referência externa opcional",
            placeholder="ID de evento, campanha ou pedido — se existir",
        )
        ent_starts_at = st.text_input(
            "Início ISO opcional",
            key="aion_entitlement_starts_at",
            placeholder="2026-10-01T00:00:00-04:00",
        )
        ent_expires_at = st.text_input(
            "Expiração ISO opcional",
            key="aion_entitlement_expires_at",
            placeholder="2026-11-01T00:00:00-04:00",
        )
        ent_note = st.text_area(
            "Nota administrativa",
            key="aion_entitlement_note",
            placeholder="Motivo da solicitação. Não use este campo como prova de pagamento.",
        )
        create_entitlement = st.form_submit_button(
            "Criar solicitação de entitlement",
            type="primary",
        )

    if create_entitlement:
        try:
            item = new_entitlement_request(
                subject_ref,
                scope=scope,
                source_kind=source_kind,
                source_ref=source_ref,
                starts_at=ent_starts_at,
                expires_at=ent_expires_at,
                note=ent_note,
            )
            entitlements = upsert_entitlement(entitlements, item)
            updated = update_entitlements_checkpoint(
                checkpoint,
                records=entitlements,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "entitlement_request_created",
                f"Entitlement solicitado: {item['entitlement_id']}",
                evidence={
                    "entitlement_id": item["entitlement_id"],
                    "subject_ref": item["subject_ref"],
                    "scope": item["scope"],
                    "source_kind": item["source"]["kind"],
                    "account_registry_changed": False,
                    "role_changed": False,
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success(
                "Solicitação criada. Nenhuma conta, perfil, pagamento ou acesso foi alterado."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a solicitação: {type(exc).__name__}")

    if entitlements:
        ent_rows=[]
        for item in entitlements:
            evidence=item.get("provider_evidence") or {}
            ent_rows.append({
                "ID":item.get("entitlement_id"),
                "Cliente/conta":item.get("subject_ref"),
                "Escopo":item.get("scope"),
                "Origem":(item.get("source") or {}).get("kind"),
                "Status":item.get("status"),
                "Aprovado":bool((item.get("approval") or {}).get("approved",False)),
                "Evidência externa":bool(evidence.get("confirmed",False)),
            })
        st.dataframe(ent_rows,width="stretch",hide_index=True)
        entitlement_id = st.selectbox(
            "Entitlement selecionado",
            [str(x.get("entitlement_id")) for x in entitlements],
            key="aion_selected_entitlement",
        )
        selected_entitlement = next(
            (x for x in entitlements if str(x.get("entitlement_id")) == entitlement_id),
            None,
        )
        if isinstance(selected_entitlement, Mapping):
            st.write(
                f"**{selected_entitlement.get('subject_ref')}** · "
                f"{selected_entitlement.get('scope')} · "
                f"status **{selected_entitlement.get('status')}**."
            )
            if st.button(
                "✅ Aprovar solicitação de entitlement",
                key="aion_entitlement_approve",
            ):
                try:
                    approved_entitlement = approve_entitlement_request(
                        selected_entitlement,
                        access,
                    )
                    entitlements = upsert_entitlement(
                        entitlements,
                        approved_entitlement,
                    )
                    updated = update_entitlements_checkpoint(
                        checkpoint,
                        records=entitlements,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "entitlement_request_approved",
                        f"Entitlement aprovado: {approved_entitlement['entitlement_id']}",
                        evidence={
                            "entitlement_id": approved_entitlement["entitlement_id"],
                            "account_registry_changed": False,
                            "role_changed": False,
                            "executes_entitlement": False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            explicit_preflight = st.checkbox(
                "Aprovo somente o preflight deste entitlement (não libera acesso)",
                key=f"aion_entitlement_preflight_{entitlement_id}",
            )
            ent_preflight = entitlement_activation_preflight(
                selected_entitlement,
                access,
                feature_flags=flags,
                approved=bool(explicit_preflight),
            )
            st.caption(
                f"Entitlement: {'ELEGÍVEL PARA CONECTOR' if ent_preflight['allowed'] else 'BLOQUEADO'} · "
                f"{ent_preflight['reason']}"
            )
            st.info(
                "Mesmo quando o preflight ficar elegível, esta tela não altera ATLASQUANT_USERS_JSON, "
                "não muda USER/SALES/ADMIN e não cria acesso efetivo. "
                "ACTIVE_CONFIRMED exige evidência concreta de um futuro registro/provedor."
            )
    else:
        st.info("Nenhuma solicitação de entitlement registrada.")

    st.warning(
        "Ativação real de entitlement está "
        + (
            "HABILITADA POR FLAG para preflight, mas ainda não existe conector que conceda acesso."
            if flags.get("entitlement_activation")
            else "DESLIGADA por feature flag."
        )
    )

    st.markdown("#### Auditoria Conta × Entitlement · somente leitura")
    st.caption(
        "Esta auditoria compara contas USER com entitlements APP_ACCESS confirmados. "
        "ADMIN e SALES são perfis internos e ficam isentos desta expectativa comercial. "
        "O resultado não participa do login e não revoga nem concede acesso."
    )
    account_audit = dict(account_entitlement_audit or {})
    if account_audit.get("schema") != "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1":
        account_audit = audit_account_entitlements(
            configured_users(),
            entitlements,
        )
    a1,a2,a3,a4 = st.columns(4)
    a1.metric("USER ativos", account_audit["active_user_accounts"])
    a2.metric("Com direito efetivo", account_audit["effective_user_accounts"])
    a3.metric(
        "Sem direito efetivo",
        account_audit["user_accounts_without_effective_entitlement"],
    )
    a4.metric(
        "Entitlements órfãos",
        account_audit["orphan_effective_entitlements"],
    )

    if account_audit["account_rows"]:
        audit_rows=[]
        labels={
            "ENTITLEMENT_EFFECTIVE":"OK · direito confirmado",
            "NO_EFFECTIVE_ENTITLEMENT":"REVISAR · sem direito confirmado",
            "DUPLICATE_EFFECTIVE_ENTITLEMENTS":"REVISAR · duplicidade",
            "INTERNAL_ROLE_EXEMPT":"INTERNO · isento",
            "ACCOUNT_INACTIVE":"CONTA INATIVA",
        }
        for row in account_audit["account_rows"]:
            audit_rows.append({
                "Conta":row["username"],
                "Perfil":row["role"],
                "Conta ativa":row["account_active"],
                "Entitlements efetivos":row["effective_entitlements"],
                "Auditoria":labels.get(row["state"],row["state"]),
            })
        st.dataframe(audit_rows,width="stretch",hide_index=True)
    else:
        st.info(
            "Nenhuma conta segura configurada foi encontrada para a auditoria. "
            "Isso não é tratado como cliente confirmado."
        )

    if account_audit["orphan_rows"]:
        with st.expander("Entitlements efetivos sem conta correspondente",expanded=False):
            st.dataframe(
                [{
                    "Entitlement":row["entitlement_id"],
                    "Referência":row["subject_ref"],
                    "Escopo":row["scope"],
                    "Estado":row["state"],
                } for row in account_audit["orphan_rows"]],
                width="stretch",
                hide_index=True,
            )

    if audit_requires_review(account_audit):
        st.warning(
            "A auditoria encontrou divergências para revisão administrativa. "
            "Nenhuma correção automática foi executada."
        )
    else:
        st.success(
            "Auditoria sem divergências comerciais detectadas no escopo APP_ACCESS. "
            "Enforcement continua desligado."
        )
    st.caption(
        "Enforcement: DESLIGADO · autenticação alterada: NÃO · provisionamento automático: NÃO · "
        "revogação automática: NÃO."
    )

    st.divider()
    st.markdown("#### 🧩 AION pessoal · isolamento por assinante")
    tenant_ready = tenant_readiness_summary(entitlements)
    tenant_policy = tenant_policy_snapshot()

    t1,t2,t3,t4 = st.columns(4)
    t1.metric("AION_PERSONAL", tenant_ready["personal_entitlements"])
    t2.metric("Ativos confirmados", tenant_ready["effective_confirmed"])
    t3.metric("Assinantes elegíveis", tenant_ready["effective_subjects"])
    t4.metric("Cross-tenant", "BLOQUEADO")

    duplicate_subjects = tenant_ready.get("duplicate_effective_subjects") or []
    if duplicate_subjects:
        st.warning(
            f"{len(duplicate_subjects)} referência(s) possuem mais de um entitlement AION_PERSONAL efetivo. "
            "Revisar duplicidade antes de qualquer ativação futura."
        )

    st.info(
        "Meu AION ainda NÃO está ativado para assinantes nesta tela. "
        "Este painel apenas audita a prontidão do isolamento; não cria tenant, não grava memória pessoal "
        "e não provisiona acesso."
    )
    readiness_rows=[
        {"Controle":"Entitlement AION_PERSONAL confirmado","Estado":f"{tenant_ready['effective_confirmed']} efetivo(s)"},
        {"Controle":"Memória ADMIN herdada","Estado":"NÃO" if not tenant_policy["admin_memory_inherited"] else "REVISAR"},
        {"Controle":"Documentos privados do projeto herdados","Estado":"NÃO" if not tenant_policy["project_docs_inherited"] else "REVISAR"},
        {"Controle":"Acesso a outro tenant","Estado":"BLOQUEADO" if not tenant_policy["cross_tenant_access"] else "REVISAR"},
        {"Controle":"Persistência pessoal em produção","Estado":"NÃO CONFIRMADA"},
        {"Controle":"Provedor externo automático","Estado":"DESLIGADO" if not tenant_policy["external_provider_enabled_by_default"] else "REVISAR"},
        {"Controle":"Cobrança automática","Estado":"DESLIGADA" if not tenant_policy["billing_enabled"] else "REVISAR"},
        {"Controle":"Trading real","Estado":"BLOQUEADO" if not tenant_policy["real_trading_enabled"] else "REVISAR"},
    ]
    st.dataframe(readiness_rows,width="stretch",hide_index=True)
    st.caption(
        "Prontidão somente leitura · subscriber shell: DESLIGADO · persistência runtime pessoal: NÃO CONFIRMADA · "
        "provisionamento automático: NÃO."
    )

    st.markdown("#### 🛡️ Privacidade & ciclo de vida do AION pessoal")
    privacy_ready = tenant_privacy_readiness()
    privacy_policy = tenant_privacy_policy_snapshot()
    p1,p2,p3,p4 = st.columns(4)
    p1.metric("Classes pessoais permitidas", privacy_ready["allowed_data_classes"])
    p2.metric("Exportação", "CONTRATO PRONTO")
    p3.metric("Exclusão", "PLANO MANUAL")
    p4.metric("Exclusão automática", "DESLIGADA")

    st.caption(
        "Estas regras são controles técnicos internos de privacidade e ciclo de vida. "
        "As janelas abaixo são defaults de revisão do produto, não certificação jurídica/compliance."
    )
    class_rows = []
    review_days = privacy_policy.get("retention_review_days") or {}
    for item in privacy_policy.get("personal_data_classes") or []:
        key = str(item.get("key") or "")
        class_rows.append({
            "Classe": item.get("label"),
            "Finalidade": item.get("purpose"),
            "Sensibilidade": item.get("sensitivity"),
            "Revisão interna": (
                f"{int(review_days.get(key))} dias"
                if review_days.get(key) is not None
                else "sem janela definida"
            ),
        })
    if class_rows:
        st.dataframe(class_rows,width="stretch",hide_index=True)

    privacy_controls = [
        {"Controle":"Memória ADMIN no tenant","Estado":"BLOQUEADA"},
        {"Controle":"Documentos privados do projeto","Estado":"BLOQUEADOS"},
        {"Controle":"Cópia cross-tenant","Estado":"BLOQUEADA"},
        {"Controle":"Exportação automática","Estado":"DESLIGADA"},
        {"Controle":"Exclusão automática","Estado":"DESLIGADA"},
        {"Controle":"Limpeza após rotação de credencial","Estado":"REVISÃO MANUAL"},
        {"Controle":"Persistência pessoal","Estado":"AINDA DESLIGADA"},
        {"Controle":"Compliance legal afirmado","Estado":"NÃO"},
    ]
    st.dataframe(privacy_controls,width="stretch",hide_index=True)
    st.info(
        "Quando o AION pessoal for ativado no futuro, exportação e exclusão deverão operar somente "
        "no namespace do próprio assinante, com confirmação de identidade e auditoria. "
        "Nenhum dado pessoal é criado, exportado ou excluído por este painel."
    )



def render_aion_admin_console(
    access: Mapping[str, Any] | None,
    *,
    market_context: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    specialist_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    access_map = dict(access or {})
    market = dict(market_context or {})
    system = dict(system_context or {})

    if not is_admin(access_map):
        st.error("AION oficial do administrador está bloqueado para esta sessão.")
        return {
            "schema": SCHEMA,
            "allowed": False,
            "reason": "ADMIN_REQUIRED",
        }

    flags = feature_flag_snapshot(_flag_overrides())
    provider = provider_status(feature_flags=flags, env=_provider_env())
    memory_summary = canonical_memory_summary()
    cfg = _runtime_config()
    runtime_result = load_runtime_checkpoint(cfg, timeout=6.0)
    merged = merged_checkpoint(runtime_result)
    source_checkpoint = merged["checkpoint"]
    checkpoint = _working_checkpoint(source_checkpoint)
    entitlement_section = (
        checkpoint.get("entitlements")
        if isinstance(checkpoint.get("entitlements"), Mapping)
        else {}
    )
    entitlement_records = list(entitlement_section.get("records", []) or [])
    foundation_diagnostics: list[dict[str, str]] = []

    try:
        configured_account_rows = configured_users()
    except Exception as exc:
        configured_account_rows = {}
        foundation_diagnostics.append({
            "component": "account_registry",
            "error_type": type(exc).__name__,
        })

    try:
        account_entitlement_audit = audit_account_entitlements(
            configured_account_rows,
            entitlement_records,
        )
    except Exception as exc:
        account_entitlement_audit = _unknown_account_entitlement_audit(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "account_entitlement_audit",
            "error_type": type(exc).__name__,
        })

    try:
        status_board = build_master_status_board(
            checkpoint=checkpoint,
            runtime_result=runtime_result,
            provider=provider,
            feature_flags=flags,
            system_context=system,
            market_context=market,
            account_entitlement_audit=account_entitlement_audit,
            working_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
        )
    except Exception as exc:
        status_board = _unknown_status_board(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "master_status_board",
            "error_type": type(exc).__name__,
        })

    try:
        approval_inbox = collect_approval_inbox(checkpoint)
    except Exception as exc:
        approval_inbox = _unknown_approval_inbox(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "approval_inbox",
            "error_type": type(exc).__name__,
        })

    reliability_budget = normalize_budget(
        (checkpoint.get("aion") or {}).get("model_budget", {})
        if isinstance(checkpoint.get("aion"), Mapping)
        else {}
    )
    try:
        preliminary_reliability = reliability_snapshot(
            system_context=system,
            market_context=market,
            provider_status=provider,
            runtime_result=runtime_result,
            budget=reliability_budget,
            incident_snapshot={},
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        )
    except Exception as exc:
        preliminary_reliability = {
            "schema":"ATLASQUANT_AION_RELIABILITY_GOVERNANCE_V1",
            "posture":"UNKNOWN",
            "data_guardian":{"state":"UNKNOWN","reconciliation":{"observations":[],"conflict_count":0,"critical_conflict_count":0}},
            "cost_guardian":{"state":"UNKNOWN","automatic_billing":False,"automatic_upgrade":False},
            "memory_protection":{"state":"UNKNOWN","write_safe_precondition":False},
            "rollback_governance":{"state":"STANDBY","automatic_rollback":False},
            "degraded_mode":{"state":"DEGRADED_SAFE","can_authorize_market_action":False,"real_orders_enabled":False},
            "next_actions":["Revisar a camada Reliability & Governance."],
            "automatic_failover":False,
            "automatic_repair":False,
            "automatic_rollback":False,
            "automatic_paid_fallback":False,
            "real_orders_enabled":False,
            "executes_action":False,
        }
        foundation_diagnostics.append({
            "component":"reliability_governance_preflight",
            "error_type":type(exc).__name__,
        })
    system["reliability"] = preliminary_reliability

    try:
        incident_snapshot = collect_incidents(
            checkpoint=checkpoint,
            runtime_result=runtime_result,
            system_context=system,
            account_audit=account_entitlement_audit,
        )
        if reconcile_global_worker_incident_center is not None:
            incident_snapshot = reconcile_global_worker_incident_center(
                incident_snapshot,
                st.session_state.get(_AION_GLOBAL_SUPERVISION_KEY),
                runtime_result,
            )
    except Exception as exc:
        incident_snapshot = {
            "schema":"ATLASQUANT_AION_INCIDENT_CENTER_V1",
            "incidents":[],
            "closed_incidents":[],
            "closed_total":0,
            "total":0,
            "counts":{"INFO":0,"LOW":0,"MEDIUM":0,"HIGH":0,"CRITICAL":0},
            "highest_severity":"UNKNOWN",
            "has_critical":False,
            "rollback_review_recommended":False,
            "rollback_reasons":[],
            "automatic_containment":False,
            "automatic_rollback":False,
            "automatic_secret_rotation":False,
            "automatic_account_mutation":False,
            "real_orders_enabled":False,
            "executes_action":False,
            "truth_state":"UNKNOWN",
        }
        foundation_diagnostics.append({
            "component":"incident_center",
            "error_type":type(exc).__name__,
        })

    try:
        final_reliability = reliability_snapshot(
            system_context=system,
            market_context=market,
            provider_status=provider,
            runtime_result=runtime_result,
            budget=reliability_budget,
            incident_snapshot=incident_snapshot,
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        )
    except Exception as exc:
        final_reliability = preliminary_reliability
        foundation_diagnostics.append({
            "component":"reliability_governance_final",
            "error_type":type(exc).__name__,
        })
    system["reliability"] = final_reliability

    continuity_section = (
        checkpoint.get("continuity")
        if isinstance(checkpoint.get("continuity"), Mapping)
        else {}
    )
    continuity_state = continuity_summary(
        list(continuity_section.get("missions", []) or []),
        list(continuity_section.get("handoffs", []) or []),
    )
    interface_validation_state = (
        dict(system.get("interface_validation"))
        if isinstance(system.get("interface_validation"), Mapping)
        else interface_validation_mission(
            system.get("critical_surfaces")
            if isinstance(system.get("critical_surfaces"), Mapping)
            else {}
        )
    )
    publication_state = (
        dict(system.get("publication_truth"))
        if isinstance(system.get("publication_truth"), Mapping)
        else {}
    )
    release_gate_state = (
        dict(system.get("release_gate"))
        if isinstance(system.get("release_gate"), Mapping)
        else release_gate(
            publication_truth=publication_state,
            interface_validation=interface_validation_state,
        )
    )
    try:
        executive_snapshot = executive_pulse(
            runtime_result=runtime_result,
            approval_inbox=approval_inbox,
            incident_snapshot=incident_snapshot,
            status_board=status_board,
            continuity_summary=continuity_state,
            interface_validation=interface_validation_state,
            publication_truth=publication_state,
            release_gate_snapshot=release_gate_state,
            reliability_snapshot=final_reliability,
            live_event_snapshot=(
                system.get("live_event_intelligence")
                if isinstance(system.get("live_event_intelligence"), Mapping)
                else {}
            ),
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
            foundation_diagnostics=foundation_diagnostics,
        )
    except Exception as exc:
        executive_snapshot = {
            "schema":"ATLASQUANT_AION_EXECUTIVE_PULSE_V1",
            "posture":"UNKNOWN",
            "primary":{
                "priority":"P2",
                "area":"🛠️ Desenvolvimento",
                "title":"Pulso Executivo indisponível",
                "detail":"A priorização executiva não pôde ser confirmada nesta execução.",
                "next_action":"Usar a Próxima Ação AION e o Painel Mestre até revisar esta camada.",
                "source":"safe_fallback",
            },
            "attention_items":[],
            "attention_count":0,
            "runtime_status":str(runtime_result.get("status") or "UNKNOWN"),
            "integrity_state":"UNKNOWN",
            "approval_count":int(approval_inbox.get("total") or 0),
            "incident_count":int(incident_snapshot.get("total") or 0),
            "critical_incidents":0,
            "active_missions":int(continuity_state.get("active_missions") or 0),
            "blocked_missions":int(continuity_state.get("blocked_missions") or 0),
            "checkpoint_dirty":bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            "checkpoint_conflict":bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
            "degraded_components":len(foundation_diagnostics),
            "interface_validation_state":str(interface_validation_state.get("state") or "UNKNOWN"),
            "interface_validation_confirmed":int(interface_validation_state.get("confirmed") or 0),
            "interface_validation_total":int(interface_validation_state.get("total") or 3),
            "interface_validation_remaining":int(interface_validation_state.get("remaining") or 3),
            "interface_validation_complete":bool(interface_validation_state.get("all_confirmed_current_build",False)),
            "publication_state":str(publication_state.get("state") or "UNKNOWN"),
            "publication_main_match":str(publication_state.get("main_match") or "UNKNOWN"),
            "production_verification":str(publication_state.get("production_verification") or "UNKNOWN"),
            "can_claim_latest_main_live":bool(publication_state.get("can_claim_latest_main_live",False)),
            "release_gate_state":str(release_gate_state.get("state") or "UNKNOWN"),
            "release_gate_confirmed_stages":int(release_gate_state.get("confirmed_stages") or 0),
            "release_gate_total_stages":int(release_gate_state.get("total_stages") or 4),
            "release_gate_next_stage":str(release_gate_state.get("next_stage") or ""),
            "release_gate_claim_allowed":bool(release_gate_state.get("release_claim_allowed",False)),
            "recommended_workspace":"🛠️ Desenvolvimento",
            "executes_action":False,
            "real_orders_enabled":False,
        }
        foundation_diagnostics.append({
            "component":"executive_pulse",
            "error_type":type(exc).__name__,
        })

    try:
        copilot_snapshot = build_admin_copilot_snapshot(
            status_board=status_board,
            incident_snapshot=incident_snapshot,
            executive_snapshot=executive_snapshot,
            reliability_snapshot=final_reliability,
            system_context=system,
            max_items=6,
        )
    except Exception as exc:
        copilot_snapshot = {
            "schema":"ATLASQUANT_AION_ADMIN_COPILOT_V1",
            "state":"UNKNOWN",
            "items":[],
            "attention_count":0,
            "primary":None,
            "evidence_only":True,
            "promotes_setup":False,
            "automatic_setup_promotion":False,
            "automatic_approval":False,
            "automatic_feature_change":False,
            "automatic_repair":False,
            "automatic_deploy":False,
            "automatic_publish":False,
            "automatic_charge":False,
            "real_trading_enabled":False,
            "executes_action":False,
        }
        foundation_diagnostics.append({
            "component":"admin_copilot",
            "error_type":type(exc).__name__,
        })
    system["admin_copilot"] = copilot_snapshot

    try:
        commander_snapshot = commander_briefing(
            checkpoint=checkpoint,
            system_context=system,
            executive_snapshot=executive_snapshot,
        )
    except Exception as exc:
        commander_snapshot = {
            "schema":"ATLASQUANT_AION_OPERATIONAL_INTELLIGENCE_V1",
            "mode":"COMMANDER",
            "posture":"UNKNOWN",
            "objective":"Não confirmado.",
            "next_action":"Revisar a camada de inteligência operacional.",
            "blockers":[],
            "active_missions":0,
            "release_gate_state":"UNKNOWN",
            "publication_state":"UNKNOWN",
            "executive_priority":"P2",
            "executive_area":"🛠️ Desenvolvimento",
            "audit":{"status":"UNKNOWN","counts":{},"rows":[],"independent_sources":0,"conflict_count":0},
            "evidence_confidence":{"score":0,"label":"SEM_EVIDENCIA","is_profit_probability":False},
            "executes_action":False,
            "automatic_repair":False,
            "automatic_deploy":False,
            "real_orders_enabled":False,
        }
        foundation_diagnostics.append({
            "component":"aion_operational_intelligence",
            "error_type":type(exc).__name__,
        })
    system["commander_snapshot"] = commander_snapshot

    _render_header(
        access_map,
        str(runtime_result.get("status") or "UNKNOWN"),
        str(provider.get("state") or "UNKNOWN"),
        system,
    )
    _render_admin_brief(access_map, executive_snapshot)
    _render_executive_grid(memory_summary, runtime_result, provider, market)

    if foundation_diagnostics:
        degraded = ", ".join(
            f"{item['component']} ({item['error_type']})"
            for item in foundation_diagnostics
        )
        st.warning(
            "AION abriu em modo degradado seguro nas camadas auxiliares: "
            f"{degraded}. Nenhum estado ausente foi tratado como confirmado."
        )
        st.caption(
            "A leitura completa dessas camadas não pôde ser confirmada nesta execução. "
            "Somente o tipo do erro é exibido; mensagens internas não são expostas. "
            "Nenhuma ação externa, permissão ou trading real foi habilitado pelo fallback."
        )

    jump_request = st.session_state.pop(_AION_WORKSPACE_JUMP_KEY, None)
    if jump_request in AION_WORKSPACES:
        st.session_state["aion_admin_workspace"] = jump_request

    selected_workspace = st.selectbox(
        "Área AION",
        AION_WORKSPACES,
        key="aion_admin_workspace",
        help=(
            "Carrega uma área administrativa por vez. Isso reduz a carga da interface "
            "e evita montar workspaces não selecionados no celular."
        ),
    )
    st.caption("AION Admin · navegação estável · uma área por vez · Guardian permanece ativo.")

    workspace_error_type = ""
    try:
        if selected_workspace == "🧠 Central":
            _render_central(
                access_map, checkpoint, runtime_result, memory_summary, flags,
                system, status_board, approval_inbox, incident_snapshot,
                executive_snapshot, copilot_snapshot,
                specialist_snapshot=specialist_snapshot,
            )
        elif selected_workspace == "🗂️ Secretaria":
            _render_secretary(access_map, checkpoint, flags, system, market, status_board, approval_inbox)
        elif selected_workspace == "📈 Trading":
            _render_trading(market, system)
        elif selected_workspace == "🎬 Studio":
            _render_studio(access_map, checkpoint, flags)
        elif selected_workspace == "💼 Negócios":
            _render_business(access_map, checkpoint, flags)
        elif selected_workspace == "🧪 Laboratório":
            _render_laboratory(access_map, checkpoint, flags, incident_snapshot)
        elif selected_workspace == "🛠️ Desenvolvimento":
            _render_development(access_map, checkpoint, source_checkpoint, runtime_result, flags)
        elif selected_workspace == "🔐 Assinaturas":
            _render_entitlements(
                access_map,
                checkpoint,
                flags,
                account_entitlement_audit,
            )
        elif selected_workspace == "🎟️ Promoções":
            _render_promotions(
                access_map,
                checkpoint,
                flags,
            )
    except Exception as exc:
        workspace_error_type = type(exc).__name__
        st.error(
            "Esta área do AION encontrou um erro isolado. "
            "A Central e as demais áreas continuam disponíveis."
        )
        st.caption(
            f"Diagnóstico seguro: {workspace_error_type}. "
            "Nenhuma permissão operacional foi ampliada e nenhuma ação externa foi executada."
        )

    with st.expander("Política Custo Zero"):
        for item in ZERO_COST_RULES:
            st.markdown(f"- {item}")

    return {
        "schema": SCHEMA,
        "allowed": True,
        "runtime_status": runtime_result.get("status"),
        "runtime_confirmed": bool(merged.get("runtime_confirmed")),
        "memory_documents": memory_summary.get("document_count"),
        "provider_state": provider.get("state"),
        "feature_flags": flags,
        "checkpoint_digest": checkpoint_digest(checkpoint),
        "checkpoint_integrity_state": str(
            ((runtime_result.get("integrity") or {}) if isinstance(runtime_result.get("integrity"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "guardian_blocked_now": int(
            guardian_posture(access_map, feature_flags=flags).get("blocked_now") or 0
        ),
        "tenant_privacy_contract_ready": bool(
            tenant_privacy_readiness().get("policy_defined", False)
        ),
        "incident_center_total": int(incident_snapshot.get("total") or 0),
        "incident_center_has_critical": bool(incident_snapshot.get("has_critical", False)),
        "incident_center_rollback_review": bool(
            incident_snapshot.get("rollback_review_recommended", False)
        ),
        "executive_posture": str(executive_snapshot.get("posture") or "UNKNOWN"),
        "executive_primary_area": str(
            ((executive_snapshot.get("primary") or {}) if isinstance(executive_snapshot.get("primary"), Mapping) else {}).get("area")
            or "🧠 Central"
        ),
        "executive_attention_count": int(executive_snapshot.get("attention_count") or 0),
        "central_view_mode": str(st.session_state.get("aion_central_view_mode") or "Essencial"),
        "continuity_active_missions": int(
            continuity_summary(
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("missions", []) or []),
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("handoffs", []) or []),
            ).get("active_missions") or 0
        ),
        "continuity_handoff_count": int(
            continuity_summary(
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("missions", []) or []),
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("handoffs", []) or []),
            ).get("handoff_count") or 0
        ),
        "checkpoint_dirty": bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
        "checkpoint_conflict": bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        "knowledge_graph_nodes": int(
            knowledge_graph_summary(
                checkpoint.get("knowledge_graph")
                if isinstance(checkpoint.get("knowledge_graph"), Mapping)
                else {}
            ).get("nodes") or 0
        ),
        "evaluation_lab_candidates": int(
            evaluation_lab_summary(
                checkpoint.get("evaluation_lab")
                if isinstance(checkpoint.get("evaluation_lab"), Mapping)
                else {}
            ).get("human_review_candidates") or 0
        ),
        "digital_twins_total": int(
            digital_twin_summary(
                list(
                    ((checkpoint.get("digital_twins") or {}) if isinstance(checkpoint.get("digital_twins"), Mapping) else {}).get("records", [])
                    or []
                )
            ).get("twins") or 0
        ),
        "dev_fusion_candidates": int(
            dev_fusion_summary(
                list(
                    ((checkpoint.get("dev_fusion") or {}) if isinstance(checkpoint.get("dev_fusion"), Mapping) else {}).get("pipelines", [])
                    or []
                )
            ).get("human_review_candidates") or 0
        ),
        "release_confidence_ready": int(
            release_confidence_summary(
                list(
                    ((checkpoint.get("release_confidence") or {}) if isinstance(checkpoint.get("release_confidence"), Mapping) else {}).get("records", [])
                    or []
                )
            ).get("human_review_ready") or 0
        ),
        "tool_hub_tools": int(
            tool_hub_summary(
                checkpoint.get("tool_hub")
                if isinstance(checkpoint.get("tool_hub"), Mapping)
                else {},
                checkpoint.get("portable_core")
                if isinstance(checkpoint.get("portable_core"), Mapping)
                else {},
            ).get("tools") or 0
        ),
        "durable_tasks_resumable": int(
            durable_tasks_summary(
                list(
                    ((checkpoint.get("durable_tasks") or {}) if isinstance(checkpoint.get("durable_tasks"), Mapping) else {}).get("records", [])
                    or []
                )
            ).get("resumable") or 0
        ),
        "resilience_safe_mode": str(
            resilience_summary(
                checkpoint.get("resilience")
                if isinstance(checkpoint.get("resilience"), Mapping)
                else {}
            ).get("safe_mode") or "UNKNOWN"
        ),
        "resilience_open_circuits": int(
            resilience_summary(
                checkpoint.get("resilience")
                if isinstance(checkpoint.get("resilience"), Mapping)
                else {}
            ).get("open_circuits") or 0
        ),
        "portable_core_workspaces": int(
            portable_core_summary(
                checkpoint.get("portable_core")
                if isinstance(checkpoint.get("portable_core"), Mapping)
                else {}
            ).get("workspaces") or 0
        ),
        "vault_policy_ok": bool(
            vault_summary(
                checkpoint.get("vault")
                if isinstance(checkpoint.get("vault"), Mapping)
                else {}
            ).get("policy_ok", False)
        ),
        "task_summary": queue_summary((checkpoint.get("operating") or {}).get("tasks", [])),
        "status_board_counts": status_board.get("counts"),
        "status_board_has_unresolved": bool(status_board.get("has_unresolved")),
        "approval_inbox_total": int(approval_inbox.get("total") or 0),
        "approval_inbox_has_pending": bool(approval_inbox.get("has_pending")),
        "commercial_access_audit_needs_review": audit_requires_review(account_entitlement_audit),
        "live_event_background_state": str(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("background_watch_state")
            or "UNKNOWN"
        ),
        "live_event_continuous_24h_confirmed": bool(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("continuous_runtime_confirmed", False)
        ),
        "live_event_journal_count": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("journal_event_count")
            or 0
        ),
        "live_event_external_delivery_allowed": False,
        "foundation_status": "DEGRADED_SAFE" if foundation_diagnostics else "OK",
        "foundation_diagnostics": foundation_diagnostics,
        "selected_workspace": selected_workspace,
        "workspace_status": "ERROR_ISOLATED" if workspace_error_type else "OK",
        "workspace_error_type": workspace_error_type,
        "critical_surface_counts": (
            ((system.get("critical_surfaces") or {}) if isinstance(system.get("critical_surfaces"), Mapping) else {}).get("counts")
            or {}
        ),
        "critical_surfaces_have_unresolved": bool(
            ((system.get("critical_surfaces") or {}) if isinstance(system.get("critical_surfaces"), Mapping) else {}).get("has_unresolved", True)
        ),
        "guided_revalidation_state": str(
            ((system.get("guided_revalidation") or {}) if isinstance(system.get("guided_revalidation"), Mapping) else {}).get("state")
            or "NONE"
        ),
        "interface_validation_state": str(interface_validation_state.get("state") or "UNKNOWN"),
        "interface_validation_confirmed": int(interface_validation_state.get("confirmed") or 0),
        "interface_validation_total": int(interface_validation_state.get("total") or 3),
        "interface_validation_remaining": int(interface_validation_state.get("remaining") or 3),
        "interface_validation_complete": bool(
            interface_validation_state.get("all_confirmed_current_build", False)
        ),
        "publication_state": str(publication_state.get("state") or "UNKNOWN"),
        "publication_main_match": str(publication_state.get("main_match") or "UNKNOWN"),
        "production_verification": str(
            publication_state.get("production_verification") or "UNKNOWN"
        ),
        "can_claim_latest_main_live": bool(
            publication_state.get("can_claim_latest_main_live", False)
        ),
        "release_gate_state": str(release_gate_state.get("state") or "UNKNOWN"),
        "release_gate_progress_pct": float(
            release_gate_state.get("progress_pct") or 0.0
        ),
        "release_gate_claim_allowed": bool(
            release_gate_state.get("release_claim_allowed", False)
        ),
        "release_gate_next_stage": str(
            release_gate_state.get("next_stage") or ""
        ),
        "learning_episodes": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("episodes") or 0
        ),
        "learning_open_episodes": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("open_episodes") or 0
        ),
        "learning_human_review_candidates": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("human_review_candidates") or 0
        ),
        "learning_automatic_changes": False,
        "reliability_posture": str(final_reliability.get("posture") or "UNKNOWN"),
        "reliability_degraded_mode": str(
            ((final_reliability.get("degraded_mode") or {}) if isinstance(final_reliability.get("degraded_mode"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_source_conflicts": int(
            ((((final_reliability.get("data_guardian") or {}) if isinstance(final_reliability.get("data_guardian"), Mapping) else {}).get("reconciliation") or {}) if isinstance(((final_reliability.get("data_guardian") or {}) if isinstance(final_reliability.get("data_guardian"), Mapping) else {}).get("reconciliation"), Mapping) else {}).get("conflict_count")
            or 0
        ),
        "reliability_memory_state": str(
            ((final_reliability.get("memory_protection") or {}) if isinstance(final_reliability.get("memory_protection"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_cost_state": str(
            ((final_reliability.get("cost_guardian") or {}) if isinstance(final_reliability.get("cost_guardian"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_automatic_repair": False,
        "reliability_automatic_rollback": False,
        "source_mesh_state": str(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("market_state")
            or "UNKNOWN"
        ),
        "source_mesh_live_confirmed": bool(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("market_live_confirmed", False)
        ),
        "source_mesh_observations": int(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("observation_count")
            or 0
        ),
        "source_mesh_fallbacks": int(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("fallback_or_unavailable")
            or 0
        ),
        "live_event_state": str(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "live_event_alerts": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("alert_count")
            or 0
        ),
        "live_event_urgent_review": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("urgent_review_count")
            or 0
        ),
        "live_event_24x7_confirmed": bool(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("continuous_runtime_confirmed", False)
        ),
        "commander_posture": str(commander_snapshot.get("posture") or "UNKNOWN"),
        "commander_objective": str(commander_snapshot.get("objective") or ""),
        "commander_next_action": str(commander_snapshot.get("next_action") or ""),
        "commander_evidence_confidence": int(
            ((commander_snapshot.get("evidence_confidence") or {}) if isinstance(commander_snapshot.get("evidence_confidence"), Mapping) else {}).get("score")
            or 0
        ),
        "commander_evidence_label": str(
            ((commander_snapshot.get("evidence_confidence") or {}) if isinstance(commander_snapshot.get("evidence_confidence"), Mapping) else {}).get("label")
            or "SEM_EVIDENCIA"
        ),
        "commander_executes_action": False,
        "admin_copilot_state": str(copilot_snapshot.get("state") or "UNKNOWN"),
        "admin_copilot_attention_count": int(copilot_snapshot.get("attention_count") or 0),
        "admin_copilot_executes_action": False,
        "admin_copilot_real_trading_enabled": False,
        "validation_center": validation_center_snapshot(
            system,
            runtime_status=runtime_result.get("status"),
        ),
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "AION_WORKSPACES", "render_aion_admin_console", "AION_ADMIN_CSS"]
