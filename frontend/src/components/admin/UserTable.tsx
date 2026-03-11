"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Search,
  ShieldCheck,
  ShieldOff,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { AdminUser } from "@/types/admin";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";

const PAGE_SIZE = 10;

export function UserTable() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [toggling, setToggling] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const data = await apiFetch<any>("/api/admin/users");
      setUsers(Array.isArray(data) ? data : data.users || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const toggleAdmin = async (userId: number, currentAdmin: boolean) => {
    setToggling(userId);
    try {
      await apiFetch(`/api/admin/users/${userId}/toggle-admin`, {
        method: "POST",
        body: JSON.stringify({ is_admin: !currentAdmin }),
      });
      setUsers((prev) =>
        prev.map((user) =>
          user.id === userId ? { ...user, is_admin: !currentAdmin } : user
        )
      );
    } finally {
      setToggling(null);
    }
  };

  const filtered = users.filter(
    (user) =>
      user.email.toLowerCase().includes(search.toLowerCase()) ||
      user.display_name.toLowerCase().includes(search.toLowerCase())
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  useEffect(() => {
    setPage(0);
  }, [search]);

  if (loading) {
    return (
      <div className="app-table-shell">
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-panel p-6">
        <div className="flex items-center gap-2 text-amber-300">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm">{error}</span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          The admin users endpoint may not be available. Ensure the backend has
          the admin routes enabled before relying on this screen.
        </p>
      </div>
    );
  }

  return (
    <div className="app-table-shell">
      <div className="app-section-header flex-col items-start sm:flex-row sm:items-center">
        <div>
          <h3 className="text-sm font-semibold">
            Users
            <span className="ml-2 font-normal text-muted-foreground">
              {filtered.length}
            </span>
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Manage elevated access and verify account posture.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search by email or name..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="h-10 rounded-full pl-9 pr-3"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="app-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Display Name</th>
              <th>Admin</th>
              <th>Verified</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    title={search ? "No matching users" : "No users found"}
                    description="Search results and user rows will appear here once accounts exist."
                    className="py-10"
                  />
                </td>
              </tr>
            ) : (
              paginated.map((user) => (
                <tr key={user.id}>
                  <td className="font-mono text-xs">{user.email}</td>
                  <td>{user.display_name}</td>
                  <td>
                    {user.is_admin ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-300">
                        <ShieldCheck className="h-3 w-3" />
                        Admin
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">User</span>
                    )}
                  </td>
                  <td>
                    {user.email_verified ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                    ) : (
                      <XCircle className="h-4 w-4 text-muted-foreground" />
                    )}
                  </td>
                  <td className="text-xs text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <Button
                      onClick={() => toggleAdmin(user.id, user.is_admin)}
                      disabled={toggling === user.id}
                      variant="secondary"
                      size="sm"
                      className="h-9 rounded-full px-3"
                    >
                      {toggling === user.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : user.is_admin ? (
                        <>
                          <ShieldOff className="h-3 w-3" />
                          Remove Admin
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="h-3 w-3" />
                          Make Admin
                        </>
                      )}
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="app-section-header border-t-0">
          <span className="text-xs text-muted-foreground">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => setPage((current) => Math.max(0, current - 1))}
              disabled={page === 0}
              variant="ghost"
              size="icon"
              className="h-9 w-9"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              onClick={() =>
                setPage((current) => Math.min(totalPages - 1, current + 1))
              }
              disabled={page >= totalPages - 1}
              variant="ghost"
              size="icon"
              className="h-9 w-9"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
