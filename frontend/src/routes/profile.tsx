import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { LogOut, MessageCircle, Check } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAssessment } from "@/lib/assessment-context";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [{ title: "Profile — Naavya" }, { name: "description", content: "Manage your Naavya account." }],
  }),
  component: ProfilePage,
});

function ProfilePage() {
  const { user, logout } = useAssessment();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.name ?? "");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState(user?.email ?? "");
  const [lang, setLang] = useState("en");
  const [notif, setNotif] = useState(true);
  const [waConnected, setWaConnected] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!user) {
    return (
      <div className="min-h-screen bg-background">
        <SiteNav />
        <main className="mx-auto max-w-md px-6 py-20 text-center">
          <h1 className="font-display text-2xl font-semibold text-foreground">
            Log in to see your profile
          </h1>
          <Button
            className="mt-6 rounded-full"
            onClick={() => navigate({ to: "/login" })}
          >
            Log in
          </Button>
        </main>
      </div>
    );
  }

  const initials = user.name
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main className="mx-auto max-w-2xl px-6 py-10 md:py-16">
        <div className="flex items-center gap-4">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-2xl font-semibold text-primary-foreground">
            {initials || "🙂"}
          </span>
          <div>
            <h1 className="font-display text-2xl font-semibold text-foreground">
              {user.name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {user.role === "asha" ? "ASHA Worker" : "Parent / Caregiver"}
            </p>
          </div>
        </div>

        <Section title="Personal info">
          <div className="space-y-4">
            <FormRow label="Full name" id="pname">
              <Input id="pname" value={name} onChange={(e) => setName(e.target.value)} className="h-12 rounded-2xl" />
            </FormRow>
            <FormRow label="Phone" id="pphone">
              <Input id="pphone" placeholder="Add your info" value={phone} onChange={(e) => setPhone(e.target.value)} className="h-12 rounded-2xl" />
            </FormRow>
            <FormRow label="Email" id="pemail">
              <Input id="pemail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="h-12 rounded-2xl" />
            </FormRow>
          </div>
        </Section>

        <Section title="Preferred language">
          <Select value={lang} onValueChange={setLang}>
            <SelectTrigger className="h-12 rounded-2xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="hi">हिन्दी</SelectItem>
              <SelectItem value="ta">தமிழ்</SelectItem>
              <SelectItem value="te">తెలుగు</SelectItem>
            </SelectContent>
          </Select>
        </Section>

        <Section title="Notifications">
          <div className="flex items-center justify-between rounded-2xl border border-border bg-surface p-4">
            <div>
              <p className="font-medium text-foreground">Follow-up reminders</p>
              <p className="text-sm text-muted-foreground">
                Get a gentle reminder to check in after a low-risk assessment.
              </p>
            </div>
            <Switch checked={notif} onCheckedChange={setNotif} />
          </div>
        </Section>

        <Section title="WhatsApp">
          <div className="flex items-center justify-between rounded-2xl border border-border bg-surface p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft text-primary">
                <MessageCircle className="h-5 w-5" />
              </span>
              <div>
                <p className="font-medium text-foreground">
                  {waConnected ? "Connected" : "Not connected"}
                </p>
                <p className="text-sm text-muted-foreground">
                  {waConnected
                    ? "Continue assessments on WhatsApp."
                    : "Link your number to continue from WhatsApp."}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              className="rounded-full"
              onClick={() => setWaConnected((v) => !v)}
            >
              {waConnected ? "Disconnect" : "Connect"}
            </Button>
          </div>
        </Section>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Button
            onClick={() => {
              setSaved(true);
              setTimeout(() => setSaved(false), 1800);
            }}
            className="rounded-full"
          >
            {saved ? <><Check className="mr-2 h-4 w-4" /> Saved</> : "Save changes"}
          </Button>
          <button
            type="button"
            onClick={() => {
              logout();
              navigate({ to: "/" });
            }}
            className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm text-muted-foreground hover:text-danger"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </main>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

function FormRow({ label, id, children }: { label: string; id?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}
