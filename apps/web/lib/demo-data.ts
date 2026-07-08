// Beach bar demo — exact schedule from gen_grafik.py (verified: 0 BAD sequences)

export const DEMO_TENANT = "Beach Bar Demo";
export const DEMO_VENUE  = "Main Beach Bar";

export const DEMO_STAFF = [
  { id: "s1", name: "Васил",    role_label: "Bartender", contract_hours: 84, color: "#6366f1", active: true },
  { id: "s2", name: "Ники",     role_label: "Bartender", contract_hours: 84, color: "#0ea5e9", active: true },
  { id: "s3", name: "Джедая",   role_label: "Bartender", contract_hours: 84, color: "#10b981", active: true },
  { id: "s4", name: "Афродита", role_label: "Bartender", contract_hours: 84, color: "#f59e0b", active: true },
];

export const DEMO_SHIFT_TYPES: Record<string, { label: string; hours: number; start: string; end: string; color: string }> = {
  A: { label: "08:00–16:00",  hours: 8,  start: "08:00", end: "16:00", color: "#B3D9FF" },
  B: { label: "16:00–00:00",  hours: 8,  start: "16:00", end: "00:00", color: "#B3D9FF" },
  C: { label: "10:00–20:00",  hours: 10, start: "10:00", end: "20:00", color: "#FFD580" },
  D: { label: "14:00–00:00",  hours: 10, start: "14:00", end: "00:00", color: "#FFD580" },
  E: { label: "08:00–20:00",  hours: 12, start: "08:00", end: "20:00", color: "#90EE90" },
  F: { label: "12:00–00:00",  hours: 12, start: "12:00", end: "00:00", color: "#FFA07A" },
};

// 28-day schedule, Mon 7 Jul – Sun 3 Aug 2026
// Codes: A=08-16/8h  B=16-00/8h  C=10-20/10h  D=14-00/10h  E=08-20/12h  F=12-00/12h
export const DEMO_SCHEDULE: Record<string, string[]> = {
  s1: "BDCAFFFCABCEEEADBFFFFCABCEEE".split(""),  // Васил — fixed to 28 chars
  s2: "CADBFFFCBCAEEECABCEEEADBFFFF".split(""),  // Ники
  s3: "CABCEEEACBDFFFDBCAFFFDBCAEEE".split(""),  // Джедая
  s4: "AACCEEE BCADFFFBCCAEEECABDFFF".replace(" ","").split(""),  // Афродита
};

// Use the verified schedule from gen_grafik.py (correct 28-char arrays)
export const DEMO_SCHEDULE_VERIFIED: Record<string, string[]> = {
  s1: "B D C A F F F  C A B C E E E  C A D B F F F  C A B C E E E".split(/\s+/).filter(Boolean),
  s2: "C A D B F F F  C B C A E E E  C A B C E E E  C A D B F F F".split(/\s+/).filter(Boolean),
  s3: "C A B C E E E  A C B D F F F  D B C A F F F  D B C A E E E".split(/\s+/).filter(Boolean),
  s4: "A A C C E E E  B C A D F F F  B C C A E E E  C A B D F F F".split(/\s+/).filter(Boolean),
};

export const DEMO_START_DATE = new Date("2026-07-06"); // Monday

export function getDemoDate(dayIndex: number): Date {
  const d = new Date(DEMO_START_DATE);
  d.setDate(d.getDate() + dayIndex);
  return d;
}

export const DAY_NAMES_BG = ["Пон", "Вт", "Ср", "Чет", "Пет", "Съб", "Нед"];
export const DAY_NAMES_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const DEMO_PREFERENCES = [
  {
    id: "p1",
    staff_name: "Афродита",
    source: "TELEGRAM",
    type: "OFF_REQUEST",
    target_dates: ["2026-07-18"],
    raw_message: "Не мога в събота 18 юли, имам семейно събитие",
    notes: "Off request for Saturday July 18",
    status: "PENDING",
    created_at: "2026-07-01T10:23:00Z",
  },
  {
    id: "p2",
    staff_name: "Ники",
    source: "TELEGRAM",
    type: "PREFERRED_SHIFT",
    target_dates: ["2026-07-14", "2026-07-15", "2026-07-16"],
    raw_message: "Предпочитам ранна смяна тази неделя ако е възможно",
    notes: "Preferred morning shift for the weekend of July 14-16",
    status: "PENDING",
    created_at: "2026-07-01T09:11:00Z",
  },
  {
    id: "p3",
    staff_name: "Васил",
    source: "WHATSAPP",
    type: "UNAVAILABLE",
    target_dates: ["2026-07-21"],
    raw_message: "Вземам един ден отпуска на 21 юли",
    notes: "Day off on July 21",
    status: "APPROVED",
    created_at: "2026-06-28T14:05:00Z",
  },
];

export const DEMO_ANALYTICS = DEMO_STAFF.map((s) => {
  const shifts = DEMO_SCHEDULE_VERIFIED[s.id];
  const cnt: Record<number, number> = { 8: 0, 10: 0, 12: 0 };
  shifts.forEach((code) => {
    const h = DEMO_SHIFT_TYPES[code]?.hours;
    if (h) cnt[h] = (cnt[h] || 0) + 1;
  });
  const total = Object.entries(cnt).reduce((sum, [h, n]) => sum + +h * n, 0);
  return {
    id: s.id,
    name: s.name,
    days_worked: shifts.length,
    total_hours: total,
    shifts_by_duration: cnt,
  };
});
