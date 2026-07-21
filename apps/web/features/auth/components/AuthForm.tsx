"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { login, signup } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const isSignup = mode === "signup";
  const mutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      isSignup ? signup(email, password) : login(email, password),
    onSuccess: (user) => {
      queryClient.setQueryData(["current-user"], user);
      router.replace("/");
    },
    onError: (authError) => setError(authError.message),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      email: String(form.get("email") ?? ""),
      password: String(form.get("password") ?? ""),
    });
  }

  return (
    <section className="auth-page" aria-labelledby="auth-heading">
      <div className="auth-card">
        <span className="eyebrow">Your lecture workspace</span>
        <h1 id="auth-heading">{isSignup ? "Create your account" : "Welcome back"}</h1>
        <p>
          {isSignup
            ? "Keep your lectures private and return to them anytime."
            : "Sign in to continue to your adaptive lectures."}
        </p>
        <form onSubmit={submit}>
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            minLength={8}
            required
          />
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary-button" disabled={mutation.isPending} type="submit">
            {mutation.isPending
              ? "Please wait…"
              : isSignup
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
        <p className="auth-alternate">
          {isSignup ? "Already have an account?" : "New to StudyFlow?"}{" "}
          <Link href={isSignup ? "/login" : "/signup"}>
            {isSignup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </div>
    </section>
  );
}
