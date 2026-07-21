import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProcessingStatus } from "@/features/lecture-processing/components/ProcessingStatus";
import type { ProcessingJob } from "@/lib/types";

const job: ProcessingJob = {
  id: "job-123",
  status: "PROCESSING",
  stage: "SEGMENTING",
  progress: 65,
  error_code: null,
  error_message: null,
};

describe("ProcessingStatus", () => {
  it("renders the current stage label and native progress value", () => {
    render(<ProcessingStatus job={job} />);

    expect(screen.getByRole("heading", { name: "Finding topic boundaries" })).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "65");
    expect(screen.getByText("65% complete")).toBeVisible();
  });
});
