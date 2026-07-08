"use client";
import { useEffect, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { exitDemoMode, DEMO_TOKEN } from "@/lib/demo-mode";
import { DEMO_TENANT } from "@/lib/demo-data";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [demo, setDemo] = useState(false);

  const NAV = [
    { href: "/dashboard", label: t("overview"), icon: "🏠" },
    { href: "/dashboard/copilot", label: t("copilot"), icon: "🤖" },
    { href: "/dashboard/schedules", label: t("schedules"), icon: "📅" },
    { href: "/dashboard/staff", label: t("staff"), icon: "👥" },
    { href: "/dashboard/preferences", label: t("preferences"), icon: "💬" },
    { href: "/dashboard/analytics", label: t("analytics"), icon: "📊" },
  ];

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setDemo(token === DEMO_TOKEN);
  }, [router]);

  function logout() {
    exitDemoMode();
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    router.replace("/login");
  }

  function switchLocale(next: string) {
    router.replace(pathname, { locale: next });
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col text-white" style={{ backgroundColor: "#1a2e44" }}>
        <div className="px-5 py-5 border-b border-white/10">
          <span className="font-bold text-lg">ShiftFlow</span>
          {demo && (
            <div className="mt-1 text-xs text-yellow-300 font-medium">{DEMO_TENANT}</div>
          )}
        </div>
        <nav className="flex-1 py-4 px-2 space-y-1">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? "bg-white/20 text-white" : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="px-4 py-3 border-t border-white/10 flex gap-1">
          {["en", "bg"].map((l) => (
            <button
              key={l}
              onClick={() => switchLocale(l)}
              className={`flex-1 text-xs font-medium py-1.5 rounded-lg transition-colors ${
                locale === l ? "bg-white/20 text-white" : "text-white/50 hover:bg-white/10 hover:text-white"
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="px-4 py-4 border-t border-white/10">
          <button
            onClick={logout}
            className="w-full text-left text-sm text-white/60 hover:text-white px-3 py-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            {t("signOut")}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto bg-gray-50">
        {children}
      </main>
    </div>
  );
}
