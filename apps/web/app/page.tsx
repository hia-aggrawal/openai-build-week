"use client";

import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { AuthGate } from "@/features/auth/components/AuthGate";
import { LectureUpload } from "@/features/lecture-upload/components/LectureUpload";

export default function Home() {
  const router = useRouter();

  return (
    <AuthGate>
      <main>
        <SiteHeader />
        <LectureUpload onCreated={(lectureId) => router.push(`/lectures/${lectureId}`)} />
      </main>
    </AuthGate>
  );
}
