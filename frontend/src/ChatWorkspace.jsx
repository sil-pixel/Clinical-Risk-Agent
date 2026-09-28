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

function parseEvent(block) {
  let type = "message";
  let data = null;
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7);
    if (line.startsWith("data: ")) data = JSON.parse(line.slice(6));
  }
  return data ? { type, data } : null;
}

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

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages, phase]);

  const submit = async (event, suppliedText) => {
    event?.preventDefault();
    const text = (suppliedText ?? input).trim();
    if (!text || !token || busy) return;
    setInput("");
    setBusy(true);
    setPhase("Starting protected checks…");
    setMessages((current) => [...current, { role: "user", text, citations: [] }]);
    let assistant = null;
    try {
      const response = await fetch(`${API_BASE}/v1/messages:stream`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ kind: "free_text", text }),
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
            throw new Error(eventData.data.message || "The request failed safely.");
          }
        }
        if (done) break;
      }
    } catch (error) {
      setMessages((current) => [...current, {
        role: "assistant", text: error.message, citations: [], responseKind: "ERROR",
      }]);
    } finally {
      setBusy(false);
      setPhase("");
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
            <article className={`chat-message chat-message--${message.role}`} key={`${message.role}-${index}`}>
              <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
              {message.responseKind === "GENERAL_EDUCATION" && (
                <small>General knowledge · no corpus citations</small>
              )}
              <p>{message.text}</p>
              {message.actions?.some((action) => action.id.includes("questionnaire")) && (
                <button className="button button--secondary" type="button" onClick={onOpenQuestionnaire}>
                  Open questionnaire
                </button>
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
          <textarea id="chat-input" value={input} maxLength="500" rows="2"
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
