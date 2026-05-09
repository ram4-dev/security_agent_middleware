// Helpers para CLI tokens y device codes.
// El token plaintext se devuelve UNA SOLA VEZ al CLI (en el poll). En DB
// solo guardamos el sha256 — si lo perdés, no se puede recuperar.

import { createHash, randomBytes } from "node:crypto";

/** Genera un token opaco para el CLI. Formato: tk_<43 chars b64url>. */
export function generateCliToken(): string {
  const bytes = randomBytes(32);
  return `tk_${bytes.toString("base64url")}`;
}

/** sha256 hex del token — lo que persiste en DB. */
export function hashCliToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

/** device_code opaco (random hex 32 chars). */
export function generateDeviceCode(): string {
  return randomBytes(16).toString("hex");
}

/**
 * user_code legible (formato XXXX-XXXX, sin caracteres ambiguos como I/1/0/O).
 * El user lo ve en el CLI y lo pega/confirma en el browser.
 */
export function generateUserCode(): string {
  // Alfabeto sin ambigüedades visuales.
  const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = randomBytes(8);
  const chars = Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]);
  return `${chars.slice(0, 4).join("")}-${chars.slice(4).join("")}`;
}

export const DEVICE_CODE_TTL_MS = 10 * 60 * 1000; // 10 min
export const DEVICE_POLL_INTERVAL_S = 3;
