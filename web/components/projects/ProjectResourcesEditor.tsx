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
      editor.commands.setContent(value, { emitUpdate: false });
    }
  }, [editor, mounted, value]);

  return (
    <div className="overflow-hidden rounded-md border border-outline-variant bg-white">
      <div className="flex flex-wrap gap-2 border-b border-outline-variant bg-surface px-2 py-2">
        <button
          type="button"
          aria-label="Bold"
          className={`rounded px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-surface-container ${
            editor?.isActive("bold") ? "bg-surface-container" : ""
          }`}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          Bold
        </button>
        <button
          type="button"
          aria-label="Bullet list"
          className={`rounded px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-surface-container ${
            editor?.isActive("bulletList") ? "bg-surface-container" : ""
          }`}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          Bullet list
        </button>
        <button
          type="button"
          aria-label="Center"
          className={`rounded px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-surface-container ${
            editor?.isActive({ textAlign: "center" }) ? "bg-surface-container" : ""
          }`}
          onClick={() => editor?.chain().focus().setTextAlign("center").run()}
        >
          Center
        </button>
      </div>
      <EditorContent
        editor={editor}
        className="min-h-56 px-4 py-3 text-sm text-slate-900 focus-within:outline-none [&_.ProseMirror]:min-h-48 [&_.ProseMirror]:outline-none"
      />
    </div>
  );
}
