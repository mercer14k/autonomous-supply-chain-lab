export function getToken() {
  return sessionStorage.getItem("lab-operator-token") || "local-demo-token";
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${getToken()}`,
    ...(options.headers as Record<string, string>),
  };
  if (options.method === "POST" && !(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (options.method === "POST")
    headers["Idempotency-Key"] = crypto.randomUUID();
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      body.error?.message ||
        body.errors?.[0]?.message ||
        `Request failed (${response.status})`,
    );
  return body as T;
}
export const money = (value: number | undefined) =>
  value === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(value);
export const number = (value: number | undefined) =>
  value === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
        value,
      );
export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`;
export function download(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
