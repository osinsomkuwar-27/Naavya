import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { submitAssessment, submitVoiceAssessment, mapRiskLevel, type AssessResponse } from "./api";

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
  transcript: string;
  audioUrl: string | null;
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
  isBackendProcessing: boolean;
  isClassified: boolean;
  lastResponse?: AssessResponse;
}

interface Ctx {
  user: User | null;
  history: Assessment[];
  draft: DraftAssessment | null;
  lastResult: Assessment | null;
  login: (u: User) => void;
  logout: () => void;
  startDraft: (method: "voice" | "text", initial: string) => DraftAssessment;
  startVoiceDraft: (audioBlob: Blob) => Promise<{ draft: DraftAssessment; isDone: boolean }>;
  appendUser: (text: string) => Promise<{ done: boolean; pendingQuestion?: string }>;
  appendVoiceUser: (audioBlob: Blob) => Promise<{ done: boolean; pendingQuestion?: string; audioUrl?: string | null }>;
  finalize: (overrideDraft?: DraftAssessment) => Promise<Assessment>;
  clearDraft: () => void;
  getById: (id: string) => Assessment | undefined;
}

const AssessmentContext = createContext<Ctx | null>(null);

const uid = () => Math.random().toString(36).slice(2, 10);

const seedHistory = (): Assessment[] => [];



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
      const draftId = uid();
      const now = Date.now();
      const messages: ChatMessage[] = [
        {
          id: uid(),
          role: "user",
          text: initial,
          timestamp: now,
        },
      ];

      const d: DraftAssessment = {
        id: draftId,
        method,
        messages,
        turnCount: 1,
        isBackendProcessing: true,
        isClassified: false,
      };
      setDraft(d);

      // Kick off backend /assess for first message
      submitAssessment({
        transcript: initial,
        conversation_id: draftId,
        language: "en",
        source: method === "voice" ? "web_mic" : "web_text",
      })
        .then((res) => {
          setDraft((prev) => {
            if (!prev || prev.id !== draftId) return prev;
            const updatedMsgs = [...prev.messages];

            if (res.status === "disambiguating" && res.pending_question) {
              updatedMsgs.push({
                id: uid(),
                role: "bot",
                text: res.pending_question,
                timestamp: Date.now(),
              });
            } else {
              updatedMsgs.push({
                id: uid(),
                role: "bot",
                text: "Got it — checking this now.",
                timestamp: Date.now(),
              });
            }

            return {
              ...prev,
              messages: updatedMsgs,
              isBackendProcessing: false,
              isClassified: res.status !== "disambiguating",
              lastResponse: res,
            };
          });
        })
        .catch((err) => {
          console.error("[Naavya] Initial /assess backend call failed:", err);
          const errorMsg = err instanceof Error ? err.message : "Backend service error";
          setDraft((prev) => {
            if (!prev || prev.id !== draftId) return prev;
            return {
              ...prev,
              messages: [
                ...prev.messages,
                {
                  id: uid(),
                  role: "bot",
                  text: `⚠️ Backend Error: ${errorMsg}. Unable to connect to triage pipeline. Please check backend service.`,
                  timestamp: Date.now(),
                },
              ],
              isBackendProcessing: false,
            };
          });
        });

      return d;
    },
    [],
  );

  const startVoiceDraft = useCallback(
    async (audioBlob: Blob) => {
      const draftId = uid();
      const now = Date.now();

      const d: DraftAssessment = {
        id: draftId,
        method: "voice",
        messages: [],
        turnCount: 1,
        isBackendProcessing: true,
        isClassified: false,
      };
      setDraft(d);

      try {
        const res = await submitVoiceAssessment(audioBlob, draftId, "en", "web_mic");
        const messages: ChatMessage[] = [];

        // Prefer the real Whisper transcript from the backend; fall back only if it's genuinely empty
        const userText =
          res.transcript && res.transcript.trim().length > 0
            ? res.transcript
            : "(Voice note submitted — no transcript available)";

        messages.push({
          id: uid(),
          role: "user",
          text: userText,
          timestamp: now,
        });

        let isDone = false;
        if (res.status === "disambiguating" && res.pending_question) {
          messages.push({
            id: uid(),
            role: "bot",
            text: res.pending_question,
            timestamp: Date.now(),
          });
        } else {
          isDone = true;
          messages.push({
            id: uid(),
            role: "bot",
            text: res.recommendation || "Got it — checking this now.",
            timestamp: Date.now(),
          });
        }

        const updatedDraft: DraftAssessment = {
          ...d,
          messages,
          isBackendProcessing: false,
          isClassified: res.status === "classified",
          lastResponse: res,
        };

        // Guard against a slower, earlier request resolving after a newer
        // draft has already replaced it in context state -- only apply this
        // update if this draft is still the active one.
        setDraft((prev) => (prev && prev.id === draftId ? updatedDraft : prev));
        return { draft: updatedDraft, isDone };

      } catch (err) {
        console.error("[Naavya] Voice backend assessment failed:", err);
        const errorMsg = err instanceof Error ? err.message : "Backend service error";
        const fallbackDraft: DraftAssessment = {
          ...d,
          messages: [
            {
              id: uid(),
              role: "user",
              text: "(Voice note)",
              timestamp: now,
            },
            {
              id: uid(),
              role: "bot",
              text: `⚠️ Voice Backend Error: ${errorMsg}. Could not process voice recording.`,
              timestamp: Date.now(),
            },
          ],
          isBackendProcessing: false,
        };
        setDraft((prev) => (prev && prev.id === draftId ? fallbackDraft : prev));
        return { draft: fallbackDraft, isDone: false };
      }
    },
    [],
  );

  const appendUser = useCallback(
    async (text: string) => {
      if (!draft) return { done: true };

      const userMsgId = uid();
      const currentDraftId = draft.id;
      const newMessages: ChatMessage[] = [
        ...draft.messages,
        { id: userMsgId, role: "user", text, timestamp: Date.now() },
      ];

      setDraft((prev) =>
        prev
          ? {
              ...prev,
              messages: newMessages,
              isBackendProcessing: true,
            }
          : null
      );

      try {
        const res = await submitAssessment({
          transcript: text,
          conversation_id: currentDraftId,
          language: "en",
          source: draft.method === "voice" ? "web_mic" : "web_text",
        });

        const isDisambiguating = res.status === "disambiguating" && !!res.pending_question;
        const isDone = !isDisambiguating;
        const pendingQ = isDisambiguating ? res.pending_question : undefined;

        setDraft((prev) => {
          if (!prev || prev.id !== currentDraftId) return prev;
          const msgs = [...prev.messages];

          if (isDisambiguating) {
            msgs.push({
              id: uid(),
              role: "bot",
              text: res.pending_question!,
              timestamp: Date.now(),
            });
          } else {
            msgs.push({
              id: uid(),
              role: "bot",
              text: "Got it — checking this now.",
              timestamp: Date.now(),
            });
          }

          return {
            ...prev,
            messages: msgs,
            isBackendProcessing: false,
            isClassified: res.status !== "disambiguating",
            lastResponse: res,
          };
        });

        return { done: isDone, pendingQuestion: pendingQ };
      } catch (err) {
        console.error("[Naavya] /assess multi-turn backend call failed:", err);
        const errorMsg = err instanceof Error ? err.message : "Backend error";
        setDraft((prev) => {
          if (!prev || prev.id !== currentDraftId) return prev;
          return {
            ...prev,
            messages: [
              ...prev.messages,
              {
                id: uid(),
                role: "bot",
                text: `⚠️ Backend Error: ${errorMsg}. Failed to process response.`,
                timestamp: Date.now(),
              },
            ],
            isBackendProcessing: false,
          };
        });
        return { done: false };
      }
    },
    [draft],
  );


  const appendVoiceUser = useCallback(
    async (audioBlob: Blob) => {
      if (!draft) return { done: true };

      const currentDraftId = draft.id;

      setDraft((prev) => (prev ? { ...prev, isBackendProcessing: true } : null));

      try {
        const res = await submitVoiceAssessment(audioBlob, currentDraftId, "en", "web_mic");

        const userText =
          res.transcript && res.transcript.trim().length > 0
            ? res.transcript
            : "(Voice note submitted — no transcript available)";

        const isDisambiguating = res.status === "disambiguating" && !!res.pending_question;
        const isDone = !isDisambiguating;

        setDraft((prev) => {
          if (!prev || prev.id !== currentDraftId) return prev;
          const msgs: ChatMessage[] = [
            ...prev.messages,
            { id: uid(), role: "user", text: userText, timestamp: Date.now() },
          ];

          if (isDisambiguating) {
            msgs.push({
              id: uid(),
              role: "bot",
              text: res.pending_question!,
              timestamp: Date.now(),
            });
          } else {
            msgs.push({
              id: uid(),
              role: "bot",
              text: res.recommendation || "Got it — checking this now.",
              timestamp: Date.now(),
            });
          }

          return {
            ...prev,
            messages: msgs,
            isBackendProcessing: false,
            isClassified: res.status === "classified",
            lastResponse: res,
          };
        });

        return { done: isDone, pendingQuestion: isDisambiguating ? res.pending_question : undefined, audioUrl: res.audio_url ?? null, };
      } catch (err) {
        console.error("[Naavya] Voice follow-up backend call failed:", err);
        const errorMsg = err instanceof Error ? err.message : "Backend service error";
        setDraft((prev) => {
          if (!prev || prev.id !== currentDraftId) return prev;
          return {
            ...prev,
            messages: [
              ...prev.messages,
              {
                id: uid(),
                role: "bot",
                text: `⚠️ Voice Backend Error: ${errorMsg}. Failed to process response.`,
                timestamp: Date.now(),
              },
            ],
            isBackendProcessing: false,
          };
        });
        return { done: false };
      }
    },
    [draft],
  );

  const finalize = useCallback(
    async (overrideDraft?: DraftAssessment): Promise<Assessment> => {
      // Prefer an explicitly-passed draft (used by the voice flow, which
      // calls this immediately after startVoiceDraft resolves -- see the
      // comment in assessment.voice.tsx's done() for why relying on the
      // `draft` closure alone is unsafe there). Falls back to component
      // state for existing callers (e.g. the text/chat flow) that don't
      // have this timing hazard.
      const activeDraft = overrideDraft ?? draft;
      if (!activeDraft) throw new Error("No active draft assessment found.");

      const lastRes = activeDraft.lastResponse;

      if (!lastRes || lastRes.status !== "classified") {
        throw new Error("Unable to complete assessment: Backend service did not return a valid classification.");
      }

      const risk = mapRiskLevel(lastRes.risk_level);
      const summary =
        risk === "high"
          ? "Visit hospital immediately"
          : risk === "medium"
          ? "Contact your ASHA worker"
          : "Continue home care";

      const finalAssessment: Assessment = {
        id: lastRes.conversation_id || activeDraft.id,
        createdAt: Date.now(),
        method: activeDraft.method,
        messages: activeDraft.messages,
        risk,
        summary,
        explanation: lastRes.recommendation || "No detailed recommendation provided.",
        nextSteps: lastRes.next_steps || [],
        symptoms: Object.keys(lastRes.clear_signs || {}).map((s) => s.replace(/_/g, " ")),
        transcript: lastRes.transcript || "",
        audioUrl: lastRes.audio_url ?? null,
      };

      setHistory((h) => [finalAssessment, ...h]);
      setLastResult(finalAssessment);
      setDraft(null);
      return finalAssessment;
    },
    [draft],
  );

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
      startVoiceDraft,
      appendUser,
      appendVoiceUser,
      finalize,
      clearDraft,
      getById,
    }),
    [user, history, draft, lastResult, startDraft, startVoiceDraft, appendUser,appendVoiceUser, finalize, clearDraft, getById],
  );

  return <AssessmentContext.Provider value={value}>{children}</AssessmentContext.Provider>;
}

export function useAssessment() {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error("useAssessment must be used inside AssessmentProvider");
  return ctx;
}
