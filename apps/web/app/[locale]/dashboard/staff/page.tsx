"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { isDemoMode } from "@/lib/demo-mode";
import { DEMO_STAFF } from "@/lib/demo-data";
import { ROLE_KEYS, OTHER_ROLE } from "@/lib/roles";

type Staff = {
  id: string; name: string; email?: string; role?: string;
  role_label: string | null; contract_hours: number; active: boolean; color: string | null;
};

export default function StaffPage() {
  const t = useTranslations("staff");
  const tRoles = useTranslations("roles");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", role_label: "", contract_hours: 40 });
  const [saving, setSaving] = useState(false);
  const [customRole, setCustomRole] = useState(false);

  function roleLabel(value?: string | null) {
    if (!value) return "";
    return ROLE_KEYS.includes(value) ? tRoles(value) : value;
  }

  function authHeaders() {
    return { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token")}` };
  }

  async function load() {
    setLoading(true);
    if (isDemoMode()) {
      setStaff(DEMO_STAFF.map((s) => ({ ...s, email: `${s.name.toLowerCase()}@demo.bg`, role: "STAFF" })));
      setLoading(false);
      return;
    }
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
    if (res.ok) { setShowForm(false); setForm({ name: "", email: "", role_label: "", contract_hours: 40 }); setCustomRole(false); await load(); }
    setSaving(false);
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">{t("title")}</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium"
          style={{ backgroundColor: "#2c4a63" }}
        >
          {t("addStaff")}
        </button>
      </div>

      {showForm && (
        <form onSubmit={addStaff} className="bg-white border border-gray-100 rounded-xl p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-700">{t("newStaffMember")}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("fullName")}</label>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("email")}</label>
              <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("role")}</label>
              <select
                value={customRole ? OTHER_ROLE : form.role_label}
                onChange={(e) => {
                  if (e.target.value === OTHER_ROLE) { setCustomRole(true); setForm({ ...form, role_label: "" }); }
                  else { setCustomRole(false); setForm({ ...form, role_label: e.target.value }); }
                }}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="">{t("selectRole")}</option>
                {ROLE_KEYS.map((r) => <option key={r} value={r}>{tRoles(r)}</option>)}
                <option value={OTHER_ROLE}>{t("otherRole")}</option>
              </select>
              {customRole && (
                <input
                  autoFocus
                  placeholder={t("customRolePlaceholder")}
                  value={form.role_label}
                  onChange={(e) => setForm({ ...form, role_label: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm mt-2"
                />
              )}
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("contractHours")}</label>
              <input type="number" value={form.contract_hours} onChange={(e) => setForm({ ...form, contract_hours: +e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-60"
              style={{ backgroundColor: "#2c4a63" }}>
              {saving ? t("saving") : t("save")}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-5 py-2 rounded-lg border text-sm text-gray-600">
              {t("cancel")}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm">{t("loading")}</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left">
                <th className="px-4 py-3 font-medium text-gray-500">{t("name")}</th>
                <th className="px-4 py-3 font-medium text-gray-500">{t("email")}</th>
                <th className="px-4 py-3 font-medium text-gray-500">{t("role")}</th>
                <th className="px-4 py-3 font-medium text-gray-500">{t("hoursPerWeek")}</th>
                <th className="px-4 py-3 font-medium text-gray-500">{t("status")}</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((s, i) => (
                <tr key={s.id} className={`border-b border-gray-50 ${i % 2 ? "bg-gray-50/50" : ""}`}>
                  <td className="px-4 py-3 font-medium text-gray-800">{s.name}</td>
                  <td className="px-4 py-3 text-gray-500">{s.email}</td>
                  <td className="px-4 py-3 text-gray-500">{roleLabel(s.role_label) || s.role}</td>
                  <td className="px-4 py-3 text-gray-500">{s.contract_hours}h</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {s.active ? t("active") : t("inactive")}
                    </span>
                  </td>
                </tr>
              ))}
              {staff.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">{t("noStaffYet")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
