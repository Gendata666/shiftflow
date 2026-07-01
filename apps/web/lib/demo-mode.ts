export const DEMO_TOKEN = "demo_mode_active";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("access_token") === DEMO_TOKEN;
}

export function enterDemoMode() {
  localStorage.setItem("access_token", DEMO_TOKEN);
  localStorage.setItem("refresh_token", DEMO_TOKEN);
}

export function exitDemoMode() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}
