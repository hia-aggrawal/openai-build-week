"use client";

import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api";
import { useCurrentUser } from "@/features/auth/hooks/useCurrentUser";

export function SiteHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const user = useCurrentUser();
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["current-user"] });
      router.replace("/login");
    },
  });

  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="StudyFlow home">
        <span className="brand-mark">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M4 5 9 12 4 19M11 7 15 12 11 17M17 9 20 12 17 15" />
          </svg>
        </span>
        StudyFlow
      </Link>
      {user.data ? (
        <div className="header-account">
          {pathname !== "/library" && (
            <Link className="header-library-link" href="/library">
              Library
            </Link>
          )}
          <button
            className="text-button"
            disabled={logoutMutation.isPending}
            onClick={() => logoutMutation.mutate()}
            type="button"
          >
            {logoutMutation.isPending ? "Signing out…" : "Log out"}
          </button>
        </div>
      ) : (
        <span className="tagline">Learn at the pace of the idea.</span>
      )}
    </header>
  );
}
