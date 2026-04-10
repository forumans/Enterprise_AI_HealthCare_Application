import type { Role } from "../types";

export function requireRole(currentRole: Role, allowed: Role[]): string | null {
  if (!allowed.includes(currentRole)) {
    return `Access denied. Required role: ${allowed.join("/")}.`;
  }
  return null;
}
