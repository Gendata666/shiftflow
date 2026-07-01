"use client";
import { useEffect, useState } from "react";

type Assignment = { id: string; staff_profile_id: string; date: string; shift_type_id: string; };
type Schedule = { id: string; period_id: string; generated_at: string; published_at: string | null; notes: string | null; assignments: Assignment[]; };
type Venue = { id: string; name: string; };

export default function SchedulesPage() {
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [generating, setGenerating] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [form, setForm] = useState({ venue_id: "", label: "", start_date: "", end_date: "" });

  function headers() {
    return { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/venues/`, { headers: headers() })
      .then((r) => r.json()).then(setVenues).catch(() => {});
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

  async function exportFile(format: "excel" | "pdf") {
    if (!schedule) return;
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/export/${schedule.id}/${format}`, { headers: headers() });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `schedule.${format === "excel" ? "xlsx" : "pdf"}`; a.click();
    }
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
              <button onClick={() => exportFile("pdf")}
                className="px-3 py-1.5 rounded-lg border text-sm text-gray-600 hover:bg-gray-50">PDF</button>
              <button onClick={() => exportFile("excel")}
                className="px-3 py-1.5 rounded-lg border text-sm text-gray-600 hover:bg-gray-50">Excel</button>
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
          <p className="text-sm text-gray-500">
            {schedule.assignments.length} shift assignments generated.
            {schedule.published_at ? " Schedule is published and visible to staff." : " Review and publish when ready."}
          </p>
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
