import { createFileRoute } from "@tanstack/react-router";
import { SiteNav } from "@/components/site-nav";
import { SiteFooter } from "@/components/site-footer";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About Naavya — Clinical safety, privacy, honesty" },
      {
        name: "description",
        content:
          "Naavya is a decision-support prototype for newborn triage, grounded in the IMNCI/HBNC guideline. Learn how it works, its limits, and how we protect your data.",
      },
      { property: "og:title", content: "About Naavya" },
      { property: "og:description", content: "How it works, clinical safety, and privacy." },
    ],
  }),
  component: AboutPage,
});

const sections = [
  {
    title: "Mission",
    body: "Naavya helps rural caregivers describe a newborn's symptoms and receive one of three plain-language recommendations: continue home care, contact the ASHA worker, or go to a facility now. Our goal is to reduce the time between a worrying symptom and a safe next step — not to replace the people who provide care.",
  },
  {
    title: "How the AI works",
    body: "You describe symptoms by voice or text. A language model transcribes and structures what you said. Follow-up questions are asked only when clarification is needed. The final recommendation is produced by matching the collected picture to rules in the government IMNCI/HBNC guideline — so every recommendation traces back to a specific published rule.",
  },
  {
    title: "Clinical safety",
    body: "Naavya never names a disease and never says 'diagnosis.' It is designed to escalate quickly on any high-risk signal, and to route uncertain cases to the ASHA worker rather than resolving them silently. It is a decision-support prototype — a validated clinical tool is a different, higher bar and is not what this product currently claims to be.",
  },
  {
    title: "Privacy",
    body: "Voice recordings are used only to produce the transcript for your session and are not shared with third parties. If you create an account, your history is saved to your account so you can review past assessments. You can delete your account and its history at any time from your profile.",
  },
  {
    title: "Technology",
    body: "Built as a mobile-first web app so it works on low-end phones with patchy data. Voice input degrades gracefully to text. WhatsApp is offered as a familiar alternative surface for people who prefer it.",
  },
];

const faqs = [
  {
    q: "Is this a diagnosis?",
    a: "No. Naavya never gives a diagnosis or names a specific disease. It gives a next-step recommendation.",
  },
  {
    q: "Do I need to create an account?",
    a: "No. You can complete a full assessment as a guest. Logging in only unlocks assessment history and WhatsApp continuity.",
  },
  {
    q: "What if the internet drops mid-conversation?",
    a: "Your session is preserved. When you're back online, the same conversation resumes — you won't have to start over.",
  },
  {
    q: "Does this replace my ASHA worker?",
    a: "Absolutely not. Naavya is designed to route to your ASHA worker, not around them.",
  },
];

function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteNav />

      <main className="mx-auto max-w-3xl px-6 py-16 md:py-24">
        <p className="text-sm font-bold uppercase tracking-wide text-primary">About Naavya</p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-foreground md:text-5xl">
          A calm second opinion for newborn care.
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Built for the moments when a caregiver is worried, tired, and not sure what to do next.
        </p>

        <div className="mt-12 space-y-10">
          {sections.map((s) => (
            <section key={s.title} className="border-t border-border pt-8">
              <h2 className="font-display text-2xl font-semibold text-foreground">{s.title}</h2>
              <p className="mt-3 text-base leading-relaxed text-muted-foreground">{s.body}</p>
            </section>
          ))}

          <section className="border-t border-border pt-8">
            <h2 className="font-display text-2xl font-semibold text-foreground">FAQ</h2>
            <Accordion type="single" collapsible className="mt-4">
              {faqs.map((f, i) => (
                <AccordionItem key={f.q} value={`i-${i}`} className="border-border">
                  <AccordionTrigger className="text-left text-base font-medium text-foreground">
                    {f.q}
                  </AccordionTrigger>
                  <AccordionContent className="text-muted-foreground">
                    {f.a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </section>

          <p className="rounded-3xl bg-warning-soft/60 p-6 text-sm text-[color:oklch(0.35_0.1_75)]">
            Naavya is a decision-support prototype, not a validated clinical tool. In any
            emergency, contact your local emergency services or nearest facility immediately.
          </p>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
