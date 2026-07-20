"use client";

import { use, useEffect, useMemo, useState, Fragment } from "react";
import { Topbar } from "../../../../components/Topbar";
import { ProjectNavigationTabs } from "../../../../components/projects/ProjectNavigationTabs";
import {
  downloadCodegenDeliveryBundle,
  getSchemaAnalysis,
  listCodegenArtifacts,
  triggerSchemaAnalysis,
  triggerCodegen,
  type CodegenArtifactRecord,
  type SchemaAnalysisRecord,
} from "../../../../lib/codegen-api";
import { listFeedContracts, saveTransformationInstructions, listFeedFibers, listFeedSlices, type FeedContractRecord, type FiberRecord } from "../../../../lib/feeds-api";
import { getProject, saveCodegenInstructions, type ProjectRecord } from "../../../../lib/projects-api";
import { getAllApprovedMappingSnapshots, type MappingSnapshotRecord } from "../../../../lib/mapping-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";

function formatDate(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function statusClassName(status: string): string {
  if (status === "active") {
    return "bg-emerald-100 text-emerald-900";
  }
  return "bg-slate-100 text-slate-700";
}

function latestActiveArtifact(artifacts: CodegenArtifactRecord[]): CodegenArtifactRecord | null {
  const active = artifacts.filter((artifact) => artifact.status === "active");
  const source = active.length > 0 ? active : artifacts;
  if (source.length === 0) {
    return null;
  }
  return [...source].sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0] ?? null;
}

function sourceDestinationLabel(source: FeedContractRecord): string {
  const refs = source.destinationObjectReferences ?? [];
  return refs.length > 0 ? refs.join(", ") : "Unassigned";
}

const generateCodingStandardsTemplate = (
  dbEngine: string,
  stagingSchema: string,
  destSchema: string
): string => {
  const engineName = dbEngine || "target database";
  const stg = stagingSchema || "staging";
  const dest = destSchema || "destination";

  let specificStandards = "";
  const lowerEngine = dbEngine?.toLowerCase() || "";
  if (lowerEngine === "postgresql") {
    specificStandards = `
     - Use standard PostgreSQL coding conventions: lowercase identifiers, snake_case for tables/columns, explicit type casting (e.g. ::date, ::integer).
     - Stored procedures/functions should be written in PL/pgSQL using dollar-quoting.`;
  } else if (lowerEngine === "mssql" || lowerEngine === "sqlserver") {
    specificStandards = `
     - Use T-SQL coding conventions: UPPERCASE SQL keywords, square brackets for identifiers only when necessary, proper schema qualifiers.
     - Always use CREATE OR ALTER PROCEDURE, never CREATE PROCEDURE alone. Scripts must be idempotent and runnable multiple times without error.
     - Every CREATE TABLE statement must be idempotent. Use IF OBJECT_ID(N'[schema].[table]', N'U') IS NULL before CREATE TABLE. Never emit an unconditional CREATE TABLE statement.

     **Migration SP Requirements:**
       1. SET XACT_ABORT ON immediately after SET NOCOUNT ON
       2. Validate source table is non-empty before MERGE; THROW if empty. The empty source validation THROW must occur before any MERGE statement executes.
       3. Use THROW not RAISERROR for all error raising (SQL Server 2012+)
       4. Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) for future-safe action logging. The CAST to NVARCHAR(255) is required to match the dest_row_id column type in mig_upsert_log. Use inserted and deleted pseudo-table aliases when logging destination-table column values in the OUTPUT clause. The MERGE source alias may be referenced only for source metadata such as source_row_num. Never use the target alias to retrieve the affected destination row identifier. OUTPUT INTO [oc_stag].[mig_upsert_log] must specify the explicit destination column list: ([run_ref], [dest_table], [source_row_num], [dest_row_id], [action]).
       5. NULL values in source columns flow through unchanged unless destination is NOT NULL
       6. Note index requirements on MERGE join key columns in comments
       7. FK lookups must be resolved via JOIN in MERGE source SELECT, not scalar variables. Every row gets its own resolved FK value.
       8. run_ref must be dynamically generated inside the procedure using OBJECT_NAME(@@PROCID) as the procedure name prefix combined with GETDATE() and NEWID(). Never accept as parameter, never hardcode.
          WRONG:  DECLARE @run_ref = '00000000-0000-4000-8000-...'
          CORRECT: DECLARE @run_ref NVARCHAR(255) = OBJECT_NAME(@@PROCID) + '_' + 
                   CONVERT(NVARCHAR(20), GETDATE(), 120) + '_' + 
                   CAST(NEWID() AS NVARCHAR(36));
       9. Schemas [cxp] and [oc_stag] are assumed to exist. Never create, drop, or alter schemas in procedures or migration scripts.
       10. Declare only variables that are used. Remove unused declarations.
       11. Never update the primary key column in WHEN MATCHED THEN UPDATE SET. The ON clause join key must never appear in the UPDATE column list.
       12. Verify bracket and parenthesis balance before outputting SQL.
       13. CRITICAL: System-managed row-level audit and technical columns that track creation or modification in THIS database — such as created_at, created_by, inserted_at, inserted_by, updated_at, updated_by, rowversion, and timestamp — must not be copied from the source or included in WHEN MATCHED THEN UPDATE SET unless the column is explicitly identified as source-system business data.

           Business date fields from the source system that represent original business event dates are legitimate update columns and should be included.

           If unsure whether a column is an audit timestamp or a business date, check the source DDL. Audit timestamps are typically auto-generated using DEFAULT GETDATE(), DEFAULT SYSUTCDATETIME(), rowversion, timestamp, or similar database-managed behavior and must not be overwritten on update.

           rowversion and SQL Server timestamp columns must not be explicitly inserted or updated.

           WRONG:  target.created_at = source.created_at
           WRONG:  target.inserted_by = source.inserted_by
           CORRECT: Omit created_at, inserted_by, and similar system-managed columns entirely from the UPDATE SET column list.
       14. THROW syntax must follow the correct T-SQL argument order: THROW error_number, message_string, state; Never swap the message and state arguments.
       15. CRITICAL: Every stored procedure must wrap all DML in TRY...CATCH with explicit transaction management: BEGIN TRY / BEGIN TRANSACTION ... COMMIT / END TRY then BEGIN CATCH / IF @@TRANCOUNT > 0 ROLLBACK / THROW / END CATCH.
       16. CRITICAL: ALL lookup tables created in the same script must be used by at least one relevant MERGE source SELECT via JOIN to resolve FK values per row — not just some of them. Never create lookup tables and then ignore them in the MERGE. Never alias a source column as an FK id — that is not a JOIN.

       The correct pattern is:
       USING (
           SELECT 
               s.*,
               lk1.[id] AS resolved_fk1_id,
               lk2.[id] AS resolved_fk2_id
           FROM [oc_stag].[source_table] s
           LEFT JOIN [oc_stag].[lookup_table_1] lk1 
               ON lk1.[code_column] = s.[source_code_column_1]
           LEFT JOIN [oc_stag].[lookup_table_2] lk2 
               ON lk2.[code_column] = s.[source_code_column_2]
           WHERE s.[pk_column] IS NOT NULL
       ) AS source

       Then reference source.resolved_fk1_id and source.resolved_fk2_id in the UPDATE SET and INSERT VALUES clauses instead of the raw source code columns.
       17. Every MERGE statement must include an OUTPUT clause logging to [oc_stag].[mig_upsert_log]. After all MERGEs complete, return a result set with run_ref, rows_inserted, rows_updated, completed_at derived from the log table.
       18. Duplicate source-key checks must be performed for every key or composite key used in the MERGE ON clause before executing MERGE. If duplicate source keys exist, THROW before MERGE. Also validate that required MERGE key columns are not NULL.
       19. Lookup seed data must be idempotent. Never emit unconditional INSERT statements for lookup rows. Use IF NOT EXISTS or INSERT ... WHERE NOT EXISTS so rerunning the script cannot create duplicate lookup values.
       20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or UNIQUE index.
       21. Before MERGE, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, THROW before executing MERGE. Preserve NULL only when the source value and destination FK are legitimately nullable.`;
  } else if (lowerEngine === "oracle") {
    specificStandards = `
     - Use PL/SQL coding conventions: UPPERCASE keywords/types, clear EXCEPTION blocks, schema-qualified table references.
     - All object names must respect Oracle length limits (max 30 or 128 characters depending on version).`;
  } else if (lowerEngine === "mysql") {
    specificStandards = `
     - Use standard MySQL coding conventions: backticks for reserved word identifiers, snake_case table/column names.
     - Stored procedures should use clear parameter scoping and DELIMITER declarations.`;
  }

  return `### Coding Standards and Guidelines

1. **Schemas and Scoping**:
   - Migration and utility stored procedures must be created under the staging schema, not the destination schema.
   - All destination tables must be created under the "${dest}" schema.
   - All staging and source tables must be read from the "${stg}" schema.
   - All DDL for lookup tables must be created in the "${stg}" schema.

2. **Database Engine Conventions (${engineName})**:
   - Write all DDL and stored procedures complying with the standard coding conventions pertinent to ${engineName}.${specificStandards}

3. **General Best Practices**:
   - Ensure all scripts are repeatable and idempotent. Use SQL Server-compatible idempotent patterns: CREATE OR ALTER for stored procedures and IF OBJECT_ID(...) IS NULL for tables. Do not drop and recreate persistent tables merely to make a script repeatable.
   - Use explicit column lists in all INSERT statements.
   - Do not hardcode environment-specific values. Do not create arbitrary default timestamps for business data columns. Database-managed audit columns, such as migration-log timestamps, may use an appropriate default when explicitly required by the schema.`;
};

const generateTransformationInstructionsTemplate = (
  feedLabel: string,
  rowCount: number,
  fibers: FiberRecord[],
  stagingSchema: string,
  snapshots: MappingSnapshotRecord[]
): string => {
  const approvedFibers = fibers.filter(
    f =>
      f.status === "business_approved" ||
      f.status === "operator_triggered" ||
      f.status === "codegen_complete" ||
      f.status === "active" ||
      f.status === "approved"
  );

  const lookupFibers = approvedFibers.filter(
    f => f.fiberType === "lookup"
  );

  const domainFibers = approvedFibers.filter(
    f => f.fiberType === "domain_object"
  );

  const schema = stagingSchema || "staging";

  let lookupSection = "\n### 1. Approved Lookup Data\n";

  if (lookupFibers.length === 0) {
    lookupSection +=
      "- No approved lookup data was identified for this feed.\n";
  } else {
    lookupFibers.forEach(fiber => {
      lookupSection += `- Approved lookup: "${fiber.fiberKey}"\n`;

      const mappings = fiber.proposedMappings ?? [];

      if (mappings.length === 0) {
        lookupSection += "  Approved mappings: none\n";
        return;
      }

      lookupSection += "  Approved mappings:\n";

      mappings.forEach(mapping => {
        const sourceValue = JSON.stringify(mapping.sourceValue);

        const destinationValue = mapping.destRow
          ? JSON.stringify(mapping.destRow)
          : (mapping.destEntryId ?? "null");

        lookupSection +=
          `    * Source value: ${sourceValue}` +
          ` -> Destination: ${destinationValue}\n`;
      });
    });
  }

  let mappingSection = "\n### 2. Approved Destination Mappings\n";

  mappingSection += `- Source table: "${schema}.${feedLabel}"\n`;

  if (domainFibers.length === 0) {
    mappingSection +=
      "- No approved destination mappings were identified for this feed.\n";
  } else {
    domainFibers.forEach(fiber => {
      const snapshot = snapshots.find(
        snap =>
          snap.destinationObjectName === fiber.fiberKey
      );

      const bindings =
        snapshot?.fieldBindings ?? fiber.fieldBindings ?? [];

      mappingSection +=
        `\n- Destination object: "${fiber.fiberKey}"\n`;

      if (bindings.length === 0) {
        mappingSection += "  Field bindings: none\n";
        return;
      }

      mappingSection += "  Field bindings:\n";

      bindings.forEach(binding => {
        const lookupText = binding.lookupName
          ? ` (Lookup: ${binding.lookupName})`
          : "";

        mappingSection +=
          `    * Source field "${binding.sourceField}"` +
          ` -> Destination column "${binding.destinationField}"` +
          `${lookupText}\n`;
      });
    });
  }

  const sourceCharacteristicsSection =
    "\n### 3. Source Characteristics\n" +
    `- Estimated source row count: ${rowCount}\n`;

  return `### Transformation Specification for Feed: ${feedLabel}
${lookupSection}
${mappingSection}
${sourceCharacteristicsSection}`;
};

export default function CodegenPage({ params }: { params: Promise<{ id: string }> }) {
  const [routeParams, setRouteParams] = useState<{ id: string } | null>(null);
  const [session, setSession] = useState<UiSession | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [sources, setSources] = useState<FeedContractRecord[]>([]);
  const [artifacts, setArtifacts] = useState<CodegenArtifactRecord[]>([]);
  const [schemaAnalysis, setSchemaAnalysis] = useState<SchemaAnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [analysisActionLoading, setAnalysisActionLoading] = useState(false);
  const [globalInstructions, setGlobalInstructions] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [expandedFeed, setExpandedFeed] = useState<string | null>(null);
  const [feedInstructions, setFeedInstructions] = useState<Record<string, string>>({});
  const [feedSaveLoading, setFeedSaveLoading] = useState<Record<string, boolean>>({});
  const [feedSuggestLoading, setFeedSuggestLoading] = useState<Record<string, boolean>>({});

  const [inspectingArtifact, setInspectingArtifact] = useState<CodegenArtifactRecord | null>(null);
  const [inspectActiveTab, setInspectActiveTab] = useState<"system" | "user" | "raw" | "sql">("system");

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve(params).then((resolved) => {
      if (active) {
        setRouteParams(resolved);
      }
    });
    return () => {
      active = false;
    };
  }, [params]);

  useEffect(() => {
    if (!session || !routeParams) {
      setLoading(true);
      return;
    }

    let active = true;
    setLoading(true);
    setPageError(null);
    setStatusMessage(null);

    void Promise.all([
      listFeedContracts(session.accessToken, routeParams.id),
      listCodegenArtifacts(session.accessToken, routeParams.id),
      getSchemaAnalysis(session.accessToken, routeParams.id),
      getProject(session.accessToken, routeParams.id),
    ])
      .then(([sourceResponse, artifactResponse, analysisResponse, projectResponse]) => {
        if (!active) {
          return;
        }
        setSources(sourceResponse);
        setArtifacts(artifactResponse);
        setSchemaAnalysis(analysisResponse);
        setProject(projectResponse);
        setGlobalInstructions(projectResponse.codegenInstructions ?? "");
      })
      .catch((error: unknown) => {
        if (active) {
          setPageError(error instanceof Error ? error.message : "Unable to load code generation.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [routeParams, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const latestArtifact = useMemo(() => latestActiveArtifact(artifacts), [artifacts]);
  const activeCount = useMemo(() => artifacts.filter((artifact) => artifact.status === "active").length, [artifacts]);
  const pendingCount = useMemo(() => {
    if (!schemaAnalysis) {
      return 0;
    }
    return Math.max(schemaAnalysis.identifiedCount - schemaAnalysis.processedCount, 0);
  }, [schemaAnalysis]);

  const refreshArtifacts = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    const response = await listCodegenArtifacts(session.accessToken, routeParams.id);
    setArtifacts(response);
  };

  const handleGenerate = async (sourceDefinitionId: string): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setActionLoading(sourceDefinitionId);
    setPageError(null);
    setStatusMessage(null);
    try {
      await triggerCodegen(session.accessToken, routeParams.id, sourceDefinitionId);
      await refreshArtifacts();
      setStatusMessage("Code generation completed.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to generate code.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReanalyze = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setPageError(null);
    setStatusMessage(null);
    setAnalysisActionLoading(true);
    try {
      const response = await triggerSchemaAnalysis(session.accessToken, routeParams.id);
      setSchemaAnalysis(response);
      setStatusMessage("Schema analysis completed.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to analyze destination schema.");
    } finally {
      setAnalysisActionLoading(false);
    }
  };

  const handleDownloadBundle = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setPageError(null);
    setStatusMessage(null);
    try {
      const sqlBundle = await downloadCodegenDeliveryBundle(session.accessToken, routeParams.id);
      const blob = new Blob([sqlBundle], { type: "text/plain" });
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = "delivery-bundle.sql";
      anchor.click();
      URL.revokeObjectURL(href);
      setStatusMessage("Delivery bundle downloaded.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to download delivery bundle.");
    }
  };

  const handleSuggestGlobalInstructions = () => {
    if (
      globalInstructions.trim() &&
      !window.confirm("This will overwrite your existing global instructions. Are you sure you want to proceed?")
    ) {
      return;
    }

    const engine = project?.domainConfig?.targetDbEngine || "";
    const staging = project?.domainConfig?.stagingSchema || "";
    const dest = project?.domainConfig?.destinationSchema || "";

    const template = generateCodingStandardsTemplate(engine, staging, dest);
    setGlobalInstructions(template.trim());
  };

  const handleSaveGlobalInstructions = async (): Promise<void> => {
    if (!session || !routeParams) return;
    setSaveLoading(true);
    setPageError(null);
    setStatusMessage(null);
    try {
      const updated = await saveCodegenInstructions(
        session.accessToken,
        routeParams.id,
        globalInstructions.trim() || null
      );
      setProject(updated);
      setGlobalInstructions(updated.codegenInstructions ?? "");
      setStatusMessage("Coding standards and global instructions saved.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to save coding standards.");
    } finally {
      setSaveLoading(false);
    }
  };

  const toggleExpandFeed = (feedId: string) => {
    if (expandedFeed === feedId) {
      setExpandedFeed(null);
    } else {
      setExpandedFeed(feedId);
      const source = sources.find((s) => s.sourceDefinitionId === feedId);
      if (source && feedInstructions[feedId] === undefined) {
        setFeedInstructions((prev) => ({
          ...prev,
          [feedId]: source.transformationInstructions ?? "",
        }));
      }
    }
  };

  const handleFeedInstructionsChange = (feedId: string, val: string) => {
    setFeedInstructions((prev) => ({
      ...prev,
      [feedId]: val,
    }));
  };

  const handleSaveFeedInstructions = async (feedId: string): Promise<void> => {
    if (!session || !routeParams) return;
    setFeedSaveLoading((prev) => ({ ...prev, [feedId]: true }));
    setPageError(null);
    setStatusMessage(null);
    try {
      const val = feedInstructions[feedId] ?? "";
      const updated = await saveTransformationInstructions(
        session.accessToken,
        routeParams.id,
        feedId,
        val.trim() || null
      );
      setSources((prev) =>
        prev.map((s) => (s.sourceDefinitionId === feedId ? updated : s))
      );
      setStatusMessage("Feed-specific transformation instructions saved.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to save transformation instructions.");
    } finally {
      setFeedSaveLoading((prev) => ({ ...prev, [feedId]: false }));
    }
  };

  const handleSuggestFeedInstructions = async (feedId: string, feedLabel: string): Promise<void> => {
    if (!session || !routeParams) return;

    const currentText = feedInstructions[feedId] ?? "";
    if (currentText.trim() && !window.confirm("This will overwrite your existing feed-specific instructions. Are you sure you want to proceed?")) {
      return;
    }

    setFeedSuggestLoading((prev) => ({ ...prev, [feedId]: true }));
    setPageError(null);
    setStatusMessage(null);
    try {
      const [fibers, slices, snapshots] = await Promise.all([
        listFeedFibers(session.accessToken, routeParams.id, feedId),
        listFeedSlices(session.accessToken, routeParams.id, feedId),
        getAllApprovedMappingSnapshots(session.accessToken, routeParams.id, feedId, true),
      ]);

      const activeSlice = slices.find((s) => s.status === "approved" || s.status === "active") || slices[0];
      const rowCount = activeSlice ? activeSlice.rowCount : 0;

      const staging = project?.domainConfig?.stagingSchema || "staging";
      const template = generateTransformationInstructionsTemplate(feedLabel, rowCount, fibers, staging, snapshots);
      setFeedInstructions((prev) => ({
        ...prev,
        [feedId]: template.trim(),
      }));
      setStatusMessage("Suggested transformation instructions generated based on fiber mappings and row count.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to suggest transformation instructions.");
    } finally {
      setFeedSuggestLoading((prev) => ({ ...prev, [feedId]: false }));
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Code Generation</p>
          <h1 className="text-3xl font-semibold text-slate-900">SQL bundle delivery</h1>
          <p className="max-w-3xl text-sm text-slate-600">
            Generate SQL from the approved mapping and source contract, review the latest active artifact, and
            download the delivery bundle for the project.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading code generation...
          </div>
        ) : pageError ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {pageError}
          </div>
        ) : session && routeParams ? (
          <>
            {statusMessage ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                {statusMessage}
              </div>
            ) : null}

            <ProjectNavigationTabs activeTab="sql-bundle" mode="codegen" projectId={routeParams.id} />

            <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-slate-900">Coding Standards & Global Instructions</h2>
                  <p className="text-sm text-slate-600">Applied to all feeds in this project during SQL generation.</p>
                </div>
                {(role === "central_team" || role === "admin") && (
                  <button
                    type="button"
                    className="rounded-lg border border-outline-variant bg-surface px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20"
                    onClick={handleSuggestGlobalInstructions}
                  >
                    Suggest Standards
                  </button>
                )}
              </div>
              <div className="space-y-2">
                <textarea
                  className="w-full rounded-lg border border-outline-variant bg-surface p-3 text-sm focus:border-primary focus:outline-none disabled:bg-slate-100 disabled:text-slate-500 font-sans"
                  rows={4}
                  placeholder="e.g. All date columns must use DATE type, never DATETIME. No default timestamps."
                  value={globalInstructions}
                  onChange={(e) => setGlobalInstructions(e.target.value)}
                  disabled={role !== "central_team" && role !== "admin"}
                />
                {(role === "central_team" || role === "admin") && (
                  <div className="flex justify-end">
                    <button
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:bg-slate-200 disabled:text-slate-400"
                      onClick={handleSaveGlobalInstructions}
                      disabled={saveLoading}
                    >
                      {saveLoading ? "Saving..." : "Save"}
                    </button>
                  </div>
                )}
              </div>
            </section>

            <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Sources</h2>
                <p className="text-sm text-slate-600">Generate SQL from each source contract.</p>
              </div>

              {sources.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No source contracts available.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Source</th>
                        <th className="px-4 py-3">Destination</th>
                        <th className="px-4 py-3">Encoding</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((source) => (
                        <Fragment key={source.sourceDefinitionId}>
                          <tr className="border-t border-outline-variant hover:bg-slate-50/50">
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <button
                                  type="button"
                                  className="p-1 text-slate-500 hover:text-slate-900 focus:outline-none"
                                  onClick={() => toggleExpandFeed(source.sourceDefinitionId)}
                                >
                                  <span
                                    className="inline-block transition-transform duration-200"
                                    style={{
                                      transform:
                                        expandedFeed === source.sourceDefinitionId
                                          ? "rotate(90deg)"
                                          : "rotate(0deg)",
                                    }}
                                  >
                                    ▶
                                  </span>
                                </button>
                                <div>
                                  <div className="text-sm font-semibold text-slate-900">{source.label}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-700">{sourceDestinationLabel(source)}</td>
                            <td className="px-4 py-3 text-sm text-slate-700">{source.encoding}</td>
                            <td className="px-4 py-3 text-sm text-slate-700">{source.status}</td>
                            <td className="px-4 py-3">
                              {role === "central_team" ? (
                                <button
                                  className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                                  disabled={actionLoading === source.sourceDefinitionId}
                                  onClick={() => void handleGenerate(source.sourceDefinitionId)}
                                  type="button"
                                >
                                  Generate SQL
                                </button>
                              ) : (
                                <span className="text-sm text-slate-500">No action</span>
                              )}
                            </td>
                          </tr>
                          {expandedFeed === source.sourceDefinitionId && (
                            <tr className="bg-slate-50 border-t border-outline-variant">
                              <td colSpan={5} className="px-8 py-4">
                                <div className="space-y-2">
                                  <h4 className="text-sm font-semibold text-slate-900">
                                    Feed-specific transformation instructions
                                  </h4>
                                  <textarea
                                    className="w-full rounded-lg border border-outline-variant bg-white p-3 text-sm focus:border-primary focus:outline-none disabled:bg-slate-100 disabled:text-slate-500 font-sans"
                                    rows={3}
                                    placeholder="e.g. Map claim_no -> external_claim_number; prepend 'OC' to form a 15-char claim ID."
                                    value={feedInstructions[source.sourceDefinitionId] ?? ""}
                                    onChange={(e) => handleFeedInstructionsChange(source.sourceDefinitionId, e.target.value)}
                                    disabled={role !== "central_team" && role !== "admin"}
                                  />
                                  {(role === "central_team" || role === "admin") && (
                                    <div className="flex justify-end gap-2">
                                      <button
                                        type="button"
                                        className="rounded-lg border border-outline-variant bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                                        onClick={() => void handleSuggestFeedInstructions(source.sourceDefinitionId, source.label)}
                                        disabled={feedSuggestLoading[source.sourceDefinitionId] || feedSaveLoading[source.sourceDefinitionId]}
                                      >
                                        {feedSuggestLoading[source.sourceDefinitionId] ? "Generating..." : "Generate Instructions"}
                                      </button>
                                      <button
                                        type="button"
                                        className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover disabled:bg-slate-200 disabled:text-slate-400"
                                        onClick={() => void handleSaveFeedInstructions(source.sourceDefinitionId)}
                                        disabled={feedSaveLoading[source.sourceDefinitionId] || feedSuggestLoading[source.sourceDefinitionId]}
                                      >
                                        {feedSaveLoading[source.sourceDefinitionId] ? "Saving..." : "Save"}
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900">Latest active artifact</h2>
                    <p className="text-sm text-slate-600">{activeCount} active artifact(s) in the project.</p>
                  </div>
                  {latestArtifact ? (
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClassName(latestArtifact.status)}`}>
                      {latestArtifact.status}
                    </span>
                  ) : null}
                </div>

                {latestArtifact ? (
                  <>
                    <div className="grid gap-3 text-sm text-slate-700 sm:grid-cols-2">
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Destination</div>
                        <div className="font-semibold text-slate-900">{latestArtifact.destinationObjectName}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Artifact ID</div>
                        <div className="mono-id">{latestArtifact.codegenArtifactId}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Created</div>
                        <div>{formatDate(latestArtifact.createdAt)}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Source slice</div>
                        <div>{latestArtifact.sourceSliceVersion ?? "—"}</div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700"
                        onClick={async () => {
                          await navigator.clipboard.writeText(latestArtifact.sqlBundle ?? "");
                          setStatusMessage("SQL bundle copied to clipboard.");
                        }}
                        type="button"
                      >
                        Copy SQL
                      </button>
                      <button
                        className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700"
                        onClick={() => void handleDownloadBundle()}
                        type="button"
                      >
                        Download delivery bundle
                      </button>
                    </div>

                    <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">SQL preview</div>
                        <button
                          type="button"
                          onClick={async () => {
                            await navigator.clipboard.writeText(latestArtifact.sqlBundle ?? "");
                            setStatusMessage("SQL bundle copied to clipboard.");
                          }}
                          className="rounded-md border border-outline bg-surface px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
                        >
                          Copy
                        </button>
                      </div>
                      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100">
                        {latestArtifact.sqlBundle ?? "No SQL bundle stored."}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                    No active code generation artifact yet.
                  </div>
                )}
              </div>

              <div className="space-y-6 flex flex-col">
                <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div>
                  <h2 className="text-xl font-semibold text-slate-900">Delivery bundle</h2>
                  <p className="text-sm text-slate-600">
                    Concatenated SQL for the active artifacts in this project.
                  </p>
                </div>

                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4 text-sm text-slate-700">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Active artifacts</div>
                  <div className="mt-2 text-2xl font-semibold text-slate-900">{activeCount}</div>
                </div>

                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-4 text-sm text-slate-600">
                  The download button above saves the bundle as <span className="font-mono">delivery-bundle.sql</span>.
                </div>
              </div>

              <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900">Schema dependency analysis</h2>
                    <p className="text-sm text-slate-600">
                      Counts how many destination objects were identified, processed, and are still pending.
                    </p>
                  </div>
                  {schemaAnalysis ? (
                    <button
                      className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                      disabled={analysisActionLoading}
                      onClick={() => void handleReanalyze()}
                      type="button"
                    >
                      Re-analyze DDL
                    </button>
                  ) : null}
                </div>

                {schemaAnalysis ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Identified</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-900">
                          {schemaAnalysis.identifiedCount}
                        </div>
                        <div className="text-sm text-slate-600">destination objects</div>
                      </div>
                      <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Processed</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-900">
                          {schemaAnalysis.processedCount}
                        </div>
                        <div className="text-sm text-slate-600">have active artifacts</div>
                      </div>
                      <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Pending</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-900">{pendingCount}</div>
                        <div className="text-sm text-slate-600">still need SQL generation</div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-4 text-sm text-slate-600">
                      Analyzed: {formatDate(schemaAnalysis.analyzedAt)}
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-4 text-sm text-slate-600">
                    No schema analysis yet. Add a source and click Analyze DDL to begin.
                  </div>
                )}
              </div>
            </div>
          </section>

            <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Artifact history</h2>
                <p className="text-sm text-slate-600">Active and superseded artifacts for the project.</p>
              </div>

              {artifacts.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No artifacts yet.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Destination</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Version</th>
                        <th className="px-4 py-3">Created</th>
                        <th className="px-4 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {artifacts.map((artifact) => (
                        <tr key={artifact.codegenArtifactId} className="border-t border-outline-variant">
                          <td className="px-4 py-3 text-sm text-slate-900">{artifact.destinationObjectName}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClassName(artifact.status)}`}>
                              {artifact.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-700">
                            {artifact.sourceSliceVersion ?? "—"} / {artifact.mappingSnapshotVersion ?? "—"}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-700">{formatDate(artifact.createdAt)}</td>
                          <td className="px-4 py-3 text-right">
                            <button
                              type="button"
                              onClick={() => {
                                setInspectingArtifact(artifact);
                                setInspectActiveTab("system");
                              }}
                              className="rounded-lg border border-outline bg-surface px-3 py-1.5 text-xs font-semibold text-primary hover:bg-slate-50 transition"
                            >
                              Inspect AI Logs
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        ) : null}
      </section>

      {inspectingArtifact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="flex h-[80vh] w-full max-w-4xl flex-col rounded-2xl border border-outline bg-surface-container shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4 bg-surface">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  Inspect AI Logs for {inspectingArtifact.destinationObjectName}
                </h3>
                <p className="text-xs text-slate-500">
                  Artifact ID: {inspectingArtifact.codegenArtifactId}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setInspectingArtifact(null)}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition"
              >
                ✕
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-outline-variant bg-surface px-6">
              {[
                { id: "system", label: "System Prompt" },
                { id: "user", label: "User Prompt" },
                { id: "raw", label: "Raw LLM JSON" },
                { id: "sql", label: "Assembled SQL" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setInspectActiveTab(tab.id as any)}
                  className={`border-b-2 px-4 py-3 text-sm font-semibold transition ${
                    inspectActiveTab === tab.id
                      ? "border-primary text-primary"
                      : "border-transparent text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content area */}
            <div className="flex-1 overflow-auto bg-surface-container-low p-6 font-mono text-sm text-slate-800 relative">
              <div className="absolute top-4 right-4 z-10">
                <button
                  type="button"
                  onClick={() => {
                    const textToCopy =
                      inspectActiveTab === "system"
                        ? inspectingArtifact.compiledSystemPrompt
                        : inspectActiveTab === "user"
                        ? inspectingArtifact.compiledUserPrompt
                        : inspectActiveTab === "raw"
                        ? inspectingArtifact.rawLlmResponse
                        : inspectingArtifact.sqlBundle;
                    if (textToCopy) {
                      navigator.clipboard.writeText(textToCopy);
                      alert("Copied to clipboard!");
                    }
                  }}
                  className="rounded-lg border border-outline bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-sm"
                >
                  Copy to clipboard
                </button>
              </div>

              {inspectActiveTab === "system" && (
                <pre className="whitespace-pre-wrap rounded-xl border border-outline-variant bg-surface p-4 overflow-auto max-h-full">
                  {inspectingArtifact.compiledSystemPrompt || "No system prompt logged for this version."}
                </pre>
              )}

              {inspectActiveTab === "user" && (
                <pre className="whitespace-pre-wrap rounded-xl border border-outline-variant bg-surface p-4 overflow-auto max-h-full">
                  {inspectingArtifact.compiledUserPrompt || "No user prompt logged for this version."}
                </pre>
              )}

              {inspectActiveTab === "raw" && (
                <pre className="whitespace-pre-wrap rounded-xl border border-outline-variant bg-surface p-4 overflow-auto max-h-full">
                  {inspectingArtifact.rawLlmResponse || "No raw model response logged for this version."}
                </pre>
              )}

              {inspectActiveTab === "sql" && (
                <pre className="whitespace-pre-wrap rounded-xl border border-outline-variant bg-surface p-4 overflow-auto max-h-full">
                  {inspectingArtifact.sqlBundle || "No SQL bundle logged for this version."}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
