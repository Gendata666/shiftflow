"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { isDemoMode } from "@/lib/demo-mode";
import { DEMO_PREFERENCES } from "@/lib/demo-data";

type Pref = {
  id: string; staff_name: string; source: string; type: string;
  target_dates: string[]; raw_message: string | null; notes: string | null;
  status: string; created_at: string;
};

const SOURCE_ICONS: Record<string, string> = {
  TELEGRAM: "✈️",
  WHATSAPP: "💬",
  VIBER: "📱",
  WEB: "🌐",
};

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-600",
};

export default function PreferencesPage() {
  const t = useTranslations("preferences");
  const [prefs, setPrefs] = useState<Pref[]>([]);
  const [loading, setLoading] = useState(true);

  const TYPE_LABELS: Record<string, string> = {
    OFF_REQUEST: t("typeOffRequest"),
    UNAVAILABLE: t("typeUnavailable"),
    PREFERRED_SHIFT: t("typePreferredShift"),
    NOTES: t("typeNote"),
  };

  function headers() {
    return { Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  async function load() {
    setLoading(true);
    if (isDemoMode()) {
      setPrefs(DEMO_PREFERENCES as Pref[]);
      setLoading(false);
      return;
    }
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/preferences/?status_filter=PENDING`, { headers: headers() });
    if (res.ok) setPrefs(await res.json());
    setLoading(false);
  }

  async function resolve(id: string, action: "approve" | "reject") {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/preferences/${id}/${action}`, {
      method: "PATCH", headers: { ...headers(), "Content-Type": "application/json" },
    });
    setPrefs((prev) => prev.filter((p) => p.id !== id));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">{t("title")}</h1>
      <p className="text-gray-500 text-sm mb-6">{t("subtitle")}</p>

      {loading ? (
        <div className="text-gray-400 text-sm">{t("loading")}</div>
      ) : prefs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">💬</div>
          <p>{t("noPending")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {prefs.map((p) => (
            <div key={p.id} className="bg-white rounded-xl border border-gray-100 p-5 flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-gray-800">{p.staff_name}</span>
                  <span className="text-gray-400 text-xs">{SOURCE_ICONS[p.source]} {p.source.toLowerCase()}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[p.status]}`}>{p.status}</span>
                </div>
                <div className="text-sm text-gray-600 mb-1">
                  <strong>{TYPE_LABELS[p.type] || p.type}</strong>
                  {p.target_dates.length > 0 && ` · ${p.target_dates.join(", ")}`}
                </div>
                {p.raw_message && <div className="text-xs text-gray-400 italic">&quot;{p.raw_message}&quot;</div>}
                {p.notes && <div className="text-xs text-gray-500 mt-0.5">{p.notes}</div>}
              </div>
              {p.status === "PENDING" && (
                <div className="flex gap-2 flex-shrink-0">
                  <button onClick={() => resolve(p.id, "approve")}
                    className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700">{t("approve")}</button>
                  <button onClick={() => resolve(p.id, "reject")}
                    className="px-3 py-1.5 rounded-lg border border-red-200 text-red-600 text-xs font-medium hover:bg-red-50">{t("reject")}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
