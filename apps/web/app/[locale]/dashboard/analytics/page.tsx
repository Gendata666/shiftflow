"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { isDemoMode } from "@/lib/demo-mode";
import { DEMO_ANALYTICS } from "@/lib/demo-data";
import { listRuns, getHoursReport, type RunListItem, type HoursReport } from "@/lib/copilot-api";

export default function AnalyticsPage() {
  const t = useTranslations("analytics");
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [selectedRun, setSelectedRun] = useState("");
  const [report, setReport] = useState<HoursReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    if (isDemoMode()) {
      setIsDemo(true);
      setReport(DEMO_ANALYTICS as HoursReport[]);
      return;
    }
    (async () => {
      const list = await listRuns();
      setRuns(list);
      if (list.length > 0) {
        setSelectedRun(list[0].id);
        await load(list[0].id);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load(runId: string) {
    if (!runId) return;
    setLoading(true);
    setReport(await getHoursReport(runId));
    setLoading(false);
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">{t("title")}</h1>
      {isDemo && (
        <p className="text-sm text-gray-500 mb-6">{t("demoSubtitle")}</p>
      )}

      {!isDemo && runs.length > 0 && (
        <div className="flex gap-3 mb-6">
          <select
            value={selectedRun}
            onChange={(e) => { setSelectedRun(e.target.value); load(e.target.value); }}
            className="border rounded-lg px-3 py-2 text-sm w-96"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {new Date(r.created_at).toLocaleString()} — {r.spec_summary ?? r.status}
              </option>
            ))}
          </select>
          {loading && <span className="px-4 py-2 text-sm text-gray-400">{t("loading")}</span>}
        </div>
      )}

      {report.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left" style={{ backgroundColor: "#1a2e44" }}>
                <th className="px-4 py-3 font-medium text-white">{t("name")}</th>
                <th className="px-4 py-3 font-medium text-white text-center">{t("daysWorked")}</th>
                <th className="px-4 py-3 font-medium text-white text-center">{t("hShifts", { h: 8 })}</th>
                <th className="px-4 py-3 font-medium text-white text-center">{t("hShifts", { h: 10 })}</th>
                <th className="px-4 py-3 font-medium text-white text-center">{t("hShifts", { h: 12 })}</th>
                <th className="px-4 py-3 font-medium text-white text-center">{t("totalHours")}</th>
              </tr>
            </thead>
            <tbody>
              {report.map((r, i) => (
                <tr key={r.id} className={`border-b border-gray-50 ${i % 2 ? "bg-gray-50/50" : ""}`}>
                  <td className="px-4 py-3 font-semibold text-gray-800">{r.name}</td>
                  <td className="px-4 py-3 text-center text-gray-600">{r.days_worked}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">{r.shifts_by_duration[8] || 0}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">{r.shifts_by_duration[10] || 0}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-0.5 rounded bg-green-100 text-green-700 font-medium">{r.shifts_by_duration[12] || 0}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="font-bold text-gray-800">{r.total_hours}h</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {report.length === 0 && !loading && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📊</div>
          <p>{runs.length === 0 ? t("noSchedulesYet") : t("selectSchedule")}</p>
        </div>
      )}
    </div>
  );
}
