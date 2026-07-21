import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AuthGate } from "@/features/auth/components/AuthGate";
import { useCurrentUser } from "@/features/auth/hooks/useCurrentUser";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/features/auth/hooks/useCurrentUser", () => ({ useCurrentUser: vi.fn() }));

describe("AuthGate", () => {
  it("redirects a logged-out visitor to login", async () => {
    vi.mocked(useCurrentUser).mockReturnValue({ isPending: false, isError: true } as ReturnType<
      typeof useCurrentUser
    >);

    render(<AuthGate>Private content</AuthGate>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });
});
