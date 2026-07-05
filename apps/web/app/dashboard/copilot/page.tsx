"use client";
import { useRef, useState } from "react";
import { isDemoMode } from "@/lib/demo-mode";
import {
  Assignment,
  ChatEvent,
  GenerateResponse,
  RunSummary,
  SpecPayload,
  chatStream,
  confirmSpec,
  downloadExport,
  generateSchedule,
  parseBrief,
  updateSpecFromBrief,
} from "@/lib/copilot-api";

const DAY_NAMES_BG = ["Пон", "Вт", "Ср", "Чет", "Пет", "Съб", "Нед"];

type ChatMsg = { role: "user" | "assistant"; text: string; tools?: string[] };

export default function CopilotPage() {
  const [spec, setSpec] = useState<SpecPayload | null>(null);
  const [run, setRun] = useState<GenerateResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // brief form
  const [brief, setBrief] = useState("");
  const [startDate, setStartDate] = useState("");
  const [numDays, setNumDays] = useState(28);

  // chat
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const chatBottom = useRef<HTMLDivElement>(null);

  if (typeof window !== "undefined" && isDemoMode()) {
    return (
      <div className="p-8 text-center text-gray-400">
        <div className="text-5xl mb-4">🤖</div>
        <p>AI Copilot изисква реален акаунт — демо режимът показва само примерния график.</p>
      </div>
    );
  }

  async function guard<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(label);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onParse() {
    const result = await guard("Интерпретирам заданието…", () =>
      parseBrief({ brief, start_date: startDate, num_days: numDays })
    );
    if (result) {
      setSpec(result);
      setRun(null);
    }
  }

  async function onUpdate() {
    if (!spec) return;
    const result = await guard("Прилагам промените…", () => updateSpecFromBrief(spec.id, brief));
    if (result) {
      setSpec(result);
      setRun(null);
      setBrief("");
    }
  }

  async function onConfirm() {
    if (!spec) return;
    await guard("Потвърждавам…", () => confirmSpec(spec.id));
    setSpec({ ...spec, status: "ACTIVE" });
  }

  async function onGenerate() {
    if (!spec) return;
    const result = await guard("Генерирам график (CP-SAT)…", () => generateSchedule(spec.id));
    if (result) setRun(result);
  }

  async function onChat() {
    if (!spec || !chatInput.trim()) return;
    const userText = chatInput.trim();
    setChatInput("");
    setMessages((m) => [...m, { role: "user", text: userText }, { role: "assistant", text: "", tools: [] }]);
    try {
      for await (const event of chatStream(spec.id, userText)) {
        applyChatEvent(event);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function applyChatEvent(event: ChatEvent) {
    if (event.type === "text") {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + event.text };
        return copy;
      });
    } else if (event.type === "tool") {
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { ...last, tools: [...(last.tools ?? []), event.name] };
        return copy;
      });
    } else if (event.type === "spec_updated" && spec) {
      setSpec({ ...spec, version: event.version });
    } else if (event.type === "report") {
      setRun((r) => (r ? { ...r, summary: event.summary } : r));
    }
    chatBottom.current?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div className="p-6 max-w-[1500px]">
      <h1 className="text-2xl font-bold text-gray-800 mb-1">AI Copilot</h1>
      <p className="text-sm text-gray-500 mb-5">
        Опиши правилата за смените на естествен език — AI ги превежда в проверими правила, солвърът изгражда графика.
      </p>

      {error && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* Left: brief + spec confirmation */}
        <div className="space-y-5">
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h2 className="font-semibold text-gray-700 mb-3">
              {spec ? "Допълнително задание (сливат се с текущите правила)" : "Задание от мениджъра"}
            </h2>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={8}
              placeholder="Постави заданието тук — напр. „Създай месечен график за 4 бармани… всяка седмица 2×8ч + 2×10ч + 3×12ч…“"
              className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
            />
            {!spec && (
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Начална дата</label>
                  <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Брой дни</label>
                  <input type="number" value={numDays} onChange={(e) => setNumDays(Number(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
            )}
            <button
              onClick={spec ? onUpdate : onParse}
              disabled={!!busy || !brief.trim() || (!spec && !startDate)}
              className="mt-3 px-5 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50"
              style={{ backgroundColor: "#2c4a63" }}
            >
              {busy ?? (spec ? "Интерпретирай промените" : "Интерпретирай заданието")}
            </button>
          </div>

          {spec && (
            <SpecCard
              spec={spec}
              onConfirm={onConfirm}
              onGenerate={onGenerate}
              busy={busy}
            />
          )}

          {/* Chat */}
          {spec && spec.status === "ACTIVE" && (
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h2 className="font-semibold text-gray-700 mb-3">Разговор с копилота</h2>
              <div className="max-h-80 overflow-y-auto space-y-3 mb-3">
                {messages.map((m, i) => (
                  <div key={i} className={m.role === "user" ? "text-right" : ""}>
                    {m.tools?.map((t, j) => (
                      <div key={j} className="text-xs text-gray-400 italic mb-1">⚙ {toolLabel(t)}</div>
                    ))}
                    <div
                      className={`inline-block px-3 py-2 rounded-xl text-sm whitespace-pre-wrap text-left max-w-[85%] ${
                        m.role === "user" ? "bg-[#2c4a63] text-white" : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {m.text || "…"}
                    </div>
                  </div>
                ))}
                <div ref={chatBottom} />
              </div>
              <div className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onChat()}
                  placeholder='напр. „Защо Афродита затваря 3 уикенда?“ или „Добави: никой не работи повече от 5 поредни дни“'
                  className="flex-1 border rounded-lg px-3 py-2 text-sm"
                />
                <button onClick={onChat} className="px-4 py-2 rounded-lg text-white text-sm" style={{ backgroundColor: "#2c4a63" }}>
                  ➤
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: schedule grid + verification */}
        <div className="space-y-5">
          {run && spec && (
            <>
              <VerificationCard summary={run.summary} runId={run.run_id} />
              <ScheduleGrid spec={spec} assignments={run.assignments} findings={run.summary.findings} />
            </>
          )}
          {!run && (
            <div className="bg-white rounded-xl border border-dashed border-gray-200 p-12 text-center text-gray-400">
              <div className="text-4xl mb-3">📅</div>
              Графикът се появява тук след генериране.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function toolLabel(name: string): string {
  const map: Record<string, string> = {
    get_spec: "чета правилата",
    apply_spec_update: "прилагам промяна в правилата",
    generate_schedule: "генерирам график",
    get_verification_report: "чета проверката",
  };
  return map[name] ?? name;
}

function SpecCard({
  spec, onConfirm, onGenerate, busy,
}: {
  spec: SpecPayload;
  onConfirm: () => void;
  onGenerate: () => void;
  busy: string | null;
}) {
  const enforcementBadge = (r: { enforcement: string; relaxable: boolean; auto_repair: boolean }) => {
    if (r.enforcement === "hard" && r.relaxable) return ["max. близко", "#fef3c7", "#b45309"];
    if (r.enforcement === "hard") return ["задължително", "#fee2e2", "#b91c1c"];
    if (r.auto_repair) return ["авто-поправка", "#e0e7ff", "#4338ca"];
    return ["желателно", "#dbeafe", "#1d4ed8"];
  };

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-gray-700">
          Интерпретирани правила <span className="text-xs text-gray-400">v{spec.version}</span>
        </h2>
        <span
          className="px-2 py-0.5 rounded text-xs font-medium"
          style={{
            backgroundColor: spec.status === "ACTIVE" ? "#dcfce7" : "#fef3c7",
            color: spec.status === "ACTIVE" ? "#15803d" : "#b45309",
          }}
        >
          {spec.status === "ACTIVE" ? "потвърдени" : "чакат потвърждение"}
        </span>
      </div>

      {spec.summary && <p className="text-sm text-gray-600 mb-3">{spec.summary}</p>}

      {(spec.assumptions?.length ?? 0) > 0 && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200">
          <div className="text-xs font-semibold text-amber-800 mb-1">Предположения — провери ги:</div>
          {spec.assumptions!.map((a, i) => (
            <div key={i} className="text-xs text-amber-700">• {a}</div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mb-3">
        {spec.overview.shifts.map((s) => (
          <span key={s.id} className="px-2 py-0.5 rounded text-xs border border-gray-200 bg-gray-50">
            {s.time} · {s.hours}ч{!s.preferred && " (резервна)"}
          </span>
        ))}
      </div>

      <div className="space-y-1.5 mb-4 max-h-56 overflow-y-auto">
        {spec.overview.rules.map((r) => {
          const [label, bg, fg] = enforcementBadge(r);
          return (
            <div key={r.id} className="flex items-start gap-2 text-sm">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 mt-0.5"
                style={{ backgroundColor: bg, color: fg }}>
                {label}
              </span>
              <span className="text-gray-700">{r.description || r.id}</span>
            </div>
          );
        })}
      </div>

      <div className="flex gap-2">
        {spec.status !== "ACTIVE" && (
          <button onClick={onConfirm} disabled={!!busy}
            className="px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50"
            style={{ backgroundColor: "#16a34a" }}>
            Потвърди правилата
          </button>
        )}
        <button onClick={onGenerate} disabled={!!busy || spec.status !== "ACTIVE"}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50"
          style={{ backgroundColor: "#2c4a63" }}>
          {busy?.startsWith("Генерирам") ? busy : "Генерирай график"}
        </button>
      </div>
    </div>
  );
}

function VerificationCard({ summary, runId }: { summary: RunSummary; runId: string }) {
  const statusColor: Record<string, [string, string]> = {
    ok: ["#dcfce7", "#15803d"],
    relaxed: ["#fef3c7", "#b45309"],
    violated: ["#fee2e2", "#b91c1c"],
  };
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-gray-700">
          Проверка на правилата {summary.clean ? "✅" : "⚠️"}
        </h2>
        <div className="flex gap-2">
          <button onClick={() => downloadExport(runId, "xlsx")}
            className="px-3 py-1.5 rounded-lg border text-xs text-gray-600 hover:bg-gray-50">Excel</button>
          <button onClick={() => downloadExport(runId, "pdf")}
            className="px-3 py-1.5 rounded-lg border text-xs text-gray-600 hover:bg-gray-50">PDF</button>
        </div>
      </div>
      {summary.relaxed_rules_impossible_to_fully_satisfy.length > 0 && (
        <p className="text-xs text-amber-700 mb-2">
          Математически невъзможни за пълно спазване (минимизирани): {summary.relaxed_rules_impossible_to_fully_satisfy.join(", ")}
        </p>
      )}
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {summary.findings.map((f) => {
          const [bg, fg] = statusColor[f.status] ?? statusColor.ok;
          return (
            <div key={f.rule} className="flex items-center gap-2 text-xs">
              <span className="px-1.5 py-0.5 rounded font-medium" style={{ backgroundColor: bg, color: fg }}>
                {f.status === "ok" ? "OK" : f.status === "relaxed" ? `невъзможно ×${f.violations}` : `нарушено ×${f.violations}`}
              </span>
              <span className="text-gray-600 truncate">{f.rule}{f.detail && f.status !== "ok" ? ` — ${f.detail}` : ""}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ScheduleGrid({
  spec, assignments, findings,
}: {
  spec: SpecPayload;
  assignments: Assignment[];
  findings: RunSummary["findings"];
}) {
  const shiftById = new Map(spec.spec.shifts.map((s) => [s.id, s]));
  const staff = spec.overview.staff;
  const days = Array.from(new Set(assignments.map((a) => a.date))).sort();
  const grid = new Map(assignments.map((a) => [`${a.staff_id}|${a.date}`, a.shift_id]));
  const hasProblems = findings.some((f) => f.status !== "ok");

  const fmt = (m: number) => `${String(Math.floor((m % 1440) / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 overflow-x-auto">
      <h2 className="font-semibold text-gray-700 mb-3">График {hasProblems ? "" : "· всички правила спазени"}</h2>
      <table className="text-[11px] border-collapse w-full" style={{ minWidth: "700px" }}>
        <thead>
          <tr>
            <th className="px-2 py-1.5 text-left text-white sticky left-0" style={{ backgroundColor: "#1a2e44" }}>Служител</th>
            {days.map((d) => {
              const date = new Date(d);
              const wd = (date.getDay() + 6) % 7;
              return (
                <th key={d} className="px-1 py-1 text-center font-medium"
                  style={{ backgroundColor: wd >= 4 ? "#e8eef5" : "#eef2f7", color: "#555" }}>
                  <div>{DAY_NAMES_BG[wd]}</div>
                  <div className="text-gray-400 font-normal">{date.getDate()}</div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {staff.map((member) => (
            <tr key={member.id}>
              <td className="px-2 py-1 font-semibold text-gray-800 whitespace-nowrap sticky left-0 bg-white border-r">
                {member.name}
              </td>
              {days.map((d) => {
                const shiftId = grid.get(`${member.id}|${d}`);
                if (!shiftId || shiftId === "OFF") {
                  return (
                    <td key={d} className="border border-gray-100 text-center py-1 px-0.5 text-gray-400"
                      style={{ backgroundColor: "#f3f4f6" }}>
                      —
                    </td>
                  );
                }
                const shift = shiftById.get(shiftId);
                return (
                  <td key={d} className="border border-gray-100 text-center py-1 px-0.5"
                    style={{ backgroundColor: shift?.color_hex ?? "#f3f4f6", minWidth: "44px" }}>
                    {shift ? `${fmt(shift.start_min)}–${fmt(shift.end_min)}` : shiftId}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
