// Typed client for the copilot API (spec lifecycle, generation, SSE chat).

const API = process.env.NEXT_PUBLIC_API_URL;

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  };
}

export type ShiftOverview = {
  id: string;
  time: string;
  hours: number;
  preferred: boolean;
  days: number[] | null;
};

export type RuleOverview = {
  id: string;
  type: string;
  enforcement: "hard" | "soft";
  auto_repair: boolean;
  relaxable: boolean;
  description: string;
};

export type SpecOverview = {
  version: number;
  venue: string;
  horizon: { start: string; days: number };
  staff: { id: string; name: string }[];
  shifts: ShiftOverview[];
  rules: RuleOverview[];
};

export type SpecPayload = {
  id: string;
  version: number;
  status: string;
  summary: string | null;
  overview: SpecOverview;
  assumptions?: string[];
  spec: { shifts: { id: string; color_hex: string; start_min: number; end_min: number; label: string }[] };
};

export type Finding = {
  rule_id: string;
  rule_type: string;
  status: "ok" | "violated" | "relaxed";
  violations: number;
  cells: string[];
  message_en: string;
  message_bg: string;
};

export type Assignment = { staff_id: string; date: string; shift_id: string };

export type RunSummary = {
  status: string;
  clean: boolean;
  repair_iterations: number;
  escalated_rules: string[];
  relaxed_rules_impossible_to_fully_satisfy: string[];
  findings: { rule: string; status: string; violations: number; detail: string }[];
  per_staff: Record<string, { closing_shifts: number; weekend_closings: number; days_off: number }>;
};

export type GenerateResponse = {
  run_id: string;
  status: string;
  summary: RunSummary;
  assignments: Assignment[];
};

export async function parseBrief(body: {
  brief: string;
  start_date: string;
  num_days: number;
  staff_hint?: string;
}): Promise<SpecPayload> {
  const res = await fetch(`${API}/api/copilot/specs/parse`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export async function updateSpecFromBrief(specId: string, brief: string): Promise<SpecPayload> {
  const res = await fetch(`${API}/api/copilot/specs/${specId}/update`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ brief }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export async function confirmSpec(specId: string): Promise<void> {
  const res = await fetch(`${API}/api/copilot/specs/${specId}/confirm`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error(res.statusText);
}

export async function generateSchedule(specId: string): Promise<GenerateResponse> {
  const res = await fetch(`${API}/api/copilot/specs/${specId}/generate`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export function exportUrl(runId: string, format: "xlsx" | "pdf"): string {
  return `${API}/api/copilot/runs/${runId}/export.${format}`;
}

export async function downloadExport(runId: string, format: "xlsx" | "pdf") {
  const res = await fetch(exportUrl(runId, format), { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `grafik.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export type ChatEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string }
  | { type: "spec_updated"; version: number }
  | { type: "report"; summary: RunSummary }
  | { type: "done" };

export async function* chatStream(specId: string, message: string): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${API}/api/copilot/chat`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ spec_id: specId, message }),
  });
  if (!res.ok || !res.body) throw new Error(res.statusText);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6)) as ChatEvent;
      }
    }
  }
}
