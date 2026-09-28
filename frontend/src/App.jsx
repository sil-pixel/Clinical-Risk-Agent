import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ChatWorkspace from "./ChatWorkspace.jsx";
import EvaluationDashboard from "./EvaluationDashboard.jsx";
import { createSession, deleteSession, submitAssessment, getLatestAssessment,
  retryAssessmentExplanation } from "./api.js";
import {
  getOptionsForQuestion,
  questionnaireSections,
  totalQuestionCount,
} from "./questionnaireData.js";
import {
  getQuestionnaireStatus,
  getSectionStatus,
  SESSION_TTL_MS,
} from "./questionnaireState.js";

const activityEvents = ["pointerdown", "keydown", "touchstart"];

function ArrowIcon({ direction = "right" }) {
  return (
    <svg
      aria-hidden="true"
      className={direction === "left" ? "icon icon--left" : "icon"}
      viewBox="0 0 20 20"
    >
      <path d="M4 10h12M11 5l5 5-5 5" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg aria-hidden="true" className="status-icon" viewBox="0 0 20 20">
      <path d="m5 10 3 3 7-7" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg aria-hidden="true" className="brand-mark" viewBox="0 0 32 32">
      <path d="M16 3 27 7v7c0 7-4.6 12.1-11 15C9.6 26.1 5 21 5 14V7l11-4Z" />
      <path d="M10 16h3l2-5 3 9 2-4h3" />
    </svg>
  );
}

function Notice({ tone = "info", children }) {
  return <div className={`notice notice--${tone}`}>{children}</div>;
}

function App() {
  const [view, setView] = useState(() =>
    new URLSearchParams(window.location.search).get("view") === "evaluation" ? "evaluation" : "chat");
  const [sessionToken, setSessionToken] = useState("");
  const [sessionError, setSessionError] = useState("");
  const [answers, setAnswers] = useState({});
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [validationMessage, setValidationMessage] = useState("");
  const [systemMessage, setSystemMessage] = useState("");
  const [assessmentResult, setAssessmentResult] = useState(null);
  const [assessmentBusy, setAssessmentBusy] = useState(false);
  const [attestations, setAttestations] = useState({
    age_18_or_over: false,
    self_assessment: false,
    research_only_consent: false,
  });
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const inactivityTimer = useRef(null);
  const mainHeadingRef = useRef(null);

  useEffect(() => {
    if (assessmentResult?.explanation_status !== "pending" || !sessionToken) return;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const result = await getLatestAssessment(sessionToken);
        if (!cancelled) setAssessmentResult(result);
        if (!cancelled && result.explanation_status === "pending") {
          timer = window.setTimeout(poll, 1500);
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, 3000);
      }
    };
    timer = window.setTimeout(poll, 1000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [assessmentResult?.explanation_status, sessionToken]);

  const currentSection = questionnaireSections[currentSectionIndex];
  const overallStatus = useMemo(() => getQuestionnaireStatus(answers), [answers]);
  const sectionStatus = useMemo(
    () => getSectionStatus(currentSection, answers),
    [answers, currentSection],
  );

  const resetQuestionnaire = useCallback((reason = "Your answers have been cleared.") => {
    setAnswers({});
    setCurrentSectionIndex(0);
    setValidationMessage("");
    setSystemMessage(reason);
    setAssessmentResult(null);
    setAttestations({
      age_18_or_over: false,
      self_assessment: false,
      research_only_consent: false,
    });
    requestAnimationFrame(() => mainHeadingRef.current?.focus());
  }, []);

  const startSession = useCallback(async () => {
    try {
      setSessionError("");
      const session = await createSession();
      setSessionToken(session.session_token);
    } catch (error) {
      setSessionError(error.message);
    }
  }, []);

  const resetSession = useCallback(async () => {
    const previous = sessionToken;
    setSessionToken("");
    resetQuestionnaire("Your private session and answers have been cleared.");
    await deleteSession(previous).catch(() => {});
    await startSession();
  }, [resetQuestionnaire, sessionToken, startSession]);

  useEffect(() => {
    const scheduleExpiry = () => {
      window.clearTimeout(inactivityTimer.current);
      inactivityTimer.current = window.setTimeout(() => {
        resetQuestionnaire("For your privacy, the questionnaire was cleared after 30 minutes of inactivity.");
      }, SESSION_TTL_MS);
    };

    activityEvents.forEach((eventName) => window.addEventListener(eventName, scheduleExpiry));
    scheduleExpiry();
    return () => {
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, scheduleExpiry));
      window.clearTimeout(inactivityTimer.current);
    };
  }, [resetQuestionnaire]);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    if (isOnline && !sessionToken) startSession();
  }, [isOnline, sessionToken, startSession]);

  const selectAnswer = (questionId, optionId) => {
    setAnswers((current) => ({ ...current, [questionId]: optionId }));
    setValidationMessage("");
    setSystemMessage("");
  };

  const goToSection = (index) => {
    setCurrentSectionIndex(index);
    setValidationMessage("");
    window.scrollTo({ top: 0, behavior: "smooth" });
    requestAnimationFrame(() => mainHeadingRef.current?.focus());
  };

  const goForward = () => {
    if (sectionStatus.unansweredIds.length > 0) {
      const firstMissingId = sectionStatus.unansweredIds[0];
      setValidationMessage(
        `Please answer ${sectionStatus.unansweredIds.length} remaining ${sectionStatus.unansweredIds.length === 1 ? "question" : "questions"} before continuing.`,
      );
      requestAnimationFrame(() => document.getElementById(`${firstMissingId}-group`)?.focus());
      return;
    }
    if (currentSectionIndex < questionnaireSections.length - 1) {
      goToSection(currentSectionIndex + 1);
    }
  };

  const progressPercent = Math.round((overallStatus.answered / totalQuestionCount) * 100);
  const attestationsComplete = Object.values(attestations).every(Boolean);

  const calculateAssessment = async () => {
    if (!overallStatus.ready || !attestationsComplete || !sessionToken || assessmentBusy) return;
    setAssessmentBusy(true);
    setValidationMessage("");
    setAssessmentResult(null);
    try {
      const result = await submitAssessment(sessionToken, {
        questionnaire_version: "prototype_questionnaire_v1",
        answers,
        attestations,
      });
      setAssessmentResult(result);
      setSystemMessage("The protected assessment completed successfully.");
    } catch (error) {
      setValidationMessage(error.message);
    } finally {
      setAssessmentBusy(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#main" aria-label="Bodhica home">
          <ShieldIcon />
          <span>
            <strong>Bodhica</strong>
            <small>Private, research-only demonstration</small>
          </span>
        </a>
        <div className="header-actions">
          <button className={`button ${view === "chat" ? "button--primary" : "button--quiet"}`}
            type="button" onClick={() => setView("chat")}>Chat</button>
          <button className={`button ${view === "questionnaire" ? "button--primary" : "button--quiet"}`}
            type="button" onClick={() => setView("questionnaire")}>Questionnaire</button>
          <button className={`button ${view === "evaluation" ? "button--primary" : "button--quiet"}`}
            type="button" onClick={() => setView("evaluation")}>Evaluations</button>
          <button className="button button--quiet" type="button" onClick={resetSession}>
            Reset session
          </button>
        </div>
      </header>

      {!isOnline && (
        <div className="offline-banner" role="status">
          You're offline. Research estimates and evidence-based answers require a connection. No calculation has been performed.
        </div>
      )}

      {view === "evaluation" ? <EvaluationDashboard /> : view === "chat" ? (
        <ChatWorkspace token={sessionToken}
          sessionError={sessionError} onOpenQuestionnaire={() => setView("questionnaire")}
          onReset={resetSession} />
      ) : (
      <div className="layout">
        <aside className="sidebar" aria-label="Questionnaire progress">
          <div className="progress-card">
            <span className="progress-label">Overall progress</span>
            <strong>{progressPercent}%</strong>
            <div
              className="progress-track"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax={totalQuestionCount}
              aria-valuenow={overallStatus.answered}
              aria-label={`${overallStatus.answered} of ${totalQuestionCount} questions answered`}
            >
              <span style={{ width: `${progressPercent}%` }} />
            </div>
            <small>{overallStatus.answered} of {totalQuestionCount} answered</small>
          </div>

          <nav aria-label="Questionnaire sections">
            <ol className="section-list">
              {questionnaireSections.map((section, index) => {
                const status = getSectionStatus(section, answers);
                const isCurrent = index === currentSectionIndex;
                const isComplete = status.complete === section.questions.length;
                return (
                  <li key={section.id}>
                    <button
                      type="button"
                      className={`section-link${isCurrent ? " section-link--current" : ""}`}
                      aria-current={isCurrent ? "step" : undefined}
                      onClick={() => goToSection(index)}
                    >
                      <span className="section-number">{isComplete ? <CheckIcon /> : index + 1}</span>
                      <span>
                        <strong>{section.title}</strong>
                        <small>{status.answered}/{section.questions.length} answered</small>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          <div className="privacy-note">
            <strong>Kept in this tab only</strong>
            <p>Answers are not saved in browser storage and clear after 30 minutes without activity.</p>
          </div>
        </aside>

        <main id="main" className="main-content">
          <div className="sr-only" role="status" aria-live="polite">
            {systemMessage}
          </div>
          {systemMessage && <Notice tone="success">{systemMessage}</Notice>}

          <section className="intro-card" aria-labelledby="section-title">
            <span className="eyebrow">{currentSection.eyebrow}</span>
            <h1 id="section-title" ref={mainHeadingRef} tabIndex="-1">{currentSection.title}</h1>
            <p>{currentSection.description}</p>
            <div className="disclosure-grid">
              <div>
                <strong>Research demonstration</strong>
                <span>This is not a diagnosis, medical advice, or an emergency service.</span>
              </div>
              <div>
                <strong>Generic research profile</strong>
                <span>No genetic data is collected or interpreted for you.</span>
              </div>
            </div>
          </section>

          {validationMessage && (
            <div className="validation-summary" role="alert">
              <strong>Check this section</strong>
              <span>{validationMessage}</span>
            </div>
          )}

          <form onSubmit={(event) => event.preventDefault()} noValidate>
            <div className="question-list">
              {currentSection.questions.map((item, questionIndex) => {
                const options = getOptionsForQuestion(item);
                const isMissing = validationMessage && !answers[item.id];
                return (
                  <fieldset
                    className={`question-card${isMissing ? " question-card--invalid" : ""}`}
                    id={`${item.id}-group`}
                    key={item.id}
                    tabIndex={isMissing ? "-1" : undefined}
                    aria-describedby={item.note ? `${item.id}-note` : undefined}
                  >
                    <legend>
                      <span className="question-count">
                        Question {questionIndex + 1} of {currentSection.questions.length}
                      </span>
                      <span className="question-prompt">{item.prompt}</span>
                    </legend>
                    {item.note && <p className="question-note" id={`${item.id}-note`}>{item.note}</p>}
                    <div className="option-list">
                      {options.map((option) => (
                        <label className="option-card" key={option.id}>
                          <input
                            type="radio"
                            name={item.id}
                            value={option.id}
                            checked={answers[item.id] === option.id}
                            onChange={() => selectAnswer(item.id, option.id)}
                          />
                          <span className="radio-mark" aria-hidden="true" />
                          <span>{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                );
              })}
            </div>

            <div className="navigation-card">
              <div>
                <strong>{sectionStatus.answered} of {currentSection.questions.length} answered</strong>
              </div>
              <div className="navigation-actions">
                <button
                  className="button button--secondary"
                  type="button"
                  onClick={() => goToSection(currentSectionIndex - 1)}
                  disabled={currentSectionIndex === 0}
                >
                  <ArrowIcon direction="left" /> Previous
                </button>
                {currentSectionIndex < questionnaireSections.length - 1 ? (
                  <button className="button button--primary" type="button" onClick={goForward}>
                    Continue <ArrowIcon />
                  </button>
                ) : (
                  <button
                    className="button button--primary"
                    type="button"
                    disabled={!overallStatus.ready || !attestationsComplete || assessmentBusy
                      || !sessionToken || !isOnline}
                    onClick={calculateAssessment}
                    aria-describedby="calculation-status"
                  >
                    {assessmentBusy ? "Calculating…" : "Calculate research result"}
                  </button>
                )}
              </div>
            </div>
          </form>

          {currentSectionIndex === questionnaireSections.length - 1 && (
            <Notice tone={overallStatus.ready ? "success" : "warning"}>
              <strong id="calculation-status">Protected model calculation</strong>{" "}
              {overallStatus.unanswered > 0 && `${overallStatus.unanswered} questions remain unanswered. `}
              Complete all questions and attestations below before calculating.
            </Notice>
          )}

          {currentSectionIndex === questionnaireSections.length - 1 && (
            <section className="attestation-card" aria-labelledby="attestation-title">
              <h2 id="attestation-title">Before calculating</h2>
              {[
                ["age_18_or_over", "I confirm that I am aged 18 or over."],
                ["self_assessment", "I am completing this questionnaire only about myself."],
                ["research_only_consent", "I understand this is a research demonstration, not clinical care."],
              ].map(([id, label]) => (
                <label key={id}>
                  <input type="checkbox" checked={attestations[id]}
                    onChange={(event) => setAttestations((current) => ({
                      ...current, [id]: event.target.checked,
                    }))} />
                  <span>{label}</span>
                </label>
              ))}
            </section>
          )}

          {assessmentResult && (
            <section className="result-card" aria-labelledby="result-title">
              <span className="eyebrow eyebrow--dark">Simulated research output</span>
              <h2 id="result-title">Assessment result</h2>
              <div className="result-grid">
                <div><span>Positive-symptom estimate</span><strong>{assessmentResult.result.positive_symptom_research_probability}</strong><small>Includes hallucinations, delusions, psychotic and manic symptom patterns.</small></div>
                <div><span>Negative-symptom estimate</span><strong>{assessmentResult.result.negative_symptom_research_probability}</strong><small>This model’s target reflects depressive symptoms, such as low mood and loss of interest.</small></div>
              </div>
              {assessmentResult.explanation && (
                <p className="result-explanation">{assessmentResult.explanation}</p>
              )}
              {assessmentResult.explanation_status === "pending" && (
                <p role="status">Your scores are ready. Preparing the explanation…</p>
              )}
              {assessmentResult.explanation_status === "unavailable" && (
                <button className="button button--secondary" type="button" onClick={async () => {
                  try { setAssessmentResult(await retryAssessmentExplanation(sessionToken)); }
                  catch (error) { setValidationMessage(error.message); }
                }}>Retry explanation</button>
              )}
            </section>
          )}
        </main>
      </div>
      )}

      <footer>
        <p>Built for evaluation with synthetic training data. Do not use this questionnaire for clinical decisions.</p>
      </footer>
    </div>
  );
}

export default App;
