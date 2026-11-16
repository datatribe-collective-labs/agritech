// Talks to the AI assistant from the browser. The assistant only explains results the site already shows.

// Where the assistant lives (can be changed at build time; the default is the same server as the API).
export const ASSISTANT_URL = (process.env.NEXT_PUBLIC_ASSISTANT_URL ?? "https://94-237-15-238.sslip.io/assistant").replace(/\/$/, "");

// Always shown to the farmer, even before the server replies (people must know they talk to an AI).
export const AI_NOTICE = "You are chatting with an AI helper. It only explains the app's results and can make mistakes.";

// The longest question the server accepts (the text box stops typing at this length).
export const MAX_QUESTION_CHARS = 500;

// What the chat is about: a city, or a crop inside a city.
export type Subject = { city: string; species?: string };

// One line in the conversation, written by the farmer or by the assistant.
export type Message = { role: "farmer" | "assistant"; text: string };

// What the server returns when a chat starts.
export type Started = { session_id: string; notice: string };

// What the server returns for a question.
export type Reply = { answer: string; refused: boolean };

// The three ways a call can fail, in words the page can turn into a friendly message.
export type FailureKind = "busy" | "gone" | "unavailable";

// An error that carries the kind of failure.
export class AssistantError extends Error {
  // Remember the kind so the page can choose the right message.
  constructor(public kind: FailureKind, message: string) {
    // Pass the message on to the normal Error.
    super(message);
  }
}

// Turn a failed web response into our own error kind.
function failure(status: number): AssistantError {
  // 429 means the farmer is asking too fast.
  if (status === 429) return new AssistantError("busy", "Too many questions");
  // 404 means the chat no longer exists (it expired or was deleted).
  if (status === 404) return new AssistantError("gone", "Chat not found");
  // Anything else means the assistant cannot help right now.
  return new AssistantError("unavailable", `Assistant answered ${status}`);
}

// Send one request and return the JSON, or throw an AssistantError.
async function call<T>(path: string, init: RequestInit): Promise<T> {
  // The web response, once it arrives.
  let response: Response;
  // Try to reach the server.
  try {
    // Ask the assistant server.
    response = await fetch(ASSISTANT_URL + path, init);
  } catch {
    // No connection at all.
    throw new AssistantError("unavailable", "The assistant could not be reached");
  }
  // Turn error statuses into our own errors.
  if (!response.ok) throw failure(response.status);
  // Read the JSON body.
  return (await response.json()) as T;
}

// Headers for requests that send JSON.
const JSON_HEADERS = { "Content-Type": "application/json" };

// Open a chat pinned to the result the farmer is looking at.
export function startSession(subject: Subject): Promise<Started> {
  // Send only the names; the server rebuilds the facts itself.
  return call<Started>("/sessions", {
    // Creating something new is a POST.
    method: "POST",
    // The body is JSON.
    headers: JSON_HEADERS,
    // City always, crop only when there is one.
    body: JSON.stringify({ city: subject.city, species: subject.species ?? "" }),
  });
}

// Ask one question inside an open chat.
export function askQuestion(sessionId: string, question: string): Promise<Reply> {
  // Post the question with the chat id.
  return call<Reply>("/chat", {
    // Asking is a POST.
    method: "POST",
    // The body is JSON.
    headers: JSON_HEADERS,
    // Chat id and the question text.
    body: JSON.stringify({ session_id: sessionId, question }),
  });
}

// Delete a chat (the farmer's "forget this" button, also used when leaving the page).
export async function endSession(sessionId: string): Promise<void> {
  // Ignore failures: unused chats expire on the server anyway.
  try {
    // keepalive lets the request finish even while the page is closing.
    await fetch(`${ASSISTANT_URL}/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE", keepalive: true });
  } catch {
    // Nothing to do; the server forgets the chat after a while.
  }
}

// Tappable questions for a city page.
const CITY_QUESTIONS = [
  "What should I plant first here?",
  "Which months are best for planting?",
  "Why is the top crop ranked first?",
  "How reliable is this ranking?",
];

// Tappable questions for a crop page.
const CROP_QUESTIONS = [
  "Why does it score like this?",
  "What grows well with it?",
  "Which months suit it?",
  "How reliable is this score?",
];

// Offered at the end once the main questions are used.
const EXTRA_QUESTIONS = ["Can you explain that in simpler words?"];

// How many tappable questions to show at once.
const MAX_SUGGESTIONS = 4;

// Pick the tappable questions to show, skipping ones already asked.
export function suggestionsFor(subject: Subject, asked: string[]): string[] {
  // A crop page and a city page start with different questions.
  const base = subject.species ? CROP_QUESTIONS : CITY_QUESTIONS;
  // Questions already used, ignoring capital letters.
  const used = new Set(asked.map((q) => q.toLowerCase()));
  // Keep only questions not asked yet, main ones first.
  const fresh = [...base, ...EXTRA_QUESTIONS].filter((q) => !used.has(q.toLowerCase()));
  // Show only a few so the panel stays calm.
  return fresh.slice(0, MAX_SUGGESTIONS);
}

// The friendly sentence to show for each kind of failure.
export function failureMessage(kind: FailureKind): string {
  // Asking too fast.
  if (kind === "busy") return "You are asking quickly. Please wait a moment and try again.";
  // The chat ended, so the next question starts a new one.
  if (kind === "gone") return "This chat ended. Ask again to start a new one.";
  // Everything else.
  return "The assistant is not available right now. The results on this page are still correct.";
}
