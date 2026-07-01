import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Hero */}
      <div
        className="flex-1 flex flex-col items-center justify-center text-white px-4 text-center py-24"
        style={{ background: "linear-gradient(135deg, #1a2e44 0%, #2c4a63 50%, #1a2e44 100%)" }}
      >
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
            AI-Powered · Zero Setup · Works on Any Device
          </div>
          <h1 className="text-5xl font-bold mb-4 leading-tight">
            Smart Scheduling<br />
            <span className="text-blue-300">for Your Team</span>
          </h1>
          <p className="text-xl text-white/80 mb-8 leading-relaxed">
            Generate constraint-satisfying work schedules in seconds.
            Staff submit preferences via Telegram. Export to PDF or Excel.
            No installation — just open your browser.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              href="/register"
              className="bg-blue-500 hover:bg-blue-400 text-white font-semibold px-8 py-3 rounded-xl transition-colors text-lg"
            >
              Start Free Trial
            </Link>
            <Link
              href="/login"
              className="border border-white/30 hover:bg-white/10 text-white font-semibold px-8 py-3 rounded-xl transition-colors text-lg"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>

      {/* Feature cards */}
      <section className="bg-white py-16 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-center text-gray-800 mb-10">
            Everything a manager needs
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                <div className="text-3xl mb-3">{f.icon}</div>
                <h3 className="font-semibold text-gray-800 mb-2">{f.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Shift color legend */}
      <section className="bg-gray-50 py-12 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-xl font-semibold text-gray-700 mb-6">Color-coded shift types</h2>
          <div className="flex flex-wrap justify-center gap-3">
            {SHIFT_TYPES.map((s) => (
              <span
                key={s.label}
                className="px-4 py-2 rounded-lg text-sm font-medium border"
                style={{ backgroundColor: s.color, borderColor: s.border }}
              >
                {s.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      <footer className="bg-[#1a2e44] text-white/60 text-sm text-center py-4">
        ShiftFlow by <span className="text-white/80">Digital Nebula AI</span>
      </footer>
    </main>
  );
}

const FEATURES = [
  {
    icon: "🤖",
    title: "AI Schedule Generator",
    desc: "OR-Tools constraint solver generates gap-free schedules in seconds, respecting shift quotas, rest rules, and weekend rotation.",
  },
  {
    icon: "💬",
    title: "Telegram Preferences",
    desc: "Staff message the bot: \"I can't work Friday\" and Claude AI parses it. Manager approves with one click.",
  },
  {
    icon: "📊",
    title: "Hours Analytics",
    desc: "Track total hours per employee weekly and monthly. Spot overtime before it happens. Export reports to CSV.",
  },
  {
    icon: "📄",
    title: "PDF & Excel Export",
    desc: "One click to generate a print-ready A4 landscape schedule with color coding — exactly like a hand-made Excel.",
  },
  {
    icon: "✏️",
    title: "Manual Override",
    desc: "Swap individual shifts after generation. Re-trigger verification to check constraint satisfaction.",
  },
  {
    icon: "🔒",
    title: "Secure & Multi-tenant",
    desc: "Each venue is fully isolated. Staff see only their own schedule. All data encrypted in transit and at rest.",
  },
];

const SHIFT_TYPES = [
  { label: "8h  08:00–16:00", color: "#dbeafe", border: "#93c5fd" },
  { label: "8h  16:00–00:00", color: "#dbeafe", border: "#93c5fd" },
  { label: "10h  10:00–20:00", color: "#fef3c7", border: "#fcd34d" },
  { label: "10h  14:00–00:00", color: "#fef3c7", border: "#fcd34d" },
  { label: "12h Open  08:00–20:00", color: "#dcfce7", border: "#86efac" },
  { label: "12h Close  12:00–00:00", color: "#ffe4e6", border: "#fda4af" },
];
