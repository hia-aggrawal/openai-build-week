import { afterEach, describe, expect, it, vi } from "vitest";
import { uploadLecture } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("uploadLecture", () => {
  it("initializes, uploads sequential chunks directly, reports progress, and completes", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({ upload_id: "upload-123", expected_chunk_count: 2 }, 201),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            lecture_id: "lecture-123",
            job_id: "job-123",
            status: "QUEUED",
            duplicate: false,
          },
          202,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const progress: number[] = [];
    const file = new File([new Uint8Array(8 * 1024 * 1024), new Uint8Array(2)], "lecture.mp4", {
      type: "video/mp4",
    });

    const result = await uploadLecture(file, "Chunked lecture", 120, (value) =>
      progress.push(value),
    );

    expect(result).toEqual({
      lecture_id: "lecture-123",
      job_id: "job-123",
      status: "QUEUED",
      duplicate: false,
    });
    expect(progress).toEqual([0, 50, 100]);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/lectures/uploads");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://localhost:8000/api/lectures/uploads/upload-123/chunks/0",
    );
    expect(fetchMock.mock.calls[2][0]).toBe(
      "http://localhost:8000/api/lectures/uploads/upload-123/chunks/1",
    );
    expect(fetchMock.mock.calls[3][0]).toBe(
      "/api/lectures/uploads/upload-123/complete",
    );
    expect(fetchMock.mock.calls[1][1]?.body).toBeInstanceOf(Blob);
    expect((fetchMock.mock.calls[1][1]?.body as Blob).size).toBe(8 * 1024 * 1024);
    expect((fetchMock.mock.calls[2][1]?.body as Blob).size).toBe(2);
  });

  it("retries a failed chunk once", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({ upload_id: "upload-123", expected_chunk_count: 1 }, 201),
      )
      .mockRejectedValueOnce(new TypeError("network failure"))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            lecture_id: "lecture-123",
            job_id: "job-123",
            status: "QUEUED",
            duplicate: false,
          },
          202,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await uploadLecture(new File(["video"], "lecture.mp4", { type: "video/mp4" }), "", 60);

    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/chunks/0"))).toHaveLength(
      2,
    );
  });
});
