# Clinical Risk AI Agent — Problem Statement

## Project Overview

The Clinical Risk AI Agent is an AI-powered research assistant designed to demonstrate a modern healthcare AI architecture that combines:

- A deterministic machine learning risk prediction model (DCMFNet)
- Large Language Models (LLMs)
- Retrieval-Augmented Generation (RAG)
- Tool calling
- Stateful agent workflows
- Scientific literature retrieval

The project serves as an **AI engineering portfolio project** and research prototype.

It is **not** intended to diagnose schizophrenia, provide medical advice, or replace clinicians.

The current prototype is intended for portfolio evaluation and informal testing by invited users such as friends, developers, and researchers. It is a public-facing demonstration, not a patient product, and no user should act on a DCMFNet output. Results must be accompanied by uncertainty and limitations and must not replace qualified professional judgment.

The portfolio MVP supports English free-text interaction only. Safety interception runs before language validation. After safety permits normal processing, a local language gate blocks unsupported or uncertain language before intent classification, RAG, LLM generation, or DCMFNet and displays: `This prototype currently supports English only. Please enter your question in English.` Rephrased English intent is classified by a project-fine-tuned `distilbert/distilbert-base-uncased` encoder with calibrated confidence and abstention; the base checkpoint is not used zero-shot.

The longer-term startup direction is an India-first, clinician-only hospital product for silent research validation. It will never be patient-facing. During silent validation, outputs must not influence diagnosis, treatment, triage, or other care decisions. Hospital research mode requires separate clinical, regulatory, privacy, security, data-provenance, and model-validation approval and must not inherit demonstration-only assumptions automatically.

The deployed DCMFNet model is trained on a **fully synthetic dataset** designed to reproduce the structure of the research problem without using confidential participant data.

---

# Objective

Build an AI system capable of:

1. Collecting structured mental health questionnaire responses through a manual questionnaire for fields with approved user-facing definitions.
2. Determining which information is still required.
3. Calling a trained DCMFNet model to estimate a research risk score.
4. Retrieving scientific evidence relevant to the user's questions or prediction.
5. Explaining the prediction in understandable language.
6. Answering follow-up educational questions.
7. Remaining grounded in scientific literature.
8. Clearly communicating uncertainty.
9. Never acting as a diagnostic system.

The project should demonstrate production-quality AI engineering rather than simply wrapping an LLM with a chat interface.

---

# High-Level Architecture

The application follows a deterministic, stateful workflow.

The system first determines **what the user wants**, then **what information is currently available**, executes the required tools, and finally asks the LLM to explain the results.

```
                         User
                           │
                           ▼
              Input Validation & Safety
                           │
                           ▼
                   Intent Router
                           │
                           ▼
              LangGraph State Machine
                           │
         ┌─────────────────┼──────────────────┐
         │                 │                  │
         ▼                 ▼                  ▼
 Collect Missing      Call DCMFNet        Retrieve
 Questionnaire        Risk Model API      Scientific Evidence
 Data                                       (RAG)
         │                 │                  │
         └─────────────────┼──────────────────┘
                           ▼
                 Structured Context
                           │
                           ▼
                          LLM
                           │
                           ▼
                 Response Validation
                           │
                           ▼
                          User
```

---

# Design Philosophy

The system follows one core principle:

> **Use deterministic systems whenever correctness matters. Use LLMs only where reasoning and communication are required.**

The LLM must never:

- calculate risk scores
- invent scientific evidence
- fabricate citations
- diagnose users

Instead, the LLM should orchestrate tools and communicate their outputs naturally.

---

# DCMFNet

DCMFNet is a deep learning model trained independently from this repository.

It accepts structured questionnaire features and produces two separate research risk probabilities:

- a positive-symptom risk probability (`SCZ18_Pos_Norm`) for positive symptoms of schizophrenia, including psychotic and manic symptoms
- a negative-symptom risk probability (`SCZ18_Neg_Norm`) for negative symptoms of schizophrenia, including depressive symptoms

The probabilities remain separate. They must not be combined, recalculated, or modified by the LLM.

Present valid probabilities separately as percentages while retaining their exact raw model values only inside the protected volatile request/session boundary. Percentage formatting is deterministic application logic, not an LLM responsibility. Do not introduce qualitative risk bands without scientifically validated thresholds. If a raw value is below `0.0` or above `1.0`, fail closed as an internal system variance: do not clamp it, pass it to the LLM, display an estimate, log it, or persist it. The UI displays exactly `Error: Unable to compute estimate due to an internal system variance. Please try again later.` The exact raw value is wiped with the protected failure object at request teardown.

Every valid result includes a plain-language explanation, the approved research-only disclaimer, and the synthetic-data indicator. This system performs prediction, not causal inference. Until validated feature importance is available, individual-answer questions receive: `This is a prediction, not a causal explanation. The model evaluates all 105 inputs together; no single answer can be identified as the cause of the result. Validated feature importance is not available for this result.`

For the portfolio MVP's manual questionnaire, PRS and batch-by-genetic-PC interaction inputs that cannot be measured from the user use a versioned generic profile populated from the selected artifact's exported training medians. The system must disclose that these genetic inputs are generic and unmeasured, must not describe the result as personalized genetic risk, and must never derive these values from family history, nationality, ethnicity, race, or descent.

The generic genetic profile is demonstration-only behavior. A future hospital research mode must reject it unless separately justified and approved through its research protocol, model contract, and regulatory process. The fail-closed out-of-range rule applies in every mode. The two modes must be distinguishable in configuration, state, results, telemetry, and tests so demonstration behavior cannot enter hospital workflows accidentally.

For the portfolio MVP, raw conversational text, questionnaire fields/tokens/vectors, inference inputs/results, probabilities, personalized responses, and session history have no permitted persistent destination, including an encrypted audit database. They exist only in volatile client/backend memory and are wiped after exactly 15 minutes of explicit-user inactivity, reset, relevant failure/crisis purge, or process restart. They never enter browser persistent storage/cache, logs, traces, analytics events, backups, or crash dumps. Runtime payloads cannot be sent to public LLM, embedding, moderation, tracing, or analytics APIs; models run locally or in an operator-controlled isolated India-fenced VPC with technical and contractual zero retention. Only pre-aggregated unlinkable product counters may persist. The MVP exposes no research-record or file-upload surface.

The Clinical Risk AI Agent treats DCMFNet as a black-box inference service.

Responsibilities of DCMFNet:

- deterministic inference
- separate positive- and negative-symptom probability estimation
- risk prediction

Responsibilities of the AI Agent:

- collecting questionnaire responses
- deciding workflow execution
- retrieving scientific literature
- explaining predictions
- answering follow-up questions

---

# Intent Routing

Every user request is first classified into a high-level intent.

Example intents include:

- Risk Assessment
- Explain My Risk
- Scientific Question
- Mental Health Education
- General Conversation
- Unsupported / Unsafe Request

The Intent Router determines **what the user wants**.

It does **not** decide whether sufficient information has already been collected.

---

# LangGraph Workflow

LangGraph orchestrates the application's state.

It determines:

- which questionnaire fields have already been collected
- which information is still missing
- when DCMFNet should be called
- when RAG should execute
- when the LLM should generate a response

Example:

```
User:
"I want to know my schizophrenia risk."

↓

Intent:
Risk Assessment

↓

Questionnaire Complete?

├── No
│
│ Ask missing questions
│
│ Update state
│
│ Continue assessment
│
└── Yes
      ↓
Call DCMFNet
```

Another example:

```
User:
"Why is my risk score high?"

↓

Intent:
Explain My Risk

↓

Prediction Available?

├── No
│
│ Complete assessment first
│
└── Yes
      ↓
Retrieve scientific evidence
      ↓
LLM explanation
```

---

# Retrieval-Augmented Generation (RAG)

Whenever the assistant makes scientific or medical claims, those claims should be grounded in retrieved literature.

Workflow:

```
User Question

↓

Embedding Search

↓

Relevant Literature

↓

LLM

↓

Grounded Explanation
```

Scientific knowledge should remain external to the model rather than embedded inside prompts.

General websites are not scientific sources. Authority discovery is limited to a versioned domain allowlist initially containing `*.who.int`, `*.cdc.gov`, `*.nih.gov`, `*.nhs.uk`, and configured Indian health-ministry/public-health domains under `*.gov.in`; DOI/PMID, date, quality, and retraction gates remain mandatory.

The scientific vector namespace must be disconnected from questionnaire tokens, patient-specific token matrices, feature vectors, inference payloads, session IDs, and identities. Mandatory metadata filtering admits only the approved scientific-publication/general-mental-health/non-patient class. Every two weeks, the vector pipeline verifies all active PMIDs/DOIs through PubMed and/or another approved retraction index and immediately purges newly detected deprecated or retracted evidence from active retrieval, caches, and context windows.

Every factual medical or scientific claim in an answer must have an explicit inline citation mapped to verified metadata from the current retrieval result. Uncited, speculative, or extrapolated claims are prohibited. A generation cycle receives no more than a configured 3-to-5 distinct highly relevant sources, defaulting to 5; fewer are allowed when fewer eligible sources exist. Conflicting evidence must preserve and cite each materially supported position within that cap or return a limitation rather than a one-sided conclusion.

The exact DCMFNet probability is displayed as an immutable model-tool result with artifact provenance, not cited to a paper as though literature validates the individual's number. Any medical or scientific interpretation around that result still requires an inline citation.

Raw matched excerpts do not appear in response prose. Inline citation markers open collapsed interactive metadata containers that show the retrieval-owned exact matched text string with DOI/PMID and bibliographic/quality metadata.

The current system produces predictions only. It does not determine what caused a clinical outcome and does not currently report individual feature importance.

Later, a locally validated SHAP integration may report the top three inputs that most influenced a specific prediction. The LLM may describe that model influence accurately. SHAP feature importance is not causal inference and must not be presented as proof that a feature caused the outcome. A feature's clinical relevance may be discussed separately when supported by inline-cited retrieved medical evidence.

## Supported conversational scope

The assistant uses approved scientific RAG for general mental health, genetics and environmental risk factors, diet and lifestyle, diabetes and physical health, and scientific context for existing model results.

Medication and treatment information is limited to general evidence summaries related to schizophrenia or other mental-health disorders. The assistant must not provide individualized prescribing, dosage, treatment selection, or medication-change instructions and must direct the user to an appropriate qualified professional. Medication questions should direct users to a psychiatrist or other prescribing doctor; psychological-support questions may also direct users to a psychologist or suitable mental-health professional.

Unrelated general medical questions are out of scope. The assistant provides at most a one- or two-line high-level response and directs the user to an appropriate doctor or healthcare professional. It does not invoke DCMFNet or the full RAG workflow for these questions.

DCMFNet may be invoked only for an explicit request to calculate positive/psychotic-symptom risk or negative/depressive-symptom risk, after `risk_assessment` routing, safety handling, and complete deterministic questionnaire validation. Discussion or education about psychosis, depression, schizophrenia, genetics, diet, lifestyle, diabetes, medication, treatment, or other health topics never authorizes inference by itself. Explaining an existing result uses the stored immutable result and RAG without rerunning DCMFNet unless a new assessment is explicitly requested.

---

# Tool Calling

The LLM should never perform deterministic computations itself.

Instead, it calls tools.

Expected tools include:

- calculate_risk()
- retrieve_papers()
- retrieve_model_information()
- validate_questionnaire()
- summarize_papers()

Additional tools may be added when appropriate.

---

# Embeddings

Embeddings enable semantic retrieval.

Users should be able to ask natural questions such as:

> Why did weed increase my score?

and retrieve literature discussing:

- cannabis
- psychosis
- schizophrenia risk

without relying on exact keyword matches.

---

# Structured Outputs

Internal communication between tools and the LLM should use structured objects whenever possible.

Example:

```json
{
  "risk_score": 0.24,
  "major_factors": [],
  "retrieved_papers": [],
  "summary": "...",
  "limitations": []
}
```

This improves:

- testing
- validation
- maintainability
- reproducibility

---

# Safety

The assistant must never:

- diagnose schizophrenia
- recommend medication
- guarantee future outcomes
- claim certainty
- fabricate citations
- fabricate model outputs

The assistant should always communicate:

- uncertainty
- limitations
- research-only nature

---

# Repository Goals

The project should demonstrate:

- modular architecture
- production-quality engineering
- deterministic workflows
- reusable components
- clean abstractions
- strong documentation
- comprehensive testing

---

# Expected Agent Architecture

Rather than one monolithic coding agent, the repository should use a collection of specialized implementation agents coordinated by a central orchestrator.


## Product Manager Agent

Responsible for:

- project planning
- feature prioritization
- task breakdown

---

## Architect Agent

Responsible for:

- software architecture
- directory structure
- interfaces
- dependency management

---

## AI Architect Agent

Responsible for:

- LLM and LangGraph architecture
- RAG architecture
- prompt and structured context design
- AI safety and grounding architecture
- LLM, embedding, and reranking provider/model selection criteria
- AI and retrieval evaluation strategy

The AI Architect designs the AI and RAG subsystems. The AI Engineer and RAG Engineer implement those designs within the Software Architect's system boundaries.

---

## Backend Engineer Agent

Responsible for:

- FastAPI
- API integration
- model serving
- routing
- endpoints

---

## AI Engineer Agent

Responsible for:

- LangChain
- LangGraph
- tool calling
- prompts
- agent workflow

---

## RAG Engineer Agent

Responsible for:

- document ingestion
- embeddings
- vector database
- retrieval
- reranking

---

## ML Engineer Agent

Responsible for:

- DCMFNet inference
- model loading
- prediction API
- model metadata

---

## Frontend Agent

Responsible for:

- Streamlit interface
- questionnaire UI
- visualization

---

## Testing Agent

Responsible for:

- unit tests
- integration tests
- end-to-end tests

---

## Reviewer Agent

Responsible for:

- code review
- architecture review
- identifying technical debt

---

## Documentation Agent

Responsible for:

- README
- architecture documentation
- API documentation
- setup guides

---

## Agent Workflow

Create agents/workflow.md as the shared reference for how these development agents should be used.

It should define a recommended sequence similar to:

```
1. Product Manager
      ↓
2. Software Architect
      ↓
3. ML Engineer
      ↓
4. AI Architect
      ↓
5. RAG Engineer
      ↓
6. AI Engineer
      ↓
7. Backend Engineer
      ↓
8. Frontend Engineer
      ↓
9. Testing Agent
      ↓
10. Reviewer
      ↓
11. Documentation Agent
```

Adjust the exact order if the repository or dependencies discovered during inspection justify it.

For each stage, document:

* what the agent should receive as input
* what it should produce
* what must be complete before the next stage begins
* which later agents may need to send work back for revision

The workflow should explicitly support iteration.

For example:

```
Testing Agent
    ↓
failure in LangGraph workflow
    ↓
AI Engineer
    ↓
Tester reruns tests
```
or:

```
Reviewer
    ↓
API boundary issue
    ↓
Software Architect / Backend Engineer
    ↓
Reviewer rechecks
```

The workflow is a development coordination document, not runtime orchestration code.

Initial dependency expectations

The Product Manager should first translate the problem statement into MVP scope, milestones, and acceptance criteria.

The Software Architect should then define repository structure, interfaces, service boundaries, and major architectural decisions.

The ML Engineer should establish the contract for the exported DCMFNet model before the rest of the system assumes its input/output interface.

The AI Architect should then design the LLM, LangGraph, and RAG architecture, including scientific source policy, retrieval/provenance flow, grounding, safety, provider criteria, and evaluation gates.

The RAG Engineer should implement and validate the approved scientific retrieval architecture and contract.

The AI Engineer should then implement the intent-routing and LangGraph workflow around the approved AI architecture and established tool contracts.

The Backend Engineer should expose and integrate the required APIs and services.

The Frontend Engineer should build against stable backend contracts rather than inventing its own application logic.

Testing, review, and documentation should happen after the core architecture is functioning, with feedback loops to the responsible implementation agent.

# Development Principles

All agents should:

- write modular code
- avoid unnecessary complexity
- minimize coupling
- maximize readability
- follow Python best practices
- produce production-quality code
- document important decisions
- prefer explicitness over magic
- favor deterministic behavior over autonomous decision making where possible

The repository should feel like a real production AI system rather than a collection of scripts.

---

# Final Goal

The completed project should allow someone to clone the repository, install the dependencies, run the application locally, complete a questionnaire, receive a deterministic DCMFNet risk estimate, view an evidence-grounded explanation generated using retrieved scientific literature, and inspect a clean, modular, production-quality AI architecture that demonstrates modern AI engineering practices.
