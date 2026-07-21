import type { Lecture, LectureCreated, LectureListPage, User } from "./types";

interface ApiErrorBody {
  error?: { message?: string };
}

interface UploadSession {
  upload_id: string;
  expected_chunk_count: number;
}

const UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024;
const publicApiOrigin = (process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(body.error?.message ?? "Something went wrong. Please try again.");
  }
  return response.json() as Promise<T>;
}

export async function signup(email: string, password: string): Promise<User> {
  return parseResponse<User>(
    await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  );
}

export async function login(email: string, password: string): Promise<User> {
  return parseResponse<User>(
    await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  );
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/logout", { method: "POST" });
  if (!response.ok) await parseResponse<never>(response);
}

export async function getCurrentUser(): Promise<User> {
  return parseResponse<User>(await fetch("/api/auth/me"));
}

async function putChunkWithRetry(url: string, chunk: Blob): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/octet-stream" },
        body: chunk,
      });
      if (response.ok) return;
      if (attempt === 1) await parseResponse<never>(response);
    } catch (error) {
      if (attempt === 1) throw error;
    }
  }
}

export async function uploadLecture(
  file: File,
  title: string,
  duration: number,
  onProgress?: (percentage: number) => void,
) {
  const session = await parseResponse<UploadSession>(
    await fetch("/api/lectures/uploads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type,
        total_size: file.size,
        chunk_size: UPLOAD_CHUNK_SIZE,
      }),
    }),
  );

  onProgress?.(0);
  for (let index = 0; index < session.expected_chunk_count; index += 1) {
    const chunk = file.slice(index * UPLOAD_CHUNK_SIZE, (index + 1) * UPLOAD_CHUNK_SIZE);
    await putChunkWithRetry(
      `${publicApiOrigin}/api/lectures/uploads/${session.upload_id}/chunks/${index}`,
      chunk,
    );
    onProgress?.(Math.round(((index + 1) / session.expected_chunk_count) * 100));
  }

  return parseResponse<LectureCreated>(
    await fetch(`/api/lectures/uploads/${session.upload_id}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, duration_seconds: duration }),
    }),
  );
}

export async function getLecture(lectureId: string): Promise<Lecture> {
  return parseResponse<Lecture>(await fetch(`/api/lectures/${lectureId}`));
}

export async function getLectures(limit: number, offset: number): Promise<LectureListPage> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return parseResponse<LectureListPage>(await fetch(`/api/lectures?${query}`));
}

export async function deleteLecture(lectureId: string): Promise<void> {
  const response = await fetch(`/api/lectures/${lectureId}`, { method: "DELETE" });
  if (!response.ok) await parseResponse<never>(response);
}

export async function retryLecture(lectureId: string): Promise<LectureCreated> {
  return parseResponse<LectureCreated>(
    await fetch(`/api/lectures/${lectureId}/retry`, { method: "POST" }),
  );
}
