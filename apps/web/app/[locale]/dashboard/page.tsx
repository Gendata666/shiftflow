import { getTranslations } from "next-intl/server";

export default async function DashboardPage() {
  const t = await getTranslations("dashboard");

  const STAT_CARDS = [
    { icon: "👥", value: "—", label: t("statStaff") },
    { icon: "📅", value: "—", label: t("statSchedule") },
    { icon: "💬", value: "—", label: t("statPending") },
    { icon: "⚠️", value: "0", label: t("statBad") },
  ];

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">{t("title")}</h1>
      <p className="text-gray-500 mb-8">{t("welcome")}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {STAT_CARDS.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="text-2xl mb-2">{s.icon}</div>
            <div className="text-2xl font-bold text-gray-800">{s.value}</div>
            <div className="text-sm text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="font-semibold text-gray-700 mb-4">{t("quickStart")}</h2>
        <ol className="space-y-3 text-sm text-gray-600">
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">1</span>
            {t.rich("step1", { strong: (chunks) => <strong>{chunks}</strong> })}
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">2</span>
            {t.rich("step2", { strong: (chunks) => <strong>{chunks}</strong>, em: (chunks) => <em>{chunks}</em> })}
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">3</span>
            {t.rich("step3", { em: (chunks) => <em>{chunks}</em> })}
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">4</span>
            {t("step4")}
          </li>
        </ol>
      </div>
    </div>
  );
}
