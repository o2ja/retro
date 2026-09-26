"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Banner,
  ConfirmButton,
  EmptyRow,
  Field,
  PageHeader,
  Panel,
  Toast,
  Toggle,
  formatDate,
  useToast,
} from "@/components/admin/ui";
import { archivePost, createPost, listPosts, updatePost } from "@/lib/admin";
import type { Post } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const BLANK = {
  id: 0,
  title: "",
  excerpt: "",
  content: "",
  category: "",
  author_name: "Retro Watches",
  cover_image_url: "",
  featured: false,
};

export default function AdminJournalPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [draft, setDraft] = useState({ ...BLANK });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    listPosts({ page_size: 50 })
      .then((result) => {
        setPosts(result.items);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load posts."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (key: string, value: unknown) =>
    setDraft((current) => ({ ...current, [key]: value as never }));

  function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const body = {
      title: draft.title,
      excerpt: draft.excerpt || null,
      content: draft.content || null,
      category: draft.category || null,
      author_name: draft.author_name || null,
      cover_image_url: draft.cover_image_url || null,
      featured: draft.featured,
    };
    const action = draft.id ? updatePost(draft.id, body) : createPost(body);
    action
      .then(() => {
        setDraft({ ...BLANK });
        load();
        setToast({ kind: "success", text: draft.id ? "Post saved." : "Draft created." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not save.",
        }),
      )
      .finally(() => setBusy(false));
  }

  function setStatus(post: Post, status: "DRAFT" | "PUBLISHED") {
    updatePost(post.id, { status })
      .then(() => {
        load();
        setToast({
          kind: "success",
          text: status === "PUBLISHED" ? "Published; it is live now." : "Unpublished.",
        });
      })
      .catch(() => setToast({ kind: "error", text: "Could not change the status." }));
  }

  return (
    <>
      <PageHeader
        title="Journal"
        description="Only published posts appear on the storefront."
      />

      {error && <Banner kind="error">{error}</Banner>}

      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        <Panel title="Posts">
          {posts.length === 0 ? (
            <EmptyRow>Nothing written yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-line">
              {posts.map((post) => (
                <li key={post.id} className="px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 flex-1 truncate">{post.title}</span>
                    <span
                      className={`text-xs ${
                        post.status === "PUBLISHED" ? "text-success" : "text-ink-subtle"
                      }`}
                    >
                      {post.status.toLowerCase()}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-ink-subtle">
                    {post.category ?? "Uncategorised"} ·{" "}
                    {post.published_at
                      ? `published ${formatDate(post.published_at)}`
                      : "not published"}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() =>
                        setDraft({
                          id: post.id,
                          title: post.title,
                          excerpt: post.excerpt ?? "",
                          content: post.content ?? "",
                          category: post.category ?? "",
                          author_name: post.author_name ?? "",
                          cover_image_url: post.cover_image_url ?? "",
                          featured: post.featured,
                        })
                      }
                      className="underline underline-offset-4"
                    >
                      Edit
                    </button>
                    {post.status === "PUBLISHED" ? (
                      <button
                        type="button"
                        onClick={() => setStatus(post, "DRAFT")}
                        className="underline underline-offset-4"
                      >
                        Unpublish
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setStatus(post, "PUBLISHED")}
                        className="underline underline-offset-4"
                      >
                        Publish
                      </button>
                    )}
                    {post.status !== "ARCHIVED" && (
                      <ConfirmButton
                        label="Archive"
                        question="Archive this post?"
                        onConfirm={() =>
                          archivePost(post.id).then(load).catch(() => undefined)
                        }
                      />
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title={draft.id ? "Edit post" : "New post"}>
          <form onSubmit={save} className="space-y-4 px-4 py-4">
            <Field label="Title *">
              <input
                required
                value={draft.title}
                onChange={(event) => set("title", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Category">
              <input
                value={draft.category}
                onChange={(event) => set("category", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Author">
              <input
                value={draft.author_name}
                onChange={(event) => set("author_name", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Cover image URL">
              <input
                value={draft.cover_image_url}
                onChange={(event) => set("cover_image_url", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Excerpt">
              <textarea
                rows={3}
                value={draft.excerpt}
                onChange={(event) => set("excerpt", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Content" hint="Blank lines separate paragraphs">
              <textarea
                rows={10}
                value={draft.content}
                onChange={(event) => set("content", event.target.value)}
                className="field"
              />
            </Field>
            <Toggle
              label="Featured"
              checked={draft.featured}
              onChange={(value) => set("featured", value)}
            />
            <div className="flex gap-2">
              <button type="submit" disabled={busy} className="btn btn-primary flex-1">
                {busy ? "Saving…" : draft.id ? "Save post" : "Create draft"}
              </button>
              {draft.id > 0 && (
                <button
                  type="button"
                  onClick={() => setDraft({ ...BLANK })}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </Panel>
      </div>

      <Toast toast={toast} />
    </>
  );
}
