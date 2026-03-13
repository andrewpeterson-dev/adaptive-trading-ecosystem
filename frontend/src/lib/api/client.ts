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

const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);
const MAX_RETRIES = 2;
const DEFAULT_TIMEOUT_MS = 30_000;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

// ── In-memory GET cache with TTL ────────────────────────────────────────
const _cache = new Map<string, { data: unknown; expiresAt: number }>();
const _inflight = new Map<string, Promise<unknown>>();
const DEFAULT_CACHE_TTL_MS = 5_000; // 5s — prevents redundant calls within polling cycles

function getCached<T>(key: string): T | null {
  const entry = _cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    _cache.delete(key);
    return null;
  }
  return entry.data as T;
}

/** Invalidate cache entries whose keys contain the given substring. */
export function invalidateCache(pathSubstring?: string): void {
  if (!pathSubstring) {
    _cache.clear();
    return;
  }
  Array.from(_cache.keys()).forEach((key) => {
    if (key.includes(pathSubstring)) _cache.delete(key);
  });
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function shouldAttachJsonContentType(body: BodyInit | null | undefined): boolean {
  if (!body) return false;
  if (typeof FormData !== "undefined" && body instanceof FormData) return false;
  if (typeof Blob !== "undefined" && body instanceof Blob) return false;
  if (typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams) return false;
  return true;
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number; maxRetries?: number; cacheTtlMs?: number } = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, maxRetries = MAX_RETRIES, cacheTtlMs = DEFAULT_CACHE_TTL_MS, ...fetchOptions } = options;
  const method = (fetchOptions.method || "GET").toUpperCase();
  const isGet = method === "GET" && !fetchOptions.body;

  // Return cached response for GET requests
  if (isGet) {
    const cached = getCached<T>(path);
    if (cached !== null) return cached;
    // Deduplicate concurrent identical GET requests
    const pending = _inflight.get(path);
    if (pending) return pending as Promise<T>;
  }

  const doFetch = async (): Promise<T> => {
    try {
      return await _apiFetchInner<T>(path, { ...fetchOptions, timeoutMs, maxRetries });
    } finally {
      _inflight.delete(path);
    }
  };

  if (isGet) {
    const promise = doFetch().then((data) => {
      if (cacheTtlMs > 0) {
        _cache.set(path, { data, expiresAt: Date.now() + cacheTtlMs });
      }
      return data;
    });
    _inflight.set(path, promise);
    return promise;
  }

  // Invalidate relevant caches on mutations
  const segment = path.split("/").slice(0, 4).join("/");
  invalidateCache(segment);

  return _apiFetchInner<T>(path, { ...fetchOptions, timeoutMs, maxRetries });
}

async function _apiFetchInner<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number; maxRetries?: number } = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, maxRetries = MAX_RETRIES, ...fetchOptions } = options;
  const method = (fetchOptions.method || "GET").toUpperCase();
  const headers = new Headers(fetchOptions.headers);

  if (!headers.has("Content-Type") && shouldAttachJsonContentType(fetchOptions.body)) {
    headers.set("Content-Type", "application/json");
  }

  if (!SAFE_METHODS.has(method) && !headers.has("X-CSRF-Token")) {
    const csrfToken = getCookie("csrf_token");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  // Only retry idempotent methods or explicit opt-in
  const canRetry = method === "GET" || method === "HEAD" || maxRetries > MAX_RETRIES;

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= (canRetry ? maxRetries : 0); attempt++) {
    try {
      const res = await fetchWithTimeout(
        path,
        {
          ...fetchOptions,
          headers,
          credentials: fetchOptions.credentials ?? "include",
        },
        timeoutMs
      );

      if (!res.ok) {
        // Retry on transient server errors for safe methods
        if (canRetry && RETRYABLE_STATUS_CODES.has(res.status) && attempt < maxRetries) {
          const delay = Math.min(1000 * 2 ** attempt, 8000);
          await new Promise((r) => setTimeout(r, delay));
          continue;
        }

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
    } catch (e) {
      lastError = e as Error;
      // Don't retry non-retryable errors or mutations
      if (e instanceof ApiError || !canRetry || attempt >= maxRetries) throw e;
      // Retry on network/timeout errors
      if (e instanceof DOMException && e.name === "AbortError") {
        lastError = new ApiError(408, "Request Timeout", "Request timed out");
      }
      const delay = Math.min(1000 * 2 ** attempt, 8000);
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  throw lastError || new Error("Request failed");
}
