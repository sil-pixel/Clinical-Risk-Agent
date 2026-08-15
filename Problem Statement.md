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

The deployed DCMFNet model is trained on a **fully synthetic dataset** designed to reproduce the structure of the research problem without using confidential participant data.

---

# Objective

Build an AI system capable of:

1. Collecting structured mental health questionnaire responses.
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

It accepts structured questionnaire features and produces a research risk probability.

The Clinical Risk AI Agent treats DCMFNet as a black-box inference service.

Responsibilities of DCMFNet:

- deterministic inference
- probability estimation
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
4. RAG Engineer
      ↓
5. AI Engineer
      ↓
6. Backend Engineer
      ↓
7. Frontend Engineer
      ↓
8. Testing Agent
      ↓
9. Reviewer
      ↓
10. Documentation Agent
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

The RAG Engineer should define the scientific retrieval contract.

The AI Engineer should then build the intent-routing and LangGraph workflow around those established tool contracts.

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