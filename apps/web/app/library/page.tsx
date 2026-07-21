"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { AuthGate } from "@/features/auth/components/AuthGate";
import { LectureList } from "@/features/lecture-list/components/LectureList";
import { LectureUpload } from "@/features/lecture-upload/components/LectureUpload";

export default function LibraryPage() {
  const router = useRouter();
  const uploadDialogRef = useRef<HTMLDialogElement>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    const dialog = uploadDialogRef.current;
    if (!uploadOpen || !dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
  }, [uploadOpen]);

  function closeUploadDialog() {
    const dialog = uploadDialogRef.current;
    if (dialog?.open && typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog?.removeAttribute("open");
    }
    setUploadOpen(false);
  }

  function openLecture(lectureId: string) {
    closeUploadDialog();
    router.push(`/lectures/${lectureId}`);
  }

  return (
    <AuthGate>
      <main>
        <SiteHeader />
        <section className="library-intro" aria-labelledby="library-heading">
          <div>
            <span className="eyebrow">Library</span>
            <h1 id="library-heading">Your lectures</h1>
            <p>Return to completed lectures or follow one that is still being prepared.</p>
          </div>
          <button
            aria-label="Upload a lecture"
            className="library-add-button"
            onClick={() => setUploadOpen(true)}
            type="button"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20">
              <path d="M4 10h12M10 4v12" />
            </svg>
          </button>
        </section>
        <LectureList />
        {uploadOpen && (
          <dialog
            aria-label="Upload a lecture"
            className="library-upload-dialog"
            onCancel={(event) => {
              event.preventDefault();
              closeUploadDialog();
            }}
            onClose={() => setUploadOpen(false)}
            ref={uploadDialogRef}
          >
            <button
              aria-label="Close upload dialog"
              className="dialog-close-button"
              onClick={closeUploadDialog}
              type="button"
            >
              <svg aria-hidden="true" viewBox="0 0 20 20">
                <path d="M5 5l10 10M15 5 5 15" />
              </svg>
            </button>
            <LectureUpload compact onCreated={openLecture} />
          </dialog>
        )}
      </main>
    </AuthGate>
  );
}
