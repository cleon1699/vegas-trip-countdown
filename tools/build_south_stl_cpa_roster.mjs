import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/south_stl_county_cpa_roster");
const outputXlsx = path.join(outputDir, "south_stl_county_cpa_firm_roster.xlsx");
const outputCsv = path.join(outputDir, "south_stl_county_cpa_firm_roster.csv");

const verificationDate = "2026-06-30";
const zipCodes = ["63123", "63125", "63126", "63127", "63128", "63129"];
const rosterHeaders = [
  "Firm Name",
  "License/Registration Number",
  "License Status",
  "Address",
  "City",
  "State",
  "ZIP",
  "Phone",
  "Website",
  "Source URL",
  "Verification Date",
  "Notes",
];

const requestText = [
  "Subject: Sunshine Law request - active Missouri CPA firm licensees in South St. Louis County ZIP codes",
  "",
  "Missouri State Board of Accountancy:",
  "",
  "Pursuant to Missouri's Sunshine Law, please provide an electronic copy, preferably CSV or Excel, of all active CPA firm licensees/registrants with a physical or mailing address in any of the following ZIP codes: 63123, 63125, 63126, 63127, 63128, and 63129.",
  "",
  "Please include, to the extent maintained in the licensing system, firm name, license or registration number, license type, current license status, issue date, expiration date, public address, city, state, ZIP code, public phone number, public email address, website if maintained, and any DBA or branch-office indicator.",
  "",
  "If the requested records are maintained in a database, please export the responsive fields directly from that system rather than providing screenshots or PDFs. If any field is exempt from disclosure, please provide the non-exempt fields and cite the statutory basis for each redaction.",
  "",
  "Please let me know in advance if fulfilling this request will incur any charge. If the Board maintains an existing downloadable roster or public report that contains the responsive records, a link to that file is acceptable.",
  "",
  "Thank you.",
].join("\n");

function styleTitle(sheet, range) {
  range.format = {
    fill: "#1F4E5F",
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };
  range.format.rowHeight = 28;
}

function styleHeader(range) {
  range.format = {
    fill: "#D9EAF7",
    font: { bold: true, color: "#17324D" },
    borders: { preset: "outside", style: "thin", color: "#9FB8C8" },
  };
  range.format.wrapText = true;
}

function styleNoteBlock(range) {
  range.format = {
    fill: "#F7F9FB",
    borders: { preset: "outside", style: "thin", color: "#C8D3DC" },
  };
  range.format.wrapText = true;
}

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const roster = workbook.worksheets.add("CPA Firm Roster");
const methodology = workbook.worksheets.add("Methodology");
const request = workbook.worksheets.add("Records Request");

for (const sheet of [summary, roster, methodology, request]) {
  sheet.showGridLines = false;
}

summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["South St. Louis County CPA Firm Roster"]];
styleTitle(summary, summary.getRange("A1:H1"));
summary.getRange("A3:B9").values = [
  ["Verification date", verificationDate],
  ["Scope", "Licensed CPA firms/offices, not individual CPAs"],
  ["ZIP codes", zipCodes.join(", ")],
  ["Official source", "Missouri Division of Professional Registration / Missouri State Board of Accountancy"],
  ["Roster status", "Pending official data export or Board response"],
  ["Why no firm rows are prefilled", "The public Salesforce/MOPRO license portal is searchable but did not expose an auditable bulk export or zip-filtered listing during implementation."],
  ["Next action", "Send the Sunshine Law request in the Records Request sheet to mosba@pr.mo.gov."],
];
summary.getRange("A3:A9").format = { font: { bold: true }, fill: "#EAF2F8" };
summary.getRange("A3:B9").format.borders = { preset: "insideHorizontal", style: "thin", color: "#D4DCE3" };
summary.getRange("A3:B9").format.wrapText = true;
summary.getRange("A11:H11").merge();
summary.getRange("A11").values = [["Acceptance checklist"]];
styleHeader(summary.getRange("A11:H11"));
summary.getRange("A12:C17").values = [
  ["Check", "Status", "Notes"],
  ["Official license source identified", "Complete", "Missouri Board of Accountancy and MOPRO license portal documented."],
  ["ZIP filter defined", "Complete", zipCodes.join(", ")],
  ["Rows include only active official records", "Pending", "No rows included until Board/export supplies authoritative active-firm records."],
  ["Duplicate checks", "Ready", "Use license number first, then normalized firm name/address."],
  ["Secondary verification", "Ready", "Use firm websites/public listings only after official license records are received."],
];
styleHeader(summary.getRange("A12:C12"));
summary.getRange("A13:C17").format.borders = { preset: "insideHorizontal", style: "thin", color: "#E1E7EC" };
summary.getRange("A13:C17").format.wrapText = true;

roster.getRange("A1:L1").values = [rosterHeaders];
styleHeader(roster.getRange("A1:L1"));
roster.getRange("A2:L2").values = [[
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "Do not populate until official Missouri Board/DPR data confirms active CPA firm status.",
]];
const rosterTable = roster.tables.add("A1:L2", true, "CPA_Firm_Roster");
rosterTable.showFilterButton = true;
rosterTable.style = "TableStyleMedium2";
roster.freezePanes.freezeRows(1);

methodology.getRange("A1:F1").merge();
methodology.getRange("A1").values = [["Methodology and Source Audit"]];
styleTitle(methodology, methodology.getRange("A1:F1"));
methodology.getRange("A3:F3").values = [[
  "Step",
  "Source",
  "URL",
  "Result",
  "Use in roster",
  "Notes",
]];
styleHeader(methodology.getRange("A3:F3"));
methodology.getRange("A4:F9").values = [
  [
    "1",
    "Missouri Board of Accountancy home/contact page",
    "https://pr.mo.gov/accountancy.asp",
    "Confirmed official Board and contact details.",
    "Authoritative source/contact",
    "Board contact shown as Missouri State Board of Accountancy, 3605 Missouri Boulevard, P.O. Box 613, Jefferson City, MO 65102-0613; phone 573.751.0012; mosba@pr.mo.gov.",
  ],
  [
    "2",
    "MOPRO license portal",
    "https://pr.mo.gov/licensee-search.asp",
    "Public licensing portal loads through Salesforce/MOPRO with reCAPTCHA-related controls.",
    "Official lookup source",
    "Suitable for individual record verification; not suitable for an auditable exhaustive bulk scrape in this implementation.",
  ],
  [
    "3",
    "MOPRO canonical portal",
    "https://mopro.mo.gov/license/s/",
    "Same Salesforce licensing portal observed.",
    "Official lookup source",
    "No reliable public zip-filtered export endpoint identified.",
  ],
  [
    "4",
    "Downloadable listings page",
    "https://pr.mo.gov/listings.asp",
    "Routed to the Salesforce/MOPRO licensing portal.",
    "Checked for roster export",
    "No accessible CPA firm listing export found during implementation.",
  ],
  [
    "5",
    "ZIP boundary",
    "User-approved ZIP set",
    "63123, 63125, 63126, 63127, 63128, 63129",
    "Filtering criteria",
    "Core South St. Louis County definition selected by user.",
  ],
  [
    "6",
    "Records request fallback",
    "Records Request sheet",
    "Ready to send",
    "Primary completion path",
    "Use returned CSV/XLSX to populate CPA Firm Roster and mark verification date.",
  ],
];
methodology.getRange("A4:F9").format.wrapText = true;
methodology.getRange("A4:F9").format.borders = { preset: "insideHorizontal", style: "thin", color: "#E1E7EC" };

request.getRange("A1:D1").merge();
request.getRange("A1").values = [["Ready-to-send Missouri Sunshine Law Request"]];
styleTitle(request, request.getRange("A1:D1"));
request.getRange("A3:B8").values = [
  ["To", "mosba@pr.mo.gov"],
  ["Agency", "Missouri State Board of Accountancy"],
  ["Phone", "573.751.0012"],
  ["Address", "3605 Missouri Boulevard; P.O. Box 613; Jefferson City, MO 65102-0613"],
  ["Requested format", "CSV or Excel"],
  ["Requested ZIPs", zipCodes.join(", ")],
];
request.getRange("A3:A8").format = { font: { bold: true }, fill: "#EAF2F8" };
request.getRange("A3:B8").format.wrapText = true;
request.getRange("A10:D22").merge();
request.getRange("A10").values = [[requestText]];
styleNoteBlock(request.getRange("A10:D22"));
request.getRange("A10:D22").format.rowHeight = 230;

const sheets = [
  [summary, [22, 86, 150, 18, 18, 18, 18, 18]],
  [roster, [28, 24, 18, 34, 18, 10, 10, 16, 28, 44, 18, 60]],
  [methodology, [10, 34, 44, 34, 28, 68]],
  [request, [22, 64, 18, 18]],
];

for (const [sheet, widths] of sheets) {
  widths.forEach((width, idx) => {
    sheet.getRangeByIndexes(0, idx, 1, 1).format.columnWidth = width;
  });
}

await fs.writeFile(outputCsv, rosterHeaders.join(",") + "\n", "utf8");

for (const sheetName of ["Summary", "CPA Firm Roster", "Methodology", "Records Request"]) {
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const safeName = sheetName.toLowerCase().replaceAll(" ", "_");
  await fs.writeFile(path.join(outputDir, `${safeName}_preview.png`), new Uint8Array(await preview.arrayBuffer()));
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputXlsx);
console.log(`Saved ${outputXlsx}`);
