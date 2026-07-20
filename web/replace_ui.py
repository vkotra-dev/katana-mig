import re

with open("app/projects/[id]/feeds/[feedId]/page.tsx", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
i = 0
while i < len(lines):
    line = lines[i]
    if "import { listAiCallLogs, type AICallLogRecord } from" in line:
        new_lines.append(line.replace('import { listAiCallLogs, type AICallLogRecord }', ''))
        i += 1
        continue
        
    if "import { UnifiedCommentThread }" in line:
        new_lines.append(line)
        new_lines.append('import { AiLogViewer } from "../../../../../components/ai-logs/AiLogViewer";\n')
        i += 1
        continue
        
    if "import { AiLogViewer } from " in line:
        # Avoid duplicate
        i += 1
        continue

    if "const [fiberAiLogs, setFiberAiLogs] = useState" in line:
        i += 1
        continue
    if "const [expandedAiLogs, setExpandedAiLogs] = useState" in line:
        i += 1
        continue
    if "const [inspectingAiLog, setInspectingAiLog] = useState" in line:
        i += 1
        continue
    if "const [inspectAiActiveTab, setInspectAiActiveTab] = useState" in line:
        i += 1
        continue

    # Remove the listAiCallLogs block inside submitLookupInputs
    if "const logs = await listAiCallLogs(" in line:
        i += 4
        continue
        
    if "const toggleAiLog = (key: string) => {" in line:
        i += 7
        continue

    # 1. feedId AI Prompt Logs
    if "{/* AI Prompt Logs for feed */}" in line:
        new_lines.append(line)
        new_lines.append('                <AiLogViewer token={session?.accessToken} projectId={projectId} feature="feed_mapping" callType="source_analysis" artifactId={feedId} canViewLogs={role === "central_team" || role === "admin"} />\n')
        i += 1
        while i < len(lines) and "{/* A. Destination Object Tables */}" not in lines[i]:
            i += 1
        continue

    # 2. AI Trace & Reasoning
    if "{snapshot?.aiTrace && (" in line:
        new_lines.append('                              <AiLogViewer token={session?.accessToken} projectId={projectId} feature="feed_mapping" callType="mapping" artifactId={snapshot.mappingSnapshotId} canViewLogs={role === "central_team" || role === "admin"} />\n')
        i += 1
        while i < len(lines) and "                              )}" not in lines[i]:
            i += 1
        i += 1
        continue

    # 3. Domain Object AI Prompt Logs
    if "{/* AI Prompt Logs */}" in line and "fiber && fiberAiLogs[fiber.fiberId]" in lines[i+2]:
        # we replaced ai trace with AiLogViewer anyway, wait, we don't need two of them for domain object.
        # Oh, the requirement said: "replace the in-progress inline grid/modal (currently uncommitted in page.tsx, covering feed_analysis and lookup_mapping only) with <AiLogViewer.../>... plus a new instance per destination-object table card scoped to call_type=mapping, artifactId=mappingSnapshotId"
        # and "Delete the legacy AI Trace & Reasoning <details> panel — the new mapping-scoped viewer instance replaces it."
        # This means the Domain Object AI Prompt Logs (which might be what lines 965-1022 are, or maybe there are none for domain object? Oh wait, lines 965-1022 *are* Domain Object Prompt Logs!). We should remove lines 965-1022 completely or replace them with the one we already added? The prompt says "delete the legacy AI Trace & Reasoning... the new mapping-scoped viewer instance replaces it." So we replace `aiTrace` with the `<AiLogViewer>`, and delete the inline grid. Wait, if the inline grid is for `fiberAiLogs`, we just delete it! But wait, `fiberAiLogs` for domain object? Wait, the domain object fiber has `fiber.fiberId`. Do we need a viewer for the fiber or for the mapping snapshot?
        # The prompt says: "plus a new instance per destination-object table card scoped to call_type=mapping, artifactId=mappingSnapshotId". So we don't need the one for `fiber.fiberId` in the domain object loop? Actually the prompt says "scoped per artifact as before (feed-level, per domain_object fiber, per lookup fiber)". 
        # But wait! A domain object is a fiber! So it has a fiber AI prompt log AND a mappingSnapshot AI trace.
        # If I need to just delete the inline grid and replace it with AiLogViewer:
        new_lines.append('                              <AiLogViewer token={session?.accessToken} projectId={projectId} feature="feed_mapping" callType="mapping" artifactId={fiber?.fiberId} canViewLogs={role === "central_team" || role === "admin"} />\n')
        i += 1
        while i < len(lines) and "                              )}" not in lines[i]:
            i += 1
        i += 1
        continue

    # 4. Lookup AI Prompt Logs
    if "{/* AI Prompt Logs */}" in line and "fiber && fiberAiLogs[fiber.fiberId]" in lines[i+2]:
        new_lines.append('                              <AiLogViewer token={session?.accessToken} projectId={projectId} feature="feed_mapping" callType="lookup_mapping" artifactId={fiber?.fiberId} canViewLogs={role === "central_team" || role === "admin"} />\n')
        i += 1
        while i < len(lines) and "                              )}" not in lines[i]:
            i += 1
        i += 1
        continue

    # 5. inspectingAiLog modal
    if "{inspectingAiLog && (" in line:
        i += 1
        while i < len(lines) and "      )}" not in lines[i]:
            i += 1
        i += 1
        continue

    new_lines.append(line)
    i += 1

with open("app/projects/[id]/feeds/[feedId]/page.tsx", "w") as f:
    f.writelines(new_lines)
