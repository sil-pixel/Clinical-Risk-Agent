"""Fixed user-facing reply texts and shared prompt fragments for the conversation layer.

Kept apart from orchestration so wording changes never touch control flow.
"""

from __future__ import annotations

from .routing import Intent

CRISIS_RESPONSE = (
    "If you or someone you know is in crisis, help is available. You are not alone. "
    "Please reach out now to Tele-MANAS at 14416 or 1800-89-14416 (free, 24/7), or "
    "the Vandrevala Foundation at +91 9999 666 555 (24/7). If there is immediate "
    "danger, call 112 or go to the nearest hospital emergency department."
)
EMERGENCY_RESPONSE = (
    "EMERGENCY DETECTED: This tool is not a triage or emergency response service. If you "
    "are experiencing a medical or psychological emergency, call 112 (India's national "
    "emergency number) or go immediately to the nearest hospital emergency department."
)
ACUTE_DISTRESS_RESPONSE = (
    "It sounds like you are experiencing a deeply overwhelming and stressful moment. "
    "Because this is an automated research demonstration, I cannot provide the clinical "
    "grounding or support you need right now. Please connect with a trusted friend, family "
    "member, or a qualified mental health professional immediately."
)
MINOR_RESPONSE = (
    "Access denied. This research prototype is approved for adults aged 18 and over. "
    "No risk calculation has been performed."
)
THIRD_PARTY_RESPONSE = (
    "I cannot assess or interpret another person's health information. I can provide "
    "general, non-personalized education, or that person may choose to use the adult "
    "research demonstration themselves."
)
DIAGNOSTIC_RESPONSE = (
    "I am an AI research prototype and cannot diagnose any medical or psychiatric condition."
)
PRESCRIPTIVE_RESPONSE = (
    "I cannot recommend, select, dose, evaluate, start, stop, or change medication or "
    "treatment plans. Please consult a registered medical practitioner, psychiatrist, or "
    "treating doctor before making any changes."
)
LANGUAGE_RESPONSE = "Input error: Language unsupported. Please resubmit your query in English."
ASSESSMENT_RESPONSE = (
    "I cannot calculate clinical probabilities or interpret metric values directly inside "
    "this chat window. To compute a simulated research risk estimate for psychotic or manic "
    "patterns based on generic genetic baselines, please click the link below to launch the "
    "assessment questionnaire."
)
CLARIFICATION_RESPONSE = "I didn't quite catch that. Please select what you would like to do:"
# Asked when the router has a plausible guess below the routing threshold.
SUGGESTION_QUESTIONS = {
    Intent.RISK_ASSESSMENT: "Did you want to estimate your own risk with the research questionnaire?",
    Intent.EXPLAIN_MY_RISK: "Did you want an explanation of your assessment result?",
    Intent.SCIENTIFIC_QUESTION: "Did you want to know what the research says about this?",
    Intent.MENTAL_HEALTH_EDUCATION: "Did you want a general explanation of this topic?",
    Intent.GENERAL_CONVERSATION: "Did you mean this as a general question, not a research or assessment request?",
}
SUGGESTION_FOOTER = "If not, choose another option or rephrase your message."
QUESTIONNAIRE_ACTION = {"id": "submit_risk_assessment_questionnaire",
                        "label": "Submit Risk Assessment Questionnaire"}
RESEARCH_ACTION = {"id": "ask_about_schizophrenia_and_clinical_associations",
                   "label": "Ask About Schizophrenia & Clinical Associations"}
NO_PRIOR_RESULT_RESPONSE = (
    "There is no validated assessment result in this session to explain. You can launch the "
    "research questionnaire if you would like to create one."
)
GENERAL_RESPONSE = (
    "Hello. You can chat normally, ask a mental-health research question, or open the "
    "optional research questionnaire."
)
UNSUPPORTED_RESPONSE = (
    "That request is outside this prototype's bounded research scope. Ask one of the listed "
    "research questions or open the optional research questionnaire."
)
GENERATION_UNAVAILABLE = (
    "I couldn't generate a validated evidence-based response at this time. Please try again later."
)
CRISIS_BACKSTOP_INSTRUCTION = (
    "Safety override: if the user's message suggests that they or someone else may be in "
    "crisis, at risk of suicide or self-harm, in danger, or facing a medical emergency, do not "
    "answer it; return response_kind=refusal with a one-sentence text. Use refusal for nothing else."
)
