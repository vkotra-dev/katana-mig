/**
 * Helper to split a CSV row string into individual column values,
 * correctly handling commas within double quotes (e.g. "Smith, Jr.")
 * and stripping outer double quotes.
 */
export function splitCsvRow(row: string): string[] {
  return row.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map((val) => {
    let cleaned = val.trim();
    if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
      cleaned = cleaned.slice(1, -1);
    }
    return cleaned;
  });
}
