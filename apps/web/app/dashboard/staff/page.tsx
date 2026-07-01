"use client";
import { useEffect, useState } from "react";

type Staff = {
  id: string; name: string; email: string; role: string;
  role_label: string | null; contract_hours: number; active: boolean; color: string | null;
};

export default function StaffPage() {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", role_label: "", contract_hours: 40 });
  const [saving, setSaving] = useState(false);

  function authHeaders() {
    return { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  async function load() {
    setLoading(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/staff/`, { headers: authHeaders() });
    if (res.ok) setStaff(await res.json());
    setLoading(false);
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  async function addStaff(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/staff/`, {
      method: "POST", headers: authHeaders(), body: JSON.stringify(form),
    });
    if (res.ok) { setShowForm(false); setForm({ name: "", email: "", role_label: "", contract_hours: 40 }); await load(); }
    setSaving(false);
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Staff</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium"
          style={{ backgroundColor: "#2c4a63" }}
        >
          + Add Staff
        </button>
      </div>

      {showForm && (
        <form onSubmit={addStaff} className="bg-white border border-gray-100 rounded-xl p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-700">New Staff Member</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Full name</label>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Email</label>
              <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Role label (e.g. Bartender)</label>
              <input value={form.role_label} onChange={(e) => setForm({ ...form, role_label: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Contract hours/week</label>
              <input type="number" value={form.contract_hours} onChange={(e) => setForm({ ...form, contract_hours: +e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-60"
              style={{ backgroundColor: "#2c4a63" }}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-5 py-2 rounded-lg border text-sm text-gray-600">
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm">Loading...</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left">
                <th className="px-4 py-3 font-medium text-gray-500">Name</th>
                <th className="px-4 py-3 font-medium text-gray-500">Email</th>
                <th className="px-4 py-3 font-medium text-gray-500">Role</th>
                <th className="px-4 py-3 font-medium text-gray-500">Hours/wk</th>
                <th className="px-4 py-3 font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((s, i) => (
                <tr key={s.id} className={`border-b border-gray-50 ${i % 2 ? "bg-gray-50/50" : ""}`}>
                  <td className="px-4 py-3 font-medium text-gray-800">{s.name}</td>
                  <td className="px-4 py-3 text-gray-500">{s.email}</td>
                  <td className="px-4 py-3 text-gray-500">{s.role_label || s.role}</td>
                  <td className="px-4 py-3 text-gray-500">{s.contract_hours}h</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {s.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
              {staff.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No staff yet. Add your first team member above.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
