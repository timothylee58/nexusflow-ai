const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const DEFAULT_ORG = process.env.NEXT_PUBLIC_ORG_ID ?? "default";

export function getOrgId(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("nexusflow_org_id") ?? DEFAULT_ORG;
  }
  return DEFAULT_ORG;
}

export function setOrgId(orgId: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("nexusflow_org_id", orgId);
  }
}

export async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (API_KEY) headers.set("Authorization", `Bearer ${API_KEY}`);
  headers.set("X-Org-ID", getOrgId());
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(input, { ...init, headers });
}
