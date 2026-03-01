export interface AdminUser {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlatformStat {
  label: string;
  value: string | number;
  icon: string;
  trend?: {
    value: number;
    direction: "up" | "down" | "flat";
  };
}

export interface SystemHealth {
  service: string;
  status: "healthy" | "degraded" | "down";
  uptime?: string;
  last_check?: string;
}
