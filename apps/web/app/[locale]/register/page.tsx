"use client";
import { useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link, useRouter, usePathname } from "@/i18n/navigation";

export default function RegisterPage() {
  const t = useTranslations("register");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", company: "", slug: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCompany = (v: string) => {
    const slug = v.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    setForm({ ...form, company: v, slug });
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || t("registrationFailed"));
        return;
      }
      const { access_token, refresh_token } = await res.json();
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      router.push("/dashboard");
    } catch {
      setError(t("networkError"));
    } finally {
      setLoading(false);
    }
  }

  function switchLocale(next: string) {
    router.replace(pathname, { locale: next });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-end gap-1 mb-4">
          {["en", "bg"].map((l) => (
            <button
              key={l}
              onClick={() => switchLocale(l)}
              className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
                locale === l ? "bg-gray-200 text-gray-800" : "text-gray-400 hover:bg-gray-100"
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold" style={{ color: "#1a2e44" }}>ShiftFlow</h1>
          <p className="text-gray-500 mt-1">{t("subtitle")}</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("yourName")}</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")}</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("password")}</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("companyName")}</label>
            <input
              type="text"
              value={form.company}
              onChange={(e) => handleCompany(e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {form.slug && (
              <p className="text-xs text-gray-400 mt-1">{t("workspace")}: <strong>{form.slug}</strong></p>
            )}
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-white font-semibold transition-colors disabled:opacity-60"
            style={{ backgroundColor: "#2c4a63" }}
          >
            {loading ? t("creatingAccount") : t("createAccount")}
          </button>
          <p className="text-center text-sm text-gray-500">
            {t("alreadyHaveAccount")}{" "}
            <Link href="/login" className="text-blue-600 hover:underline">{t("signIn")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
