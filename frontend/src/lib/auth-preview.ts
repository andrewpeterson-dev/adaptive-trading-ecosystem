const VERIFICATION_PREVIEW_KEY = "auth:verification-preview-url";
const RESET_PREVIEW_KEY = "auth:reset-preview-url";

function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function stashValue(key: string, value?: string | null): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  if (!value) {
    storage.removeItem(key);
    return;
  }
  storage.setItem(key, value);
}

function consumeValue(key: string): string | null {
  const storage = getStorage();
  if (!storage) {
    return null;
  }
  const value = storage.getItem(key);
  if (value) {
    storage.removeItem(key);
  }
  return value;
}

export function stashVerificationPreviewUrl(value?: string | null): void {
  stashValue(VERIFICATION_PREVIEW_KEY, value);
}

export function consumeVerificationPreviewUrl(): string | null {
  return consumeValue(VERIFICATION_PREVIEW_KEY);
}

export function stashResetPreviewUrl(value?: string | null): void {
  stashValue(RESET_PREVIEW_KEY, value);
}

export function consumeResetPreviewUrl(): string | null {
  return consumeValue(RESET_PREVIEW_KEY);
}
