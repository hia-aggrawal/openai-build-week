"use client";

import { useParams, useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { LectureExperience } from "@/features/lecture-player/components/LectureExperience";
import { AuthGate } from "@/features/auth/components/AuthGate";

export default function LecturePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  return (
    <AuthGate>
      <main>
        <SiteHeader />
        <LectureExperience lectureId={params.id} onStartOver={() => router.push("/")} />
      </main>
    </AuthGate>
  );
}
