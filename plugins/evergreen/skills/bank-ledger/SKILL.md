---
name: bank-ledger
description: Use this skill whenever the user (Evergreen back-office) wants to maintain or query the master bank-ledger Google Sheet — the canonical record of every credit and debit hitting the six approved Maybank/AmBank accounts. Triggers include "refresh bank ledger", "import bank transactions", "check ledger", "show unmatched credits", "set up bank ledger", or any task involving incoming bank transaction emails or daily bank reconciliation against the master sheet.
version: 0.1.0
updated: 2026-04-26 08:20
---

# Bank Ledger — Evergreen Master Transaction Sheet

The single source of truth for every transaction hitting the six approved Maybank / AmBank accounts. Populated automatically every 30 minutes by a Google Apps Script that reads MBB and AmBank alert emails from `evergreenkk.sabah@gmail.com` and appends one row per transaction to a master Google Sheet.

This skill helps you set up that pipeline, query the sheet, and reconcile the day. It does **not** modify `sale-audit` — sale-audit will read from this sheet in a future revision; until then, sale-audit keeps using its existing bank-statement folder.

---

## 1. Why a separate skill

Audit logic (`sale-audit`) and bank ingestion (`bank-ledger`) stay decoupled. They share data via the Google Sheet — neither calls the other directly. Either skill can change without breaking the other.

## 2. Bank accounts (must match `sale-audit` §2)

The skill recognises only these six accounts. Any transaction email referencing an account outside this list is logged but flagged in the sheet as `account = OTHER` for human triage.

- **Maybank**: 510161015366, 560166149415, 560166149422
- **AmBank**: 8881058618135, 8881058618146, 8881058618157

Account values in the sheet are stored as `<bank-prefix>-<last-4>` for readability and partial-match safety: `MBB-5366`, `MBB-9415`, `MBB-9422`, `AMB-8135`, `AMB-8146`, `AMB-8157`. Bank emails almost always print the masked account as `xxxx5366` — the parser pulls the last 4 digits and prepends the bank prefix.

## 3. Google Sheet — schema

A single Google Sheet with one tab named **`transactions`**. Row 1 is the header. The Apps Script appends to the next empty row.

| # | Column           | Description                                                                                              |
|---|------------------|----------------------------------------------------------------------------------------------------------|
| 1 | `txn_id`         | sha256 of (`account` + `value_date` + `amount` + `narrative` + Gmail message-id). Primary dedup key.     |
| 2 | `account`        | `MBB-5366`, `AMB-8135`, etc., or `OTHER` if last-4 doesn't match §2.                                     |
| 3 | `value_date`     | `YYYY-MM-DD` — date the funds settled (extracted from the email body).                                   |
| 4 | `posting_date`   | `YYYY-MM-DD HH:MM` — when the bank posted the entry (usually the email's send time).                     |
| 5 | `amount`         | Numeric, RM, always positive. Direction is in column 6.                                                  |
| 6 | `direction`      | `CR` (credit / money in) or `DR` (debit / money out).                                                    |
| 7 | `narrative`      | Free-text bank reference / description / counterparty name.                                              |
| 8 | `source_ref`     | Slip / transaction reference if extractable from the email (often blank for MBB).                        |
| 9 | `source`         | `email-mbb`, `email-amb`, `csv-import`, or `manual`.                                                     |
| 10 | `ingested_at`   | `YYYY-MM-DD HH:MM` — when the row landed in the sheet.                                                    |
| 11 | `matched_slip`  | Filled in a later revision by `sale-audit` once the slip ↔ credit match is implemented. Blank for now.    |
| 12 | `status`        | `new`, `matched`, `unmatched`, or `superseded`. Apps Script writes `new`; future sale-audit updates it.   |

The Sheet ID gets stored as a `reference` memory on first run, so you only paste it once.

## 4. Paths and config

On first run, ask and save these `reference` memories:

1. **Bank-ledger Sheet ID** — the long string in the Sheet's URL (between `/d/` and `/edit`). Example: `1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT_uVwXyZ`.
2. **Apps Script trigger status** — flag indicating the 30-minute trigger is configured (`yes` once §7 setup is verified). The skill reminds the user to verify this on first run.

Verify both before doing any read/write — never silently write to the wrong sheet.

## 5. Workflow — interactive

When the user invokes the skill in chat:

1. Confirm Sheet ID is in memory; if not, prompt for it once.
2. Read the `transactions` tab.
3. Answer the user's question — common patterns:
   - "show today's credits" → filter `value_date = today` and `direction = CR`.
   - "any unmatched credits this week?" → filter `status = unmatched` within the last 7 days.
   - "total received in MBB-5366 yesterday" → sum `amount` where `account = MBB-5366` and `value_date = yesterday` and `direction = CR`.
   - "is RM 350 on 2026-04-25 to MBB-5366 in the ledger?" → look it up; return found / not found.
4. Never mutate the sheet from the skill itself in v0.1.0 — the Apps Script is the only writer (avoids race conditions with the 30-min trigger).

## 6. Workflow — automatic (every 30 min, no human)

The 30-minute refresh runs entirely inside Google — no Claude session, no server cron. The Apps Script (see `apps-script/parse-bank-emails.gs`) does this loop:

1. Search Gmail for unread / unprocessed emails matching each bank's sender + subject pattern.
2. For each matching email, run the bank-specific parser to extract `account`, `value_date`, `amount`, `direction`, `narrative`.
3. Compute `txn_id`. Skip if already in the sheet (dedup).
4. Append a new row with `status = new`.
5. Apply a Gmail label `bank-ledger-processed` to the email so it is not re-parsed next cycle.

If a parser fails to extract required fields, the email is **not** marked processed. It will be retried next cycle. After three failures, the script logs the message ID and email subject to a sheet tab `parse_failures` for manual review.

## 7. Setup — one-time

### 7.1 Create the master Google Sheet

1. Open `evergreenkk.sabah@gmail.com` Gmail in a browser.
2. Go to <https://sheets.new> → name the file **Evergreen Bank Ledger**.
3. Rename the default tab from `Sheet1` to `transactions`.
4. Paste this header into row 1 (one column per cell, in order):
   ```
   txn_id  account  value_date  posting_date  amount  direction  narrative  source_ref  source  ingested_at  matched_slip  status
   ```
5. Freeze row 1: View → Freeze → 1 row.
6. Copy the Sheet ID from the URL (the long string between `/d/` and `/edit`). Save it — you'll paste it into Apps Script and into Claude.
7. Create a second empty tab named `parse_failures` for the Apps Script to log emails it can't parse.

### 7.2 Install the Apps Script

1. In the Sheet: **Extensions → Apps Script**.
2. Delete any starter code in `Code.gs`.
3. Copy the entire contents of `apps-script/parse-bank-emails.gs` (in this skill folder) and paste it in.
4. At the top of the script, replace `PUT-YOUR-SHEET-ID-HERE` with the Sheet ID from step 7.1.
5. Save (`Ctrl+S`). When prompted, name the project **Bank Ledger Importer**.
6. Click **Run** → select function `parseAllBankEmails` → grant the requested Gmail + Sheets permissions (one-time consent for the Gmail account).
7. Confirm at least one row appears in the sheet (run on an inbox that already has bank emails to test). If parsing fails, see §8.

### 7.3 Schedule the 30-minute trigger

1. In Apps Script, click the **clock icon** (Triggers) on the left sidebar.
2. **Add Trigger**:
   - Function to run: `parseAllBankEmails`
   - Deployment: `Head`
   - Event source: `Time-driven`
   - Type of time-based trigger: `Minutes timer`
   - Select minute interval: `Every 30 minutes`
3. Save. Google will run the parser automatically every 30 minutes from now on.

### 7.4 Tell Claude

In Claude, say *"set up bank ledger, my sheet ID is &lt;ID&gt;"*. The skill stores the Sheet ID in `reference` memory and confirms by reading the header row.

## 8. Email parser — tuning

The shipped parser in `apps-script/parse-bank-emails.gs` is a **starter template**. It has reasonable regex for typical MBB and AmBank alert formats, but real emails vary by:

- **Account product** (savings vs current vs business)
- **Channel** (DuitNow QR vs IBG vs Instant Transfer vs CDM deposit)
- **Bank format updates** (banks change subject lines occasionally)

To tune the parser for your actual emails:

1. Forward 5–10 sample MBB transaction emails and 5–10 AmBank emails to Kui Shung.
2. We update `parse-bank-emails.gs` with corrected regex and ship a new skill version.
3. Replace the Apps Script content with the updated version (steps 7.2.3–7.2.5).

The `parse_failures` sheet tab will accumulate any email the script could not parse. Review it weekly; emails that recur there are signals the parser needs another rule.

## 9. Limitations and known issues (v0.1.0)

- **Bookkeeper only** — `sale-audit` does **not** read this sheet yet. That integration ships in a follow-up release once the ledger has been observed running cleanly for a week.
- **No write-back from skill** — the skill in chat is read-only on the sheet; only the Apps Script writes.
- **Parser is starter-quality** — see §8.
- **DuitNow QR** alerts often omit the destination account number. The parser logs them as `account = OTHER` for human triage.
- **Email rate limit** — Apps Script can read up to ~20,000 emails per day (well above your volume). If you ever miss a day's transactions, just run `parseAllBankEmails` manually from the Apps Script editor.

## 10. Non-negotiables

- Never write to the sheet from the skill (only the Apps Script writes).
- Never invent account mappings — if the last-4 doesn't match §2, the row's `account` is `OTHER`.
- Never modify a row whose `status = matched` (sale-audit will eventually own that column).
- Never re-process an email already labelled `bank-ledger-processed`.
