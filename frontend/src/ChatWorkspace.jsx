import { useEffect, useRef, useState } from "react";

import { API_BASE } from "./api.js";

const suggestedQuestions = [
  "Tell me about schizophrenia.",
  "Is childhood ADHD associated with later substance abuse or dependence?",
  "Did the MTA childhood ADHD cohort find more frequent cannabis use and smoking by age 25?",
  "Is fifth-grade peer victimization associated with later adolescent substance use?",
  "Is cyberbullying victimization associated with later substance experimentation?",
  "Is bullying perpetration associated with smoking or drinking at age 13?",
];

/** Decode one SSE block into its typed event and JSON payload. */
function parseEvent(block) {
  let type = "message";
  let data = null;
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7);
    if (line.startsWith("data: ")) data = JSON.parse(line.slice(6));
  }
  return data ? { type, data } : null;
}

/** Render protected chat, research suggestions and optional questionnaire navigation. */
export default function ChatWorkspace({ token, sessionError, onOpenQuestionnaire, onReset }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello. You can chat normally, ask a mental-health research question, or open the optional questionnaire.",
      citations: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [phase, setPhase] = useState("");
  const [busy, setBusy] = useState(false);
  const threadRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages, phase]);

  /** Submit a chat turn and consume validated content, citations or streaming errors. */
  const submit = async (event, suppliedText, { confirmedIntent, displayText } = {}) => {
    event?.preventDefault();
    const text = (suppliedText ?? input).trim();
    if (!text || !token || busy) return;
    if (!confirmedIntent) setInput("");
    setBusy(true);
    setPhase("Starting protected checks…");
    setMessages((current) => [...current, { role: "user", text: displayText ?? text, citations: [] }]);
    let assistant = null;
    let completed = false;
    try {
      const response = await fetch(`${API_BASE}/v1/messages:stream`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(confirmedIntent
          ? { kind: "free_text", text, confirmed_intent: confirmedIntent }
          : { kind: "free_text", text }),
      });
      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error?.message || "The chat service is unavailable.");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          const eventData = parseEvent(block);
          if (!eventData) continue;
          if (eventData.type === "status") {
            setPhase(eventData.data.phase === "protected_preflight"
              ? "Checking request safety and scope…"
              : "Preparing and validating the response…");
          } else if (eventData.type === "validated_content") {
            assistant = {
              role: "assistant",
              text: eventData.data.message,
              responseKind: eventData.data.response_kind,
              limitation: eventData.data.limitation,
              actions: eventData.data.actions || [],
              sourceText: text,
              citations: [],
            };
            setMessages((current) => [...current, assistant]);
          } else if (eventData.type === "evidence" && assistant) {
            const citation = eventData.data;
            setMessages((current) => current.map((message, index) => (
              index === current.length - 1
                ? { ...message, citations: [...message.citations, citation] }
                : message
            )));
          } else if (eventData.type === "error") {
            throw new Error(`${eventData.data.message || "The request failed safely."}${eventData.data.code ? ` (${eventData.data.code})` : ''}`);
          } else if (eventData.type === "done") {
            completed = true;
          }
        }
        if (done) break;
      }
      if (!completed) throw new Error("The chat connection ended before the response completed. Please try again.");
    } catch (error) {
      setMessages((current) => [...current, {
        role: "assistant", text: error.message, citations: [], responseKind: "ERROR",
      }]);
    } finally {
      setBusy(false);
      setPhase("");
    }
  };

  /** Perform a response action: open the questionnaire, confirm a guess, or start a question. */
  const runAction = (action, message) => {
    if (action.id.includes("questionnaire")) {
      onOpenQuestionnaire();
    } else if (action.id === "confirm_intent") {
      // The backend re-checks that this intent was its own suggestion before honoring it.
      submit(null, message.sourceText, { confirmedIntent: action.intent, displayText: "Yes" });
    } else if (action.id === "ask_about_schizophrenia_and_clinical_associations") {
      setInput("What does research say about ");
      inputRef.current?.focus();
    }
  };

  return (
    <div className="chat-layout">
      <aside className="chat-sidebar">
        <span className="eyebrow eyebrow--dark">Optional assessment</span>
        <h2>Research questionnaire</h2>
          <p>Complete this protected questionnaire to find out your symptom severity risk estimate to exhibit psychotic, manic and depressive symptoms characterised by schizophrenia</p>
        <button className="button button--primary" type="button" onClick={onOpenQuestionnaire}>
          Open questionnaire
        </button>
        <div className="privacy-note">
          <strong>Memory-only session</strong>
          <p>Messages and questionnaire answers are not stored by this application.</p>
        </div>
      </aside>

      <main id="main" className="chat-main" aria-labelledby="chat-title">
        <header className="chat-hero">
          <span className="eyebrow">Enlighten about mental health with grounded explanation and evaluation</span>
          <h1 id="chat-title">Bodhica</h1>
          <p>Research demonstration only—not diagnosis, medical advice, or emergency support.</p>
        </header>

        <div className="suggestion-row" aria-label="Example research questions">
          {suggestedQuestions.map((question) => (
            <button key={question} type="button" disabled={busy || !token}
              onClick={(event) => submit(event, question)}>{question}</button>
          ))}
        </div>

        <section className="chat-thread" aria-live="polite" ref={threadRef}>
          {messages.map((message, index) => (
            <article className={`chat-message chat-message--${message.role}`} key={`${message.role}-${index}`} role={message.responseKind === "ERROR" ? "alert" : undefined}>
              <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
              {message.responseKind === "GENERAL_EDUCATION" && (
                <small>General knowledge · no corpus citations</small>
              )}
              <p>{message.text}</p>
              {message.actions?.length > 0 && (
                <div className="chat-actions">
                  {message.actions.map((action) => (
                    <button key={action.id} className="button button--secondary" type="button"
                      disabled={action.id === "confirm_intent" && (busy || !token)}
                      onClick={() => runAction(action, message)}>
                      {action.id === "launch_research_questionnaire_router" ? "Open questionnaire" : action.label}
                    </button>
                  ))}
                </div>
              )}
              {message.citations?.map((citation) => (
                <details className="evidence-card" key={citation.citation_id}>
                  <summary>{citation.citation_id} · PMID {citation.pmid}</summary>
                  <p>{citation.title}</p>
                  <blockquote>{citation.exact_matched_text}</blockquote>
                </details>
              ))}
              {message.limitation && ["NO_ELIGIBLE_EVIDENCE", "RETRIEVAL_UNAVAILABLE"].includes(
                message.responseKind,
              ) && <small>{message.limitation}</small>}
            </article>
          ))}
          {phase && <div className="chat-status" role="status">{phase}</div>}
          {sessionError && (
            <div className="validation-summary" role="alert">
              <strong>Private session unavailable</strong>
              <span>{sessionError}</span>
              <button className="button button--secondary" type="button" onClick={onReset}>
                Reconnect private session
              </button>
            </div>
          )}
          {!token && !sessionError && <div className="chat-status">Connecting private session…</div>}
        </section>

        <form className="chat-composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="chat-input">Message the assistant</label>
          <textarea id="chat-input" ref={inputRef} value={input} maxLength="500" rows="2"
            placeholder="Ask a question or start a conversation…"
            onChange={(event) => setInput(event.target.value)} disabled={busy || !token} />
          <button className="button button--primary" type="submit"
            disabled={busy || !token || !input.trim()}>Send</button>
          <button className="button button--quiet" type="button" onClick={onReset}>Reset session</button>
        </form>
      </main>
    </div>
  );
}
