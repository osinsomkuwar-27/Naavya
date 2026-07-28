import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Send, Mic, Paperclip, X } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { ChatBubble, TypingBubble } from "@/components/chat-bubble";
import { useAssessment, type ChatMessage } from "@/lib/assessment-context";

export const Route = createFileRoute("/assessment/chat")({
  head: () => ({
    meta: [{ title: "Conversation — Naavya" }, { name: "description", content: "Answer a few short questions about your baby's symptoms." }],
  }),
  component: ChatPage,
});

function ChatPage() {
  const { draft, startDraft, appendUser, finalize } = useAssessment();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"gathering" | "finishing">("gathering");

  // Bootstrap a draft if user landed here directly (text-first flow)
  useEffect(() => {
    if (!draft) {
      // no initial description — we'll wait for their first typed message
    }
  }, [draft]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [draft?.messages.length, typing]);

   useEffect(() => {
    if (draft?.isClassified && phase !== "finishing") {
      setPhase("finishing");
      const t = setTimeout(() => navigate({ to: "/assessment/processing" }), 800);
      return () => clearTimeout(t);
    }
  }, [draft?.isClassified, navigate]);

  const messages: ChatMessage[] = draft?.messages ?? [];

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setInput("");
    if (!draft) {
      startDraft("text", trimmed);
      return;
    }
    setTyping(true);
    const { done } = await appendUser(trimmed);
    setTyping(false);
    if (done) {
      setPhase("finishing");
      try {
        await finalize();
        setTimeout(() => navigate({ to: "/assessment/result" }), 600);
      } catch (err) {
        console.error("Failed to finalize chat assessment:", err);
      }
    }
  };

  const lastBot = [...messages].reverse().find((m) => m.role === "bot");
  const chips = lastBot?.quickReplies;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />

      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-4 md:px-6">
        {/* Status pill */}
        <div className="flex items-center justify-between py-4">
          <Link to="/assessment" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" /> End
          </Link>
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${phase === "gathering" ? "bg-primary animate-pulse" : "bg-success"}`} />
            {phase === "gathering"
              ? "A couple more questions to be sure"
              : "Got it — checking this now"}
          </span>
        </div>

        {/* Thread */}
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto py-4">
          {!draft && (
            <div className="rounded-3xl border border-border bg-surface p-5 text-sm text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">Tell us what's happening</p>
              <p>
                In your own words, describe your baby's symptoms. Don't worry about
                being technical — we'll ask any follow-ups we need.
              </p>
            </div>
          )}
          {messages.map((m) => (
            <ChatBubble key={m.id} msg={m} />
          ))}
          {typing && <TypingBubble />}
        </div>

        {/* Quick replies */}
        {chips && !typing && phase === "gathering" && (
          <div className="flex flex-wrap gap-2 pb-3">
            {chips.map((c) => (
              <button
                key={c}
                onClick={() => send(c)}
                className="rounded-full border border-primary/30 bg-primary-soft px-4 py-2 text-sm font-medium text-primary transition hover:bg-primary hover:text-primary-foreground"
              >
                {c}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="sticky bottom-0 mb-6 flex items-end gap-2 rounded-full border border-border bg-surface p-2 shadow-[var(--shadow-card)]"
        >
          <button
            type="button"
            disabled
            aria-label="Attach (coming soon)"
            className="flex h-10 w-10 flex-none items-center justify-center rounded-full text-muted-foreground/50"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            placeholder={draft ? "Type your reply…" : "Describe what's happening…"}
            className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted-foreground"
          />
          <Link
            to="/assessment/voice"
            aria-label="Answer by voice"
            className="flex h-10 w-10 flex-none items-center justify-center rounded-full text-primary hover:bg-primary-soft"
          >
            <Mic className="h-4 w-4" />
          </Link>
          <button
            type="submit"
            disabled={!input.trim() || phase === "finishing"}
            aria-label="Send"
            className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[var(--shadow-soft)] transition hover:opacity-95 disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
