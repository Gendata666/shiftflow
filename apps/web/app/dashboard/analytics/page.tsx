"use client";
import { useState } from "react";

type HoursReport = {
  id: string; name: string; total_hours: number; days_worked: number;
  shifts_by_duration: Record<string, number>;
};

export default function AnalyticsPage() {
  const [scheduleId, setScheduleId] = useState("");
  const [report, setReport] = useState<HoursReport[]>([]);
  const [loading, setLoading] = useState(false);

  function headers() {
    return { Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  async function load() {
    if (!scheduleId.trim()) return;
    setLoading(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/analytics/hours/${scheduleId}`, { headers: headers() });
    if (res.ok) setReport(await res.json());
    setLoading(false);
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Hours Analytics</h1>

      <div className="flex gap-3 mb-6">
        <input
          placeholder="Paste schedule ID…"
          value={scheduleId}
          onChange={(e) => setScheduleId(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-72"
        />
        <button onClick={load} disabled={loading}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-60"
          style={{ backgroundColor: "#2c4a63" }}>
          {loading ? "Loading…" : "Load Report"}
        </button>
      </div>

      {report.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left" style={{ backgroundColor: "#1a2e44" }}>
                <th className="px-4 py-3 font-medium text-white">Name</th>
                <th className="px-4 py-3 font-medium text-white text-center">Days worked</th>
                <th className="px-4 py-3 font-medium text-white text-center">8h shifts</th>
                <th className="px-4 py-3 font-medium text-white text-center">10h shifts</th>
                <th className="px-4 py-3 font-medium text-white text-center">12h shifts</th>
                <th className="px-4 py-3 font-medium text-white text-center">Total hours</th>
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
          <p>Enter a schedule ID above to see the hours report.</p>
        </div>
      )}
    </div>
  );
}
