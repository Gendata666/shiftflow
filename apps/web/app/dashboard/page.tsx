export default function DashboardPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">Dashboard</h1>
      <p className="text-gray-500 mb-8">Welcome to ShiftFlow. Manage your team schedules below.</p>

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
        <h2 className="font-semibold text-gray-700 mb-4">Quick Start</h2>
        <ol className="space-y-3 text-sm text-gray-600">
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">1</span>
            Go to <strong>Staff</strong> and add your team members
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">2</span>
            Go to <strong>Schedules</strong>, create a period, and click <em>Generate with AI</em>
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">3</span>
            Review the schedule, make manual tweaks if needed, then <em>Publish</em>
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs">4</span>
            Share the Telegram bot link with your staff so they can send shift preferences
          </li>
        </ol>
      </div>
    </div>
  );
}

const STAT_CARDS = [
  { icon: "👥", value: "—", label: "Staff members" },
  { icon: "📅", value: "—", label: "Active schedule" },
  { icon: "💬", value: "—", label: "Pending preferences" },
  { icon: "⚠️", value: "0", label: "BAD sequences" },
];
