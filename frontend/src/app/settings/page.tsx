import { SettingsDashboard } from "@/components/settings-dashboard";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8">
      <header className="mb-8 pb-6">
        <p className="mb-2 text-[0.78rem] font-bold uppercase tracking-[0.18em] text-cardinal">
          Model router
        </p>
        <h1 className="font-serif text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-[1.05] tracking-tight">
          Settings
        </h1>
        <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted">
          Choose the chat and embedding models the backend should use, set
          reasoning effort, and test the Stanford Gateway without calling
          providers from the browser.
        </p>
      </header>
      <main>
        <SettingsDashboard />
      </main>
    </div>
  );
}
