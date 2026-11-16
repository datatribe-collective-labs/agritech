"use client"; // This part runs in the browser, because it reacts to taps and typing.

// React tools for state, effects and references.
import { FormEvent, useEffect, useRef, useState } from "react";
// Lets us draw the chat directly in the page body, outside the animated page wrapper.
import { createPortal } from "react-dom";
// The assistant client and its helpers.
import {
  AI_NOTICE, AssistantError, MAX_QUESTION_CHARS, Message, askQuestion, endSession, failureMessage, startSession, suggestionsFor,
} from "@/lib/assistant";

// What the page tells us: the city, the crop (if any) and a short label for the panel title.
type Props = { city: string; species?: string; about: string };

// The "Let's discuss more" button and the chat panel that opens next to the result.
export function AskAssistant({ city, species, about }: Props) {
  // Is the panel open?
  const [open, setOpen] = useState(false);
  // The chat id once the chat has started (kept in state and in a ref for cleanup).
  const [sessionId, setSessionId] = useState<string | null>(null);
  // The conversation so far.
  const [messages, setMessages] = useState<Message[]>([]);
  // Questions already asked, so tappable ones are not repeated.
  const [asked, setAsked] = useState<string[]>([]);
  // The text in the typing box.
  const [draft, setDraft] = useState("");
  // True while we wait for the assistant.
  const [busy, setBusy] = useState(false);
  // A friendly error shown under the messages, if something went wrong.
  const [problem, setProblem] = useState<string | null>(null);
  // Always holds the latest chat id, so leaving the page can delete it.
  const sessionRef = useRef<string | null>(null);
  // Points at the scrolling message list, so we can scroll only that list (not the whole page).
  const listRef = useRef<HTMLDivElement | null>(null);
  // True once the page has loaded in the browser (the portal needs the browser's document).
  const [mounted, setMounted] = useState(false);

  // The subject of the chat, as the client library expects it.
  const subject = { city, species };

  // Note that we are now running in the browser.
  useEffect(() => {
    // From now on the portal may be drawn.
    setMounted(true);
  }, []);

  // Keep the ref in step with the state.
  useEffect(() => {
    // Copy the latest id.
    sessionRef.current = sessionId;
  }, [sessionId]);

  // When the farmer leaves the page, delete the chat on the server (best effort).
  useEffect(() => {
    // Return the cleanup that runs when the page closes.
    return () => {
      // Only delete when a chat was started.
      if (sessionRef.current) void endSession(sessionRef.current);
    };
  }, []);

  // Close the panel with the Escape key.
  useEffect(() => {
    // Do nothing while the panel is closed.
    if (!open) return;
    // Close when Escape is pressed.
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    // Listen for key presses.
    window.addEventListener("keydown", onKey);
    // Stop listening when the panel closes.
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Scroll the message list to the newest message whenever the conversation changes.
  useEffect(() => {
    // The list element, if it is on screen.
    const list = listRef.current;
    // Move to the bottom of the list only; the page behind stays where it is.
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, busy, problem, open]);

  // Make sure a chat exists, starting one if needed, and return its id.
  async function ensureSession(): Promise<string> {
    // Reuse the chat we already have.
    if (sessionRef.current) return sessionRef.current;
    // Ask the server to open a chat pinned to this result.
    const started = await startSession(subject);
    // Remember the id.
    sessionRef.current = started.session_id;
    // Update the screen state too.
    setSessionId(started.session_id);
    // Hand the id back.
    return started.session_id;
  }

  // Send one question (typed or tapped) and show the answer.
  async function ask(question: string) {
    // Remove stray spaces.
    const text = question.trim();
    // Ignore empty questions and double sends.
    if (!text || busy) return;
    // Show the farmer's question straight away.
    setMessages((m) => [...m, { role: "farmer", text }]);
    // Remember it, so a tappable copy is not offered again.
    setAsked((a) => [...a, text]);
    // Clear the typing box.
    setDraft("");
    // Hide an old error.
    setProblem(null);
    // Show the "thinking" state.
    setBusy(true);
    // Try the whole round trip.
    try {
      // Open the chat if this is the first question.
      const id = await ensureSession();
      // Ask the assistant.
      const reply = await askQuestion(id, text);
      // Show its answer.
      setMessages((m) => [...m, { role: "assistant", text: reply.answer }]);
    } catch (error) {
      // Pick the kind of failure, defaulting to "unavailable".
      const kind = error instanceof AssistantError ? error.kind : "unavailable";
      // A finished chat is forgotten, so the next question starts a fresh one.
      if (kind === "gone") {
        // Forget the old id.
        sessionRef.current = null;
        // Update the screen state too.
        setSessionId(null);
      }
      // Show the friendly message.
      setProblem(failureMessage(kind));
    } finally {
      // Stop the "thinking" state.
      setBusy(false);
    }
  }

  // Handle the typing box being submitted.
  function onSubmit(event: FormEvent) {
    // Stop the browser from reloading the page.
    event.preventDefault();
    // Send what was typed.
    void ask(draft);
  }

  // Delete the chat and start clean (the farmer's "forget this" button).
  async function forget() {
    // Take the id we hold.
    const id = sessionRef.current;
    // Forget it locally first.
    sessionRef.current = null;
    // Update the screen state too.
    setSessionId(null);
    // Clear the conversation and the question history.
    setMessages([]);
    setAsked([]);
    // Clear any error.
    setProblem(null);
    // Tell the server to delete it.
    if (id) await endSession(id);
  }

  // The tappable questions that are still unused.
  const suggestions = suggestionsFor(subject, asked);

  // Nothing to draw until we are in the browser.
  if (!mounted) return null;

  // Draw the button and, when open, the panel, directly inside the page body so "fixed" means the screen.
  return createPortal(
    <>
      {/* The button that opens the chat. Hidden while the panel is open. */}
      {!open && (
        <button type="button" className="assistant-open" onClick={() => setOpen(true)}>
          Let&apos;s discuss more
        </button>
      )}

      {/* The chat panel. */}
      {open && (
        <section className="assistant-panel" role="dialog" aria-label={`Chat about ${about}`}>
          {/* Title bar with the close button. */}
          <header className="assistant-head">
            <div>
              {/* What this chat is about. */}
              <h2>Let&apos;s discuss more</h2>
              <p className="muted small">{about}</p>
            </div>
            {/* Closing keeps the chat, so reopening continues where it stopped. */}
            <button type="button" className="assistant-close" onClick={() => setOpen(false)} aria-label="Close chat">
              ×
            </button>
          </header>

          {/* Honest notice: this is an AI. */}
          <p className="assistant-notice small">{AI_NOTICE}</p>

          {/* The conversation. aria-live makes screen readers announce new answers. */}
          <div className="assistant-messages" aria-live="polite" ref={listRef}>
            {/* A welcome line before the first question. */}
            {messages.length === 0 && (
              <p className="muted">Pick a question below, or type your own. I explain the results shown on this page.</p>
            )}
            {/* Each message, styled by who wrote it. */}
            {messages.map((m, i) => (
              <p key={i} className={`assistant-msg ${m.role}`}>
                {/* Screen readers hear who is speaking. */}
                <span className="sr-only">{m.role === "farmer" ? "You: " : "Assistant: "}</span>
                {m.text}
              </p>
            ))}
            {/* Shown while we wait for the answer. */}
            {busy && <p className="assistant-msg assistant muted">Thinking…</p>}
            {/* Shown when something went wrong. */}
            {problem && <p className="assistant-problem" role="alert">{problem}</p>}
          </div>

          {/* Tappable questions, so nobody has to type. */}
          {suggestions.length > 0 && (
            <ul className="assistant-chips" aria-label="Suggested questions">
              {suggestions.map((q) => (
                <li key={q}>
                  <button type="button" className="assistant-chip" disabled={busy} onClick={() => void ask(q)}>{q}</button>
                </li>
              ))}
            </ul>
          )}

          {/* Typing is always possible. */}
          <form className="assistant-form" onSubmit={onSubmit}>
            {/* A visible label would repeat the title, so it is for screen readers only. */}
            <label className="sr-only" htmlFor="assistant-input">Type your question</label>
            <input
              id="assistant-input"
              className="assistant-input"
              type="text"
              value={draft}
              maxLength={MAX_QUESTION_CHARS}
              placeholder="Or type your own question"
              autoComplete="off"
              onChange={(e) => setDraft(e.target.value)}
            />
            {/* Send is off while waiting or when the box is empty. */}
            <button type="submit" className="button small" disabled={busy || !draft.trim()}>Send</button>
          </form>

          {/* Let the farmer delete the chat. */}
          {messages.length > 0 && (
            <button type="button" className="assistant-forget" onClick={() => void forget()}>Delete this chat</button>
          )}
        </section>
      )}
    </>,
    document.body,
  );
}
