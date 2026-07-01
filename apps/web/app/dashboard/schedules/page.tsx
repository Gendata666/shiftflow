"use client";
import { useEffect, useState } from "react";
import { isDemoMode } from "@/lib/demo-mode";
import {
  DEMO_STAFF, DEMO_SHIFT_TYPES, DEMO_SCHEDULE_VERIFIED,
  DEMO_START_DATE, DAY_NAMES_BG,
} from "@/lib/demo-data";

type Venue = { id: string; name: string; };
type Schedule = { id: string; period_id: string; generated_at: string; published_at: string | null; notes: string | null; assignments: unknown[]; };

export default function SchedulesPage() {
  const [isDemo, setIsDemo] = useState(false);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [generating, setGenerating] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [form, setForm] = useState({ venue_id: "", label: "", start_date: "", end_date: "" });
  const [published, setPublished] = useState(false);

  function headers() {
    return { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  useEffect(() => {
    if (isDemoMode()) {
      setIsDemo(true);
      return;
    }
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/venues/`, { headers: headers() })
      .then((r) => r.json()).then(setVenues).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function generate(period_id: string) {
    setGenerating(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/schedules/generate`, {
      method: "POST", headers: headers(), body: JSON.stringify({ period_id }),
    });
    if (res.ok) {
      const { schedule_id } = await res.json();
      await new Promise((r) => setTimeout(r, 3000));
      const sr = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/schedules/${schedule_id}`, { headers: headers() });
      if (sr.ok) setSchedule(await sr.json());
    }
    setGenerating(false);
  }

  // Build date list for the demo grid
  const demoDays = Array.from({ length: 28 }, (_, i) => {
    const d = new Date(DEMO_START_DATE);
    d.setDate(d.getDate() + i);
    return d;
  });

  // Week separators — group days by week
  const weeks = [0, 1, 2, 3].map((w) => demoDays.slice(w * 7, w * 7 + 7));

  if (isDemo) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Schedules</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Beach Bar · 07 Jul – 03 Aug 2026 · AI generated · ✅ 0 BAD sequences
            </p>
          </div>
          <div className="flex gap-2">
            <span className="px-3 py-1.5 rounded-lg text-xs border border-gray-200 text-gray-400">PDF (demo)</span>
            <span className="px-3 py-1.5 rounded-lg text-xs border border-gray-200 text-gray-400">Excel (demo)</span>
            <button
              onClick={() => setPublished((p) => !p)}
              className="px-3 py-1.5 rounded-lg text-sm text-white font-medium transition-colors"
              style={{ backgroundColor: published ? "#16a34a" : "#2c4a63" }}
            >
              {published ? "Published ✓" : "Publish"}
            </button>
          </div>
        </div>

        {/* Color legend */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(DEMO_SHIFT_TYPES).map(([code, st]) => (
            <span key={code} className="px-2.5 py-1 rounded text-xs font-medium border border-gray-200"
              style={{ backgroundColor: st.color }}>
              {code} · {st.label} · {st.hours}h
            </span>
          ))}
        </div>

        {/* Schedule grid */}
        <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
          <table className="text-xs border-collapse" style={{ minWidth: "900px" }}>
            <thead>
              {/* Week headers */}
              <tr>
                <th className="w-24 px-3 py-2 text-left text-white font-semibold border-r border-white/10"
                  style={{ backgroundColor: "#1a2e44" }} rowSpan={2}>
                  Барман
                </th>
                {weeks.map((_, wi) => (
                  <th key={wi} colSpan={7} className="px-2 py-2 text-center text-white font-semibold border-r border-white/10 border-b border-white/10"
                    style={{ backgroundColor: "#2c4a63" }}>
                    СЕДМИЦА {wi + 1}
                  </th>
                ))}
                <th colSpan={3} className="px-2 py-2 text-center text-white font-semibold"
                  style={{ backgroundColor: "#1a2e44" }}>
                  Общо
                </th>
              </tr>
              {/* Day headers */}
              <tr>
                {demoDays.map((day, i) => (
                  <th key={i} className="px-1 py-1.5 text-center font-medium border-r border-gray-200"
                    style={{ backgroundColor: day.getDay() === 0 || day.getDay() === 6 ? "#e8eef5" : "#eef2f7", color: "#555" }}>
                    <div>{DAY_NAMES_BG[day.getDay() === 0 ? 6 : day.getDay() - 1]}</div>
                    <div className="text-gray-400 font-normal">{day.getDate()}</div>
                  </th>
                ))}
                <th className="px-1 py-1.5 text-center font-medium text-blue-700 border-l border-gray-200" style={{ backgroundColor: "#dbeafe" }}>8h</th>
                <th className="px-1 py-1.5 text-center font-medium text-amber-700" style={{ backgroundColor: "#fef3c7" }}>10h</th>
                <th className="px-1 py-1.5 text-center font-medium text-green-700" style={{ backgroundColor: "#dcfce7" }}>12h</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_STAFF.map((staff, si) => {
                const shifts = DEMO_SCHEDULE_VERIFIED[staff.id];
                const cnt: Record<number, number> = { 8: 0, 10: 0, 12: 0 };
                return (
                  <tr key={staff.id} className={si % 2 ? "bg-gray-50" : "bg-white"}>
                    <td className="px-3 py-2 font-semibold text-gray-800 border-r border-gray-200 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: staff.color }} />
                        {staff.name}
                      </div>
                    </td>
                    {shifts.map((code, di) => {
                      const st = DEMO_SHIFT_TYPES[code];
                      if (st) cnt[st.hours] = (cnt[st.hours] || 0) + 1;
                      return (
                        <td key={di} className="border border-gray-100 text-center py-1.5 px-0.5"
                          style={{ backgroundColor: st?.color || "#f3f4f6", minWidth: "52px" }}>
                          <span className="font-medium text-gray-700 leading-tight block">{st?.label || code}</span>
                        </td>
                      );
                    })}
                    <td className="px-2 py-1.5 text-center font-bold border-l border-gray-200" style={{ backgroundColor: "#dbeafe", color: "#1d4ed8" }}>{cnt[8]}</td>
                    <td className="px-2 py-1.5 text-center font-bold" style={{ backgroundColor: "#fef3c7", color: "#b45309" }}>{cnt[10]}</td>
                    <td className="px-2 py-1.5 text-center font-bold" style={{ backgroundColor: "#dcfce7", color: "#15803d" }}>{cnt[12]}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="text-xs text-gray-400 mt-3">
          ✅ Всяка седмица: 2×8ч + 2×10ч + 3×12ч &nbsp;·&nbsp;
          12h смени само Пет/Съб/Нед &nbsp;·&nbsp;
          0 BAD последователности &nbsp;·&nbsp;
          Приятна последователност: С1=Джедая, С2=Васил, С3=Ники, С4=Афродита
        </p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Schedules</h1>
        <button onClick={() => setShowNew(!showNew)} className="px-4 py-2 rounded-lg text-white text-sm font-medium" style={{ backgroundColor: "#2c4a63" }}>
          + New Period
        </button>
      </div>

      {showNew && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-700">Create Schedule Period</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Venue</label>
              <select value={form.venue_id} onChange={(e) => setForm({ ...form, venue_id: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">Select venue…</option>
                {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Label (e.g. July 2026)</label>
              <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Start date</label>
              <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">End date</label>
              <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={async () => {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/schedules/periods`, {
                  method: "POST", headers: headers(), body: JSON.stringify(form),
                });
                if (res.ok) { const { id } = await res.json(); await generate(id); setShowNew(false); }
              }}
              disabled={generating}
              className="px-5 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-60"
              style={{ backgroundColor: "#2c4a63" }}
            >
              {generating ? "Generating schedule…" : "Generate with AI"}
            </button>
            <button onClick={() => setShowNew(false)} className="px-5 py-2 rounded-lg border text-sm text-gray-600">Cancel</button>
          </div>
        </div>
      )}

      {schedule && (
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-800">Generated Schedule</h2>
              <p className="text-xs text-gray-400 mt-0.5">{schedule.notes}</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => {}} className="px-3 py-1.5 rounded-lg border text-sm text-gray-600 hover:bg-gray-50">PDF</button>
              <button onClick={() => {}} className="px-3 py-1.5 rounded-lg border text-sm text-gray-600 hover:bg-gray-50">Excel</button>
              <button
                onClick={async () => {
                  await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/schedules/${schedule.id}/publish`, { method: "POST", headers: headers() });
                  setSchedule({ ...schedule, published_at: new Date().toISOString() });
                }}
                className="px-3 py-1.5 rounded-lg text-sm text-white font-medium"
                style={{ backgroundColor: schedule.published_at ? "#16a34a" : "#2c4a63" }}
              >
                {schedule.published_at ? "Published ✓" : "Publish"}
              </button>
            </div>
          </div>
        </div>
      )}

      {!schedule && !showNew && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📅</div>
          <p>No schedule yet. Create a period and generate with AI.</p>
        </div>
      )}
    </div>
  );
}
