export const PASSWORD_POLICY_MESSAGE =
  "Use at least 10 characters and include at least 3 of these 4: lowercase, uppercase, number, symbol.";

export function getPasswordPolicyError(password: string): string | null {
  if (password.length < 10) {
    return "Password must be at least 10 characters.";
  }
  if (password.length > 512) {
    return "Password is too long.";
  }
  if (password !== password.trim()) {
    return "Password cannot start or end with whitespace.";
  }

  const categories = [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length;

  if (categories < 3) {
    return PASSWORD_POLICY_MESSAGE;
  }

  return null;
}
