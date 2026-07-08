// Canonical role keys — stored as `role_label` and looked up via the
// "roles" message namespace for a translated display label. Free-text
// roles (picked via "Other…") are stored verbatim and shown as-is.
export const ROLE_KEYS = [
  "bartender",
  "waiter",
  "barista",
  "cook",
  "cashier",
  "host",
  "cleaner",
  "security",
  "receptionist",
  "sales_associate",
  "manager",
  "delivery_driver",
];

export const OTHER_ROLE = "__other__";
