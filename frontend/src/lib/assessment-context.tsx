import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { submitAssessment, mapRiskLevel } from "./api";

export type Risk = "low" | "medium" | "high";

export interface ChatMessage {
  id: string;
  role: "bot" | "user";
  text: string;
  quickReplies?: string[];
  timestamp: number;
}

export interface Assessment {
  id: string;
  createdAt: number;
  method: "voice" | "text";
  symptoms: string[];
  messages: ChatMessage[];
  risk: Risk;
  summary: string;
  explanation: string;
  nextSteps: string[];
}

export interface User {
  name: string;
  email: string;
  role: "caregiver" | "asha";
}

interface DraftAssessment {
  id: string;
  method: "voice" | "text";
  messages: ChatMessage[];
  turnCount: number;
}

interface Ctx {
  user: User | null;
  history: Assessment[];
  draft: DraftAssessment | null;
  lastResult: Assessment | null;
  login: (u: User) => void;
  logout: () => void;
  startDraft: (method: "voice" | "text", initial: string) => DraftAssessment;
  appendUser: (text: string) => { done: boolean };
  finalize: () => Assessment;
  clearDraft: () => void;
  getById: (id: string) => Assessment | undefined;
}

const AssessmentContext = createContext<Ctx | null>(null);

const uid = () => Math.random().toString(36).slice(2, 10);

const seedHistory = (): Assessment[] => [
  {
    id: "seed-1",
    createdAt: Date.now() - 1000 * 60 * 60 * 26,
    method: "voice",
    symptoms: ["Mild fever for 1 day", "Feeding normally", "Alert and active"],
    messages: [],
    risk: "low",
    summary: "Continue home care",
    explanation:
      "Your baby's symptoms are mild and they are feeding and behaving normally. Watch for any change over the next 24 hours.",
    nextSteps: [
      "Keep your baby warm and comfortable.",
      "Continue regular feeding.",
      "Check temperature every few hours.",
      "Start a new assessment if symptoms get worse.",
    ],
  },
  {
    id: "seed-2",
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 4,
    method: "text",
    symptoms: ["Vomiting after feeds", "Fewer wet nappies today"],
    messages: [],
    risk: "medium",
    summary: "Contact ASHA worker",
    explanation:
      "Repeated vomiting and reduced wet nappies can be a sign your baby needs extra attention. Your ASHA worker should review this in person today.",
    nextSteps: [
      "Call your ASHA worker now.",
      "Offer small feeds more often.",
      "Note any new symptoms to share.",
    ],
  },
];

const BOT_QUESTIONS = [
  {
    text: "Thank you for sharing. How long has this been happening?",
    quickReplies: ["A few hours", "Since yesterday", "More than a day"],
  },
  {
    text: "Is your baby feeding normally?",
    quickReplies: ["Yes, normally", "Less than usual", "Not at all"],
  },
  {
    text: "Is your baby alert and responsive when you touch them?",
    quickReplies: ["Yes", "A little sleepy", "Hard to wake"],
  },
];

function classify(messages: ChatMessage[]): {
  risk: Risk;
  summary: string;
  explanation: string;
  nextSteps: string[];
  symptoms: string[];
} {
  const joined = messages
    .filter((m) => m.role === "user")
    .map((m) => m.text.toLowerCase())
    .join(" ");

  const symptoms: string[] = [];
  if (/breath|breathing|chest/.test(joined)) symptoms.push("Difficulty breathing");
  if (/blue|purple|colou?r/.test(joined)) symptoms.push("Skin colour changes");
  if (/fever|hot|temperature/.test(joined)) symptoms.push("Fever reported");
  if (/vomit|throw|spit/.test(joined)) symptoms.push("Vomiting");
  if (/diarr|loose|stool/.test(joined)) symptoms.push("Loose stools");
  if (/feed|milk|nurs/.test(joined)) symptoms.push("Feeding concern");
  if (/sleep|drowsy|wake|unconscious|responsive|hard to wake/.test(joined))
    symptoms.push("Reduced alertness");
  if (!symptoms.length) symptoms.push("General newborn concern reported");

  const high =
    /breath|blue|purple|unconscious|not at all|hard to wake|convuls|seiz|bleed/.test(
      joined,
    );
  const medium =
    /fever|vomit|diarr|less than usual|more than a day|sleepy/.test(joined);

  if (high) {
    return {
      risk: "high",
      summary: "Visit hospital immediately",
      explanation:
        "Based on what you described, your baby needs urgent in-person care. Please go to the nearest facility now — do not wait.",
      nextSteps: [
        "Go to the nearest hospital or facility right now.",
        "Keep your baby warm on the way.",
        "Call ahead if you can so they are ready.",
        "Bring any medicines your baby is already taking.",
      ],
      symptoms,
    };
  }
  if (medium) {
    return {
      risk: "medium",
      summary: "Contact your ASHA worker",
      explanation:
        "Your baby's symptoms need a closer look from your ASHA worker today. They can visit or guide you on the next step.",
      nextSteps: [
        "Call your ASHA worker now.",
        "Keep your baby warm and continue feeding little and often.",
        "Note any new symptoms so you can share them.",
        "If things get worse quickly, go to the nearest facility.",
      ],
      symptoms,
    };
  }
  return {
    risk: "low",
    summary: "Continue home care",
    explanation:
      "What you've described looks mild and your baby seems otherwise well. Watch them closely for the next 24 hours.",
    nextSteps: [
      "Keep your baby warm and comfortable.",
      "Continue regular feeding.",
      "Check temperature and behaviour every few hours.",
      "Start a new assessment if anything changes.",
    ],
    symptoms,
  };
}

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [history, setHistory] = useState<Assessment[]>([]);
  const [draft, setDraft] = useState<DraftAssessment | null>(null);
  const [lastResult, setLastResult] = useState<Assessment | null>(null);

  // Hydrate from localStorage after mount (SSR-safe)
  useEffect(() => {
    try {
      const u = localStorage.getItem("nt.user");
      if (u) setUser(JSON.parse(u));
      const h = localStorage.getItem("nt.history");
      setHistory(h ? JSON.parse(h) : seedHistory());
    } catch {
      setHistory(seedHistory());
    }
  }, []);

  useEffect(() => {
    if (user) localStorage.setItem("nt.user", JSON.stringify(user));
    else localStorage.removeItem("nt.user");
  }, [user]);

  useEffect(() => {
    if (history.length) localStorage.setItem("nt.history", JSON.stringify(history));
  }, [history]);

  const startDraft = useCallback(
    (method: "voice" | "text", initial: string) => {
      const now = Date.now();
      const messages: ChatMessage[] = [
        {
          id: uid(),
          role: "user",
          text: initial,
          timestamp: now,
        },
        {
          id: uid(),
          role: "bot",
          text: BOT_QUESTIONS[0].text,
          quickReplies: BOT_QUESTIONS[0].quickReplies,
          timestamp: now + 1,
        },
      ];
      const d: DraftAssessment = {
        id: uid(),
        method,
        messages,
        turnCount: 1,
      };
      setDraft(d);
      return d;
    },
    [],
  );

  const appendUser = useCallback(
    (text: string) => {
      let done = false;
      setDraft((prev) => {
        if (!prev) return prev;
        const messages: ChatMessage[] = [
          ...prev.messages,
          { id: uid(), role: "user", text, timestamp: Date.now() },
        ];
        const nextTurn = prev.turnCount + 1;
        if (nextTurn < BOT_QUESTIONS.length) {
          const q = BOT_QUESTIONS[nextTurn];
          messages.push({
            id: uid(),
            role: "bot",
            text: q.text,
            quickReplies: q.quickReplies,
            timestamp: Date.now() + 1,
          });
        } else {
          messages.push({
            id: uid(),
            role: "bot",
            text: "Got it — checking this now.",
            timestamp: Date.now() + 1,
          });
          done = true;
        }
        return { ...prev, messages, turnCount: nextTurn };
      });
      return { done };
    },
    [],
  );

  const finalize = useCallback((): Assessment => {
    if (!draft) throw new Error("No draft");

    // Collect all user messages into a single transcript for the backend.
    const transcript = draft.messages
      .filter((m) => m.role === "user")
      .map((m) => m.text)
      .join(" ");

    // Return a placeholder Assessment immediately so the UI can navigate;
    // we kick off the real backend call asynchronously and update history
    // when it resolves.
    const fallbackResult = classify(draft.messages);
    const assessment: Assessment = {
      id: draft.id,
      createdAt: Date.now(),
      method: draft.method,
      messages: draft.messages,
      ...fallbackResult,
    };

    // Kick off real backend assessment (non-blocking — UI already navigating)
    submitAssessment({ transcript, language: "en", conversation_id: draft.id })
      .then((res) => {
        const risk = mapRiskLevel(res.risk_level);
        const backendAssessment: Assessment = {
          id: res.conversation_id,
          createdAt: Date.now(),
          method: draft.method,
          messages: draft.messages,
          risk,
          summary: res.recommendation ?? fallbackResult.summary,
          explanation: res.recommendation ?? fallbackResult.explanation,
          nextSteps: res.next_steps.length ? res.next_steps : fallbackResult.nextSteps,
          symptoms: fallbackResult.symptoms, // derived from messages, same either way
        };
        // Replace the optimistic entry with the real backend result
        setHistory((h) =>
          h.map((a) => (a.id === draft.id || a.id === res.conversation_id ? backendAssessment : a))
        );
        setLastResult(backendAssessment);
      })
      .catch((err) => {
        console.warn(
          "[Naavya] Backend /assess call failed — using local classification fallback.",
          err,
        );
        // fallback already set; nothing more to do
      });

    setHistory((h) => [assessment, ...h]);
    setLastResult(assessment);
    setDraft(null);
    return assessment;
  }, [draft]);

  const clearDraft = useCallback(() => setDraft(null), []);

  const getById = useCallback(
    (id: string) => history.find((a) => a.id === id),
    [history],
  );

  const value = useMemo<Ctx>(
    () => ({
      user,
      history,
      draft,
      lastResult,
      login: (u) => setUser(u),
      logout: () => setUser(null),
      startDraft,
      appendUser,
      finalize,
      clearDraft,
      getById,
    }),
    [user, history, draft, lastResult, startDraft, appendUser, finalize, clearDraft, getById],
  );

  return <AssessmentContext.Provider value={value}>{children}</AssessmentContext.Provider>;
}

export function useAssessment() {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error("useAssessment must be used inside AssessmentProvider");
  return ctx;
}
