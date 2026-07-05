"use client";

import { useRouter } from "next/navigation";

export type ProjectTabKey = "overview" | "feeds" | "artifacts" | "sql-bundle";

interface ProjectNavigationTabsProps {
  activeTab: ProjectTabKey;
  mode: "detail" | "codegen";
  projectId: string;
  onTabChange?: (tab: Exclude<ProjectTabKey, "sql-bundle">) => void;
}

const tabBase = "rounded-full px-4 py-2 text-sm font-semibold";
const tabInactive = "border border-outline-variant bg-surface-container text-slate-700";
const tabActive = "bg-primary text-white";

export function ProjectNavigationTabs({ activeTab, mode, onTabChange, projectId }: ProjectNavigationTabsProps) {
  const router = useRouter();
  const tabs: Array<{ key: ProjectTabKey; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "feeds", label: "Feeds" },
    { key: "artifacts", label: "Artifacts" },
    { key: "sql-bundle", label: "SQL Bundle" },
  ];

  return (
    <div className="flex gap-2">
      {tabs.map((tab) => {
        const isActive = tab.key === activeTab;
        const className = `${tabBase} ${isActive ? tabActive : tabInactive}`;

        const handleClick = () => {
          if (mode === "detail") {
            if (tab.key === "sql-bundle") {
              router.push(`/projects/${projectId}/codegen`);
              return;
            }

            onTabChange?.(tab.key);
            return;
          }

          if (tab.key !== "sql-bundle") {
            router.push(`/projects/${projectId}`);
          }
        };

        return (
          <button
            key={tab.key}
            className={className}
            disabled={mode === "codegen" && isActive}
            onClick={handleClick}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
