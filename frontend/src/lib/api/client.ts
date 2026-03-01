export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  // Check cookie first, then localStorage
  const match = document.cookie.match(/(?:^|; )auth_token=([^;]*)/);
  if (match) return decodeURIComponent(match[1]);
  return localStorage.getItem("auth_token");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, res.statusText, message);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json();
}
