"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "../hooks/useCurrentUser";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const user = useCurrentUser();

  useEffect(() => {
    if (user.isError) router.replace("/login");
  }, [router, user.isError]);

  if (user.isPending) {
    return (
      <section className="page-message" aria-live="polite">
        <span className="eyebrow">StudyFlow</span>
        <h1>Opening your workspace</h1>
        <p>Checking your session…</p>
      </section>
    );
  }
  if (user.isError) return null;
  return children;
}
