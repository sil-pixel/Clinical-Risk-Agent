# Product Evolution Strategy

Status: Product direction approved; hospital implementation and regulatory classification deferred

Owner: Product Manager

Date: 2026-08-26

Sources: [`Problem Statement.md`](../Problem%20Statement.md), [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md), and [`AI_ARCHITECTURE_REQUIREMENTS.md`](AI_ARCHITECTURE_REQUIREMENTS.md)

## Current focus: hosted prototype demonstration

Build the complete multi-turn prototype so invited friends, developers, evaluators, and researchers can test the product experience. Testers are not patients, and the prototype must not be used for diagnosis, treatment, screening, triage, or any health decision.

The prototype may use:

- the synthetic-data-trained DCMFNet artifacts
- the manual questionnaire after field definitions are reviewed
- `generic_genetic_profile_v1`
- the approved prototype-only percentage and out-of-range display rules
- explicit research-demonstration disclaimers
- anonymous, expiring sessions without a durable health record

The prototype must collect no identity or claim of clinical validity merely because it is hosted publicly.

## Future startup product: India hospital silent validation

The first hospital product is clinician-only and never patient-facing. Its purpose is silent research validation: run versioned models on ethically and contractually approved hospital research data, measure performance, and produce research reports without allowing outputs to affect patient care.

Hospital mode requires separate approval for:

- intended use and regulatory classification under India's Medical Devices Rules and current CDSCO Medical Device Software guidance
- hospital/ethics governance and research protocol
- data protection, consent or other lawful basis, minimization, retention, access, and audit policy
- clinical endpoints, representative data, model training, calibration, external validation, subgroup analysis, and statistical analysis plan
- clinician/researcher identity, RBAC, hospital tenancy, deployment environment, integration, and incident response
- medical-device quality, risk, software-lifecycle, cybersecurity, change-control, and post-market processes when applicable

## Non-negotiable separation

- Prototype users are never described as patients.
- Hospital users are authenticated clinicians or approved researchers; patients never interact with the system.
- Generic PRS/PCA assumptions are prototype-only and do not enter hospital research records.
- Prototype out-of-range display rules do not enter hospital research evaluation.
- Synthetic-artifact performance is not represented as clinical performance.
- Hospital outputs remain silent and cannot change diagnosis, treatment, triage, or workflow decisions.
- LLM explanations never alter model outputs or substitute for statistical/clinical validation.

## Scale-without-overbuilding principle

The prototype remains a modular monolith with clear ports for inference, retrieval, LLMs, state, identity, audit, and storage. Local adapters can later be replaced with managed or hospital-hosted implementations without changing domain contracts. Services are extracted only when security, scaling, regulatory isolation, or independent deployment provides an evidenced benefit.

## Promotion gate

No component is promoted from `prototype_demo` to `hospital_silent_research` merely because it works technically. Promotion requires an explicit evidence package, owner approval, versioned contract, mode-specific tests, security/privacy review, and documented rollback. Clinical decision support is a later product stage and requires a new product decision after silent validation; it is not implied by this strategy.
