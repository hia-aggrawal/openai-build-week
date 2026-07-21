import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/features/auth/components/AuthGate", () => ({
  AuthGate: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/SiteHeader", () => ({ SiteHeader: () => <div>Header</div> }));
vi.mock("@/features/lecture-upload/components/LectureUpload", () => ({
  LectureUpload: ({ onCreated }: { onCreated: (lectureId: string) => void }) => (
    <button onClick={() => onCreated("lecture-123")}>Upload experience</button>
  ),
}));

describe("home page", () => {
  it("hosts the upload experience and opens the created lecture", () => {
    render(<Home />);

    screen.getByRole("button", { name: "Upload experience" }).click();

    expect(push).toHaveBeenCalledWith("/lectures/lecture-123");
  });
});
