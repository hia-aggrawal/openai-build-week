"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { deleteLecture, getLectures, retryLecture } from "@/lib/api";
import { formatTime } from "@/features/lecture-player/utils/playback";

const PAGE_SIZE = 6;

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function LectureList() {
  const queryClient = useQueryClient();
  const deleteDialogRef = useRef<HTMLDialogElement>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);
  const query = useInfiniteQuery({
    queryKey: ["lectures"],
    queryFn: ({ pageParam }) => getLectures(PAGE_SIZE, pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.next_offset ?? undefined,
  });
  const lectures = query.data?.pages.flatMap((page) => page.items) ?? [];
  const deleteMutation = useMutation({
    mutationFn: deleteLecture,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lectures"] }),
  });
  const retryMutation = useMutation({
    mutationFn: retryLecture,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lectures"] }),
  });

  useEffect(() => {
    const dialog = deleteDialogRef.current;
    if (!pendingDelete || !dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
  }, [pendingDelete]);

  function closeDeleteDialog() {
    const dialog = deleteDialogRef.current;
    if (dialog?.open && typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog?.removeAttribute("open");
    }
    setPendingDelete(null);
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const lectureId = pendingDelete.id;
    closeDeleteDialog();
    deleteMutation.mutate(lectureId);
  }

  return (
    <section
      className="lecture-list-section"
      id="your-lectures"
      aria-labelledby="library-heading"
    >
      {query.isPending && <p className="lecture-list-message">Loading past lectures…</p>}
      {query.isError && (
        <p className="lecture-list-message error" role="alert">
          {query.error.message}
        </p>
      )}
      {!query.isPending && !query.isError && lectures.length === 0 && (
        <div className="lecture-empty-state">
          <span className="eyebrow">Start your library</span>
          <h3>No lectures yet</h3>
          <p>
            Use Upload at the top of the page to add your first lecture. StudyFlow will move quickly
            through simple material while keeping dense concepts at a thoughtful pace.
          </p>
        </div>
      )}
      {lectures.length > 0 && (
        <div className="lecture-list">
          {lectures.map((lecture) => (
            <article className="lecture-list-item" key={lecture.id}>
              <div className="lecture-list-item-topline">
                <span className={`lecture-status lecture-status-${lecture.job_status.toLowerCase()}`}>
                  {lecture.job_status.toLowerCase()}
                </span>
                <div className="lecture-item-actions">
                  {lecture.job_status === "FAILED" && (
                    <button
                      className="lecture-action-button"
                      disabled={retryMutation.isPending}
                      onClick={() => retryMutation.mutate(lecture.id)}
                      type="button"
                    >
                      Retry
                    </button>
                  )}
                  <button
                    aria-label={`Delete ${lecture.title}`}
                    className="lecture-delete-button"
                    disabled={deleteMutation.isPending}
                    onClick={() => setPendingDelete({ id: lecture.id, title: lecture.title })}
                    type="button"
                  >
                    <svg aria-hidden="true" viewBox="0 0 20 20">
                      <path d="M4 5.5h12M8 5.5V3.75h4v1.75M6 5.5l.75 10.75h6.5L14 5.5M8.5 8.5v4.75M11.5 8.5v4.75" />
                    </svg>
                  </button>
                </div>
              </div>
              <Link href={`/lectures/${lecture.id}`} className="lecture-item-link">
                <h3>{lecture.title}</h3>
                <span className="lecture-list-meta">
                  {formatTime(lecture.duration_seconds)} · {dateFormatter.format(new Date(lecture.created_at))}
                </span>
              </Link>
            </article>
          ))}
        </div>
      )}
      {(deleteMutation.isError || retryMutation.isError) && (
        <p className="lecture-list-message error" role="alert">
          {(deleteMutation.error ?? retryMutation.error)?.message}
        </p>
      )}
      {query.hasNextPage && (
        <button
          className="text-button lecture-load-more"
          disabled={query.isFetchingNextPage}
          onClick={() => query.fetchNextPage()}
          type="button"
        >
          {query.isFetchingNextPage ? "Loading…" : "Load more lectures"}
        </button>
      )}
      {pendingDelete && (
        <dialog
          aria-describedby="delete-lecture-description"
          aria-labelledby="delete-lecture-heading"
          className="delete-lecture-dialog"
          onCancel={(event) => {
            event.preventDefault();
            closeDeleteDialog();
          }}
          onClose={() => setPendingDelete(null)}
          ref={deleteDialogRef}
        >
          <span className="eyebrow">Delete lecture</span>
          <h2 id="delete-lecture-heading">Remove this lecture?</h2>
          <p className="delete-lecture-title">“{pendingDelete.title}”</p>
          <p id="delete-lecture-description">
            This permanently removes the lecture and its uploaded video. This action can’t be
            undone.
          </p>
          <div className="delete-dialog-actions">
            <button
              autoFocus
              className="dialog-cancel-button"
              onClick={closeDeleteDialog}
              type="button"
            >
              Cancel
            </button>
            <button className="dialog-delete-button" onClick={confirmDelete} type="button">
              Delete
            </button>
          </div>
        </dialog>
      )}
    </section>
  );
}
