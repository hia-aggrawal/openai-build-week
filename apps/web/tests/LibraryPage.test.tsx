import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryPage from "@/app/library/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/features/auth/components/AuthGate", () => ({
  AuthGate: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/SiteHeader", () => ({ SiteHeader: () => <div>Header</div> }));
vi.mock("@/features/lecture-list/components/LectureList", () => ({
  LectureList: () => <div>Lecture list</div>,
}));
vi.mock("@/features/lecture-upload/components/LectureUpload", () => ({
  LectureUpload: ({
    compact,
    onCreated,
  }: {
    compact?: boolean;
    onCreated: (lectureId: string) => void;
  }) => (
    <button data-compact={compact} onClick={() => onCreated("lecture-from-dialog")}>
      Complete popup upload
    </button>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("library page", () => {
  it("opens the upload form in a dialog and navigates after completion", async () => {
    render(<LibraryPage />);

    const uploadControl = screen.getByRole("button", { name: "Upload a lecture" });
    expect(screen.queryByRole("link", { name: "Upload a lecture" })).not.toBeInTheDocument();
    fireEvent.click(uploadControl);

    const dialog = await screen.findByRole("dialog", { name: "Upload a lecture" });
    const complete = screen.getByRole("button", { name: "Complete popup upload" });
    expect(dialog).toContainElement(complete);
    expect(complete).toHaveAttribute("data-compact", "true");

    fireEvent.click(complete);

    expect(push).toHaveBeenCalledWith("/lectures/lecture-from-dialog");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
