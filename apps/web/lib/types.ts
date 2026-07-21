export type ProcessingStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface User {
  id: string;
  email: string;
}

export interface ProcessingJob {
  id: string;
  status: ProcessingStatus;
  stage: string;
  progress: number;
  error_code: string | null;
  error_message: string | null;
}

export interface TranscriptSegment {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface PlaybackSegment {
  start_seconds: number;
  end_seconds: number;
  playback_rate: number;
  complexity_score: number;
  category: string;
  reason: string;
}

export interface Lecture {
  id: string;
  title: string;
  duration_seconds: number;
  video_url: string;
  captions_url: string;
  job: ProcessingJob;
  transcript: TranscriptSegment[] | null;
  playback_profile: PlaybackSegment[] | null;
}

export interface LectureSummary {
  id: string;
  title: string;
  duration_seconds: number;
  created_at: string;
  job_status: ProcessingStatus;
}

export interface LectureListPage {
  items: LectureSummary[];
  limit: number;
  offset: number;
  next_offset: number | null;
}

export interface LectureCreated {
  lecture_id: string;
  job_id: string;
  status: ProcessingStatus;
  duplicate: boolean;
}
