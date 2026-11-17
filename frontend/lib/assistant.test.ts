// Tests for the assistant client: tappable questions, and how failures are turned into friendly messages.

// Test tools.
import { afterEach, describe, expect, it, vi } from "vitest";
// The code under test.
import { AssistantError, FEEDBACK_REASONS, askQuestion, failureMessage, feedbackHint, sendFeedback, startSession, suggestionsFor } from "./assistant";

// Put the real fetch back after every test.
afterEach(() => vi.unstubAllGlobals());

// Pretend the server answered with a status and some JSON.
function stubFetch(status: number, body: unknown = {}) {
  // Replace fetch with a fake that returns that answer.
  const fake = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
  // Make the fake the global fetch.
  vi.stubGlobal("fetch", fake);
  // Give the fake back so tests can look at the calls.
  return fake;
}

// Tests about the tappable questions.
describe("tappable questions", () => {
  // A city page and a crop page start with different questions.
  it("differ for a city and for a crop", () => {
    // The city list is about planting choices.
    expect(suggestionsFor({ city: "Lagos" }, [])[0]).toContain("plant first");
    // The crop list is about the crop's score.
    expect(suggestionsFor({ city: "Lagos", species: "Zea mays" }, [])[0]).toContain("score");
  });

  // Questions already asked are not offered again, and the list stays short.
  it("skip questions already asked and never show more than four", () => {
    // Ask the first crop question.
    const left = suggestionsFor({ city: "Lagos", species: "Zea mays" }, ["why does it score like this?"]);
    // It no longer appears.
    expect(left).not.toContain("Why does it score like this?");
    // At most four are shown.
    expect(left.length).toBeLessThanOrEqual(4);
    // Something is always left to tap at the start.
    expect(suggestionsFor({ city: "Lagos" }, []).length).toBe(4);
  });
});

// Tests about talking to the server.
describe("assistant calls", () => {
  // Starting a chat sends only the names.
  it("start a chat with only the city and crop names", async () => {
    // The server replies with a chat id.
    const fake = stubFetch(200, { session_id: "abc", notice: "AI" });
    // Start the chat.
    const started = await startSession({ city: "Lagos", species: "Zea mays" });
    // The id comes back.
    expect(started.session_id).toBe("abc");
    // The request body holds just the two names.
    expect(JSON.parse(fake.mock.calls[0][1].body)).toEqual({ city: "Lagos", species: "Zea mays" });
  });

  // Too many questions is reported as "busy".
  it("report 429 as busy, 404 as gone and other errors as unavailable", async () => {
    // Rate limited.
    stubFetch(429);
    await expect(askQuestion("abc", "hi")).rejects.toMatchObject({ kind: "busy" });
    // Chat expired.
    stubFetch(404);
    await expect(askQuestion("abc", "hi")).rejects.toMatchObject({ kind: "gone" });
    // Server trouble.
    stubFetch(500);
    await expect(askQuestion("abc", "hi")).rejects.toMatchObject({ kind: "unavailable" });
  });

  // No connection at all is also "unavailable".
  it("report a lost connection as unavailable", async () => {
    // Make fetch fail the way a dead network does.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    // The error is our own kind.
    const error = await askQuestion("abc", "hi").catch((e) => e);
    // It is an AssistantError.
    expect(error).toBeInstanceOf(AssistantError);
    // And it is the unavailable kind.
    expect(error.kind).toBe("unavailable");
  });

  // Every failure kind has a sentence for the farmer.
  it("have a friendly sentence for every failure", () => {
    // Each message is non-empty and never shows a status code.
    for (const kind of ["busy", "gone", "unavailable"] as const) {
      // Not empty.
      expect(failureMessage(kind).length).toBeGreaterThan(10);
      // No raw numbers like 429.
      expect(failureMessage(kind)).not.toMatch(/\d{3}/);
    }
  });
});

// Tests about rating answers.
describe("rating answers", () => {
  // The rating sends only ids and fixed choices, never any text from the page.
  it("sends only the chat id, answer number, rating and a tapped reason", async () => {
    // The server says it saved the rating.
    const fake = stubFetch(200, { saved: true });
    // Rate the first answer down with a reason.
    await sendFeedback("abc", 0, "down", "unclear");
    // The request went to the feedback address.
    expect(fake.mock.calls[0][0]).toContain("/feedback");
    // The body holds just those four values.
    expect(JSON.parse(fake.mock.calls[0][1].body)).toEqual({ session_id: "abc", turn: 0, rating: "down", reason: "unclear" });
  });

  // A failed rating is reported like any other failure so the page can ignore it.
  it("reports a missing chat as gone", async () => {
    // The chat no longer exists.
    stubFetch(404);
    // The error says so.
    await expect(sendFeedback("abc", 0, "up")).rejects.toMatchObject({ kind: "gone" });
  });

  // Rating must never read like the end of the conversation.
  it("always tells the farmer the chat is still open and rating is optional", () => {
    // Before rating it says optional and keep asking.
    expect(feedbackHint(undefined)).toMatch(/optional/i);
    // After either rating it says the chat is still open.
    expect(feedbackHint("up")).toMatch(/still open/i);
    expect(feedbackHint("down")).toMatch(/still open/i);
  });

  // The reasons are fixed choices the server accepts.
  it("offers only the reasons the server accepts", () => {
    // The same four values as the server.
    expect(FEEDBACK_REASONS.map((r) => r.value).sort()).toEqual(["off_topic", "other", "unclear", "wrong"]);
  });
});
