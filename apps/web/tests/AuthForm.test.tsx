import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthForm } from "@/features/auth/components/AuthForm";
import { login, signup } from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", () => ({ login: vi.fn(), signup: vi.fn() }));

function renderForm(mode: "login" | "signup") {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthForm mode={mode} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthForm", () => {
  it.each([
    ["signup", "Create account", signup],
    ["login", "Sign in", login],
  ] as const)("submits the %s flow", async (mode, button, request) => {
    vi.mocked(request).mockResolvedValue({ id: "user-1", email: "person@example.com" });
    renderForm(mode);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: button }));

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("person@example.com", "password123"),
    );
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("shows an authentication error", async () => {
    vi.mocked(login).mockRejectedValue(new Error("Email or password is incorrect."));
    renderForm("login");
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong-password" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect.",
    );
  });
});
