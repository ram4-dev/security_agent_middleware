import { cookies } from "next/headers";

export type Theme = "beam" | "ink" | "paper";

export const THEME_COOKIE = "tranquera_theme";

export function isTheme(v: unknown): v is Theme {
  return v === "beam" || v === "ink" || v === "paper";
}

export async function readThemeCookie(): Promise<Theme> {
  const c = (await cookies()).get(THEME_COOKIE)?.value;
  return isTheme(c) ? c : "ink";
}
