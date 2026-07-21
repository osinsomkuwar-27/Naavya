import type { ChatMessage } from "@/lib/assessment-context";

export function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`nt-fade-up flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-3xl px-4 py-3 text-[15px] leading-relaxed shadow-[var(--shadow-soft)] ${
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md bg-surface text-foreground"
        }`}
      >
        {msg.text}
      </div>
    </div>
  );
}

export function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 rounded-3xl rounded-bl-md bg-surface px-5 py-4 shadow-[var(--shadow-soft)]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-muted-foreground/60"
            style={{ animation: `nt-dot 1.2s infinite ${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}
