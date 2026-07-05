"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { exitDemoMode, DEMO_TOKEN } from "@/lib/demo-mode";
import { DEMO_TENANT } from "@/lib/demo-data";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: "🏠" },
  { href: "/dashboard/copilot", label: "AI Copilot", icon: "🤖" },
  { href: "/dashboard/schedules", label: "Schedules", icon: "📅" },
  { href: "/dashboard/staff", label: "Staff", icon: "👥" },
  { href: "/dashboard/preferences", label: "Preferences", icon: "💬" },
  { href: "/dashboard/analytics", label: "Analytics", icon: "📊" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [demo, setDemo] = useState(false);

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
        <div className="px-4 py-4 border-t border-white/10">
          <button
            onClick={logout}
            className="w-full text-left text-sm text-white/60 hover:text-white px-3 py-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            Sign out
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
