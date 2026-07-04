"use client";

import { useEffect, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";

export interface ProjectResourcesEditorProps {
  value: string;
  onChange: (html: string) => void;
}

export function ProjectResourcesEditor({ value, onChange }: ProjectResourcesEditorProps) {
  const [mounted, setMounted] = useState(false);
  const editor = useEditor({
    extensions: [StarterKit, TextAlign.configure({ types: ["heading", "paragraph"] })],
    content: value,
    onUpdate({ editor: currentEditor }) {
      onChange(currentEditor.getHTML());
    },
    immediatelyRender: false,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!editor || !mounted) {
      return;
    }
    const currentHtml = editor.getHTML();
    if (value !== currentHtml) {
      editor.commands.setContent(value, false);
    }
  }, [editor, mounted, value]);

  return (
    <div className="overflow-hidden rounded-md border border-outline-variant bg-white">
      <div className="flex flex-wrap gap-2 border-b border-outline-variant bg-surface px-2 py-2">
        <button
          type="button"
          aria-label="Bold"
          title="Bold"
          className={`inline-flex h-10 w-10 items-center justify-center rounded-lg border text-slate-700 transition hover:-translate-y-px hover:bg-surface-container ${
            editor?.isActive("bold")
              ? "border-primary bg-primary-container text-on-primary-container"
              : "border-outline-variant bg-white"
          }`}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
            <path
              d="M7 5h6.5a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z"
              fill="currentColor"
            />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Bullet list"
          title="Bullet list"
          className={`inline-flex h-10 w-10 items-center justify-center rounded-lg border text-slate-700 transition hover:-translate-y-px hover:bg-surface-container ${
            editor?.isActive("bulletList")
              ? "border-primary bg-primary-container text-on-primary-container"
              : "border-outline-variant bg-white"
          }`}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
            <path
              d="M8 7.5h11M8 12h11M8 16.5h11M4.5 7.5h.01M4.5 12h.01M4.5 16.5h.01"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="1.8"
            />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Center"
          title="Center"
          className={`inline-flex h-10 w-10 items-center justify-center rounded-lg border text-slate-700 transition hover:-translate-y-px hover:bg-surface-container ${
            editor?.isActive({ textAlign: "center" })
              ? "border-primary bg-primary-container text-on-primary-container"
              : "border-outline-variant bg-white"
          }`}
          onClick={() => editor?.chain().focus().setTextAlign("center").run()}
        >
          <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
            <path
              d="M6 7h12M8 11h8M6 15h12M7 19h10"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="1.8"
            />
          </svg>
        </button>
      </div>
      <EditorContent
        editor={editor}
        className="min-h-56 px-4 py-3 text-sm text-slate-900 focus-within:outline-none [&_.ProseMirror]:min-h-48 [&_.ProseMirror]:outline-none"
      />
    </div>
  );
}
