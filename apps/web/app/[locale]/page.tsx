"use client";
import { useTranslations, useLocale } from "next-intl";
import { Link, useRouter, usePathname } from "@/i18n/navigation";
import { enterDemoMode } from "@/lib/demo-mode";

type Feature = { icon: string; title: string; desc: string };
type ShiftType = { label: string; color: string; border: string };

export default function HomePage() {
  const t = useTranslations("home");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const features = t.raw("features") as Feature[];
  const shiftTypes = t.raw("shiftTypes") as ShiftType[];

  function tryDemo() {
    enterDemoMode();
    router.push("/dashboard/schedules");
  }

  function switchLocale(next: string) {
    router.replace(pathname, { locale: next });
  }

  return (
    <main className="min-h-screen flex flex-col">
      {/* Hero */}
      <div
        className="flex-1 flex flex-col items-center justify-center text-white px-4 text-center py-24 relative"
        style={{ background: "linear-gradient(135deg, #1a2e44 0%, #2c4a63 50%, #1a2e44 100%)" }}
      >
        <div className="absolute top-4 right-4 flex gap-1">
          {["en", "bg"].map((l) => (
            <button
              key={l}
              onClick={() => switchLocale(l)}
              className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
                locale === l ? "bg-white/20 text-white" : "text-white/50 hover:bg-white/10 hover:text-white"
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
            {t("badge")}
          </div>
          <h1 className="text-5xl font-bold mb-4 leading-tight">
            {t("heroTitle")}<br />
            <span className="text-blue-300">{t("heroTitleAccent")}</span>
          </h1>
          <p className="text-xl text-white/80 mb-8 leading-relaxed">
            {t("heroSubtitle")}
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <button
              onClick={tryDemo}
              className="bg-yellow-400 hover:bg-yellow-300 text-gray-900 font-bold px-8 py-3 rounded-xl transition-colors text-lg shadow-lg"
            >
              {t("tryDemo")}
            </button>
            <Link
              href="/register"
              className="bg-blue-500 hover:bg-blue-400 text-white font-semibold px-8 py-3 rounded-xl transition-colors text-lg"
            >
              {t("startFreeTrial")}
            </Link>
            <Link
              href="/login"
              className="border border-white/30 hover:bg-white/10 text-white font-semibold px-8 py-3 rounded-xl transition-colors text-lg"
            >
              {t("signIn")}
            </Link>
          </div>
        </div>
      </div>

      {/* Feature cards */}
      <section className="bg-white py-16 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-center text-gray-800 mb-10">
            {t("featuresTitle")}
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {features.map((f) => (
              <div key={f.title} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                <div className="text-3xl mb-3">{f.icon}</div>
                <h3 className="font-semibold text-gray-800 mb-2">{f.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Shift color legend */}
      <section className="bg-gray-50 py-12 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-xl font-semibold text-gray-700 mb-6">{t("shiftTypesTitle")}</h2>
          <div className="flex flex-wrap justify-center gap-3">
            {shiftTypes.map((s) => (
              <span
                key={s.label}
                className="px-4 py-2 rounded-lg text-sm font-medium border"
                style={{ backgroundColor: s.color, borderColor: s.border }}
              >
                {s.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      <footer className="bg-[#1a2e44] text-white/60 text-sm text-center py-4">
        {t("footerBy")} <span className="text-white/80">Digital Nebula AI</span>
      </footer>
    </main>
  );
}
