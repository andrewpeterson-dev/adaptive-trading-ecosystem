export interface User {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_verified: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginResponse {
  user: User;
}

export interface RegisterResponse {
  success: boolean;
  verification_required?: boolean;
  email?: string;
  email_sent?: boolean;
  message?: string;
  development_verification_url?: string | null;
  user?: User;
}

export interface PasswordResetRequestResponse {
  success: boolean;
  email_sent?: boolean;
  message: string;
  development_reset_url?: string | null;
}

export interface AuthActionResponse {
  success: boolean;
  message?: string;
}

export interface WebSocketTokenResponse {
  token: string;
  expires_in: number;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
