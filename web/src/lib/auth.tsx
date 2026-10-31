import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { Loading } from "../components/ui";
import { api, type AdminUser, type Owner } from "./api";

export const ME_KEY = ["me"] as const;
export const ADMIN_ME_KEY = ["admin", "me"] as const;

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => (await api<{ user: Owner | null }>("/api/auth/me")).user,
    staleTime: 60_000,
  });
}

export function useAdminMe() {
  return useQuery({
    queryKey: ADMIN_ME_KEY,
    queryFn: async () => (await api<{ admin: AdminUser | null }>("/api/admin/auth/me")).admin,
    staleTime: 60_000,
  });
}

export function RequireUser({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Loading />;
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const me = useAdminMe();
  if (me.isPending) return <Loading />;
  if (!me.data) return <Navigate to="/admin/login" replace />;
  return children;
}
