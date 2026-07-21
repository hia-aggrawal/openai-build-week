import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SiteHeader } from "@/components/SiteHeader";
import { useCurrentUser } from "@/features/auth/hooks/useCurrentUser";

const replace = vi.fn();
const pathname = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => pathname(),
  useRouter: () => ({ replace }),
}));
vi.mock("@/features/auth/hooks/useCurrentUser", () => ({ useCurrentUser: vi.fn() }));
vi.mock("@/lib/api", () => ({ logout: vi.fn() }));

function renderHeader() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <SiteHeader />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useCurrentUser).mockReturnValue({
    data: { id: "user-1", email: "person@example.com" },
  } as ReturnType<typeof useCurrentUser>);
});

describe("SiteHeader", () => {
  it("links to the library from non-library pages", () => {
    pathname.mockReturnValue("/lectures/lecture-123");
    renderHeader();

    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute("href", "/library");
    expect(screen.getByRole("link", { name: "StudyFlow home" })).toHaveAttribute("href", "/");
  });

  it("does not link to the current library page", () => {
    pathname.mockReturnValue("/library");
    renderHeader();

    expect(screen.queryByRole("link", { name: "Library" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "StudyFlow home" })).toHaveAttribute("href", "/");
  });
});
