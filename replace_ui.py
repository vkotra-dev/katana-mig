import re

with open("web/app/projects/[id]/feeds/[feedId]/page.tsx", "r") as f:
    content = f.read()

# 1. Remove fiberAiLogs, expandedAiLogs, inspectingAiLog, inspectAiActiveTab states
content = re.sub(r'const \[fiberAiLogs, setFiberAiLogs\] = useState[^\n]*\n', '', content)
content = re.sub(r'const \[expandedAiLogs, setExpandedAiLogs\] = useState[^\n]*\n', '', content)
content = re.sub(r'const \[inspectingAiLog, setInspectingAiLog\] = useState[^\n]*\n', '', content)
content = re.sub(r'const \[inspectAiActiveTab, setInspectAiActiveTab\] = useState[^\n]*\n', '', content)

# 2. Remove toggleAiLog function
content = re.sub(r'  const toggleAiLog = \(key: string\) => \{.*?  \};\n\n', '', content, flags=re.DOTALL)

# 3. Replace Feed level AI Prompt Logs (lines 798-858 approx)
content = re.sub(
    r'\{/\* AI Prompt Logs for feed \*/\}.*?(?=\s*</div>\s*</div>\s*</div>\s*\{/\* A\. Destination Object Tables \*/\})',
    '<AiLogViewer projectId={projectId} feature="feed_mapping" callType="source_analysis" artifactId={feedId} />',
    content,
    flags=re.DOTALL
)

# 4. Replace AI Trace & Reasoning (lines 923-964)
content = re.sub(
    r'\{snapshot\?.aiTrace && \(.*?</details>\s*</div>\s*\)',
    '<AiLogViewer projectId={projectId} feature="feed_mapping" callType="mapping" artifactId={snapshot.mappingSnapshotId} />',
    content,
    flags=re.DOTALL
)

# 5. Replace Domain Object AI Prompt Logs (lines 965-1022)
content = re.sub(
    r'\{/\* AI Prompt Logs \*/\}\s*\{\(role === "central_team" \|\| role === "admin"\) &&.*?\}\)\s*\}\s*</div>\s*\)',
    '<AiLogViewer projectId={projectId} feature="feed_mapping" callType="mapping" artifactId={fiber?.fiberId} />\n                            </>\n                          )}\n                        </div>\n                      );',
    content,
    flags=re.DOTALL
)

# 6. Replace Lookup Fiber AI Prompt Logs (lines 1211-1268)
content = re.sub(
    r'\{/\* AI Prompt Logs \*/\}\s*\{\(role === "central_team" \|\| role === "admin"\) &&\s*fiber && fiberAiLogs.*?\}\)\s*\}\s*</div>\s*\)',
    '<AiLogViewer projectId={projectId} feature="feed_mapping" artifactId={fiber?.fiberId} />\n                            </div>\n                          )}\n                        </div>\n                      );',
    content,
    flags=re.DOTALL
)

# 7. Remove inspectingAiLog Modal (lines 1283-1376)
content = re.sub(
    r'\{inspectingAiLog && \(.*?(?=\s*</main>)',
    '',
    content,
    flags=re.DOTALL
)

# 8. Add AiLogViewer import if missing and remove listAiCallLogs, AICallLogRecord
content = re.sub(
    r'import \{ listAiCallLogs, type AICallLogRecord \} from "(.*?)";',
    r'',
    content
)
if "import { AiLogViewer }" not in content:
    content = content.replace(
        'import { UnifiedCommentThread } from "../../../../../components/feeds/UnifiedCommentThread";',
        'import { UnifiedCommentThread } from "../../../../../components/feeds/UnifiedCommentThread";\nimport { AiLogViewer } from "../../../../../components/ai-logs/ai-log-viewer";'
    )

with open("web/app/projects/[id]/feeds/[feedId]/page.tsx", "w") as f:
    f.write(content)
