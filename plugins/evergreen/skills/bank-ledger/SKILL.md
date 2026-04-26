---
name: bank-ledger
description: Use this skill whenever the user (Evergreen back-office) wants to maintain or query the master bank-ledger Google Sheet — the canonical record of every credit and debit hitting the six approved Maybank/AmBank accounts. Triggers include "refresh bank ledger", "import bank transactions", "check ledger", "show unmatched credits", "set up bank ledger", "tune bank-ledger parser", or any task involving incoming bank statement attachments or daily reconciliation against the master sheet.
version: 0.3.0
updated: 2026-04-26 21:34
---

# Bank Ledger — Evergreen Master Transaction Sheet

The single source of truth for every transaction hitting the six approved Maybank / AmBank accounts. Today the production pipeline covers **AmBank only**, ingesting daily statement CSVs that AmBank emails as password-protected ZIPs. A Google Apps Script runs every morning at 06:00, downloads the ZIP, sends it to a remote unzip helper, parses the CSV, and appends rows to the `Transactions` tab. A second function in the same script — `doGet()` — exposes the sheet as a JSON query API so `sale-audit` can verify clearance from any environment without Google credentials.

`sale-audit` (v0.10+) reads from this sheet via the Web App. The bank-statement folder it used in earlier versions is **gone**.

---

## 1. Why a separate skill (vs. folding into sale-audit)

Audit logic and bank ingestion stay decoupled. They share data via the Google Sheet — neither calls the other directly. The sheet schema is the contract; either side can change without breaking the other.

## 2. Bank accounts (must match `sale-audit` §2)

The script recognises only these six accounts. AmBank emails reference each by its 2-digit suffix in the subject line (`*35)`, `*46)`, `*57)`); the Apps Script maps that suffix to the full 13-digit account number when writing the row.

- **Maybank**: 510161015366, 560166149415, 560166149422 — **not yet ingested** (see §9).
- **AmBank**: 8881058618135, 8881058618146, 8881058618157.

## 3. Google Sheet — schema

A single Google Sheet with one tab named **`Transactions`** (capital T). Row 1 is the header — written automatically by the Apps Script on first run from AmBank's CSV column order.

**24 columns, in this order:**

| # | Column                | Source / meaning                                                               |
|---|-----------------------|---------------------------------------------------------------------------------|
| 1 | `Account No`         | Full 13-digit AmBank account, e.g., `8881058618135`. Set by the script from the email subject suffix lookup. |
| 2 | `SEQ NO`             | AmBank's per-statement sequence number.                                        |
| 3 | `QR ID`              | DuitNow QR transaction id (often blank for non-QR transactions).               |
| 4 | `TRAN DATE`          | Transaction value date in `DD/MM/YYYY`.                                        |
| 5 | `TRAN TIME`          | `HH:MM:SS`.                                                                    |
| 6 | `TRAN CODE`          | AmBank's internal transaction code (e.g., `1030`).                             |
| 7 | `PROMO CODE`         | Internal promo / channel code.                                                 |
| 8 | `TRAN DESC`          | Free text describing the transaction. Crucially, contains `CR` for credits and `DR` for debits — the skill uses this to infer direction. |
| 9 | `SENDER/RECEIVER NAME` | Counterparty name (uppercase). Useful narrative for slip matching.           |
| 10 | `PAYMENT REF`        | Bank reference / customer-supplied note.                                       |
| 11 | `PAYMENT DET`        | Additional payment detail.                                                     |
| 12 | `TRAN AMT`           | Gross transaction amount in MYR.                                               |
| 13 | `NET AMT`            | Amount after MDR.                                                              |
| 14 | `BAL`                | Running balance after this transaction.                                        |
| 15 | `MDR`                | Merchant Discount Rate as a percentage string.                                 |
| 16 | `STAT`               | Status: typically `Successful`.                                                |
| 17 | `CHEQUE NO`          | `0` for non-cheque entries.                                                    |
| 18 | `REF ID`             | Internal reference id.                                                         |
| 19 | `STORE LBL`          | Merchant terminal label (POS / DuitNow only).                                  |
| 20 | `TERMINAL LBL`       | Terminal id (POS only).                                                        |
| 21 | `CONSUMER LBL`       | Consumer-facing label (POS / DuitNow only).                                    |
| 22 | `REF LBL`            | Reference label.                                                               |
| 23 | `MDR FLAT FEE`       | Flat fee component, if any.                                                    |
| 24 | `Email Date`         | Date the AmBank email itself arrived. Added by the Apps Script.                |

The Sheet ID and tab name are referenced by both the daily ingestion and the doGet handler. Changing them without updating the constants in the script will break both.

## 4. Paths and config (saved as `reference` memories)

On first run, ask and save these `reference` memories. Verify each on every reuse and never silently substitute a default.

1. **Bank-ledger Sheet ID** — the long string in the Sheet's URL.
2. **Bank-ledger Web App URL** — the deployed `doGet` endpoint, format `https://script.google.com/macros/s/AKfycb…/exec`.
3. **Bank-ledger Web App token** — the value of the Apps Script's `WEB_APP_TOKEN` script property (a long random string). Treat as a password; never log or echo it.

## 5. Workflow — interactive

When the user asks the skill questions in chat:

1. Confirm Sheet ID is in memory; if not, prompt for it once.
2. To answer "show today's credits", "any unmatched credits this week?", "is RM 350 on 2026-04-25 in the ledger?", call the Web App with the right query parameters (see §7 below) and parse the JSON.
3. Never mutate the sheet from the skill. Only the Apps Script writes (avoids race conditions with the daily ingestion).

## 6. Workflow — automatic (daily 06:00, no human)

Runs entirely inside Google — no Claude session, no server cron. The Apps Script function `fetchAmBankToSheet` does this loop:

1. Search Gmail for unread / unprocessed AmBank emails (`from:notification@ambankgroup.com has:attachment filename:zip newer_than:90d`).
2. For each match, identify the destination account from the subject suffix (e.g., `*35)` → `8881058618135`).
3. Download the `.zip` attachment, base64-encode it, POST it to the remote unzip helper at `https://ambank-unzip.onrender.com/unzip` with the ZIP password.
4. Parse the returned CSV. Skip the header row on subsequent runs.
5. Prepend the account number, append the email's received date, and write each row to the `Transactions` tab.
6. Mark the Gmail message-id as processed via the `doneIds` script property so it is never re-ingested.

Failures are logged to the Apps Script execution log (Apps Script editor → **Executions**); they do not block subsequent emails.

## 7. doGet — Web App query API

Used by `sale-audit` to verify clearance. URL = the Web App URL from §4 item 2. Token is appended on every request.

**Health-check / connectivity ping** — supply only `token`:

```
GET <URL>?token=<TOKEN>
→ { "ok": true, "ping": "bank-ledger", "row_count": <int> }
```

`sale-audit` runs this at the start of every audit to populate the meta-strip status.

**Per-slip clearance lookup** — supply `value_date` plus any of the optional filters:

| Param | Required? | Notes |
|---|---|---|
| `token` | yes | Must equal the `WEB_APP_TOKEN` script property. |
| `value_date` | yes | `YYYY-MM-DD`. |
| `account` | optional | Full 13-digit (`8881058618135`), last-4 (`8135`), or `AMB-8135`. The endpoint normalises before matching. |
| `amount` | optional | Match against `TRAN AMT`, tolerance ±0.01. |
| `direction` | optional | `CR` (default) or `DR`. Inferred from `\bCR\b` / `\bDR\b` in `TRAN DESC`. |
| `tolerance_days` | optional | 0..7, default 3. Accepts `TRAN DATE` up to value_date + N days (used for cheques). |

Response on success:

```
{
  "ok": true,
  "total_count": 1,
  "matches": [
    {
      "account_no": "8881058618135",
      "tran_date": "2026-04-25",
      "tran_time": "19:24:57",
      "tran_desc": "MISC CR",
      "sender_receiver": "MALINAH BINTI TUTUNG",
      "payment_ref": "Pindahan Dana",
      "amount": 8.62,
      "net_amt": 8.62,
      "bal": 12859.48,
      "stat": "Successful",
      "direction": "CR",
      ...
    }
  ]
}
```

Response on error:

```
{ "ok": false, "error": "<reason>" }
```

`sale-audit` handles the three match cases (`total_count` 0 / 1 / >1) per its own §6 rule 11.

## 8. Setup — one-time

### 8.1 Create the master Google Sheet

1. Sign into Gmail at `evergreenkk.sabah@gmail.com`.
2. Visit <https://sheets.new> → rename the file **Evergreen Bank Ledger**.
3. Right-click `Sheet1` → rename to **`Transactions`** (case-sensitive).
4. Copy the Sheet ID from the URL (between `/d/` and `/edit`) — you'll paste it into the script in §8.2.

The Apps Script writes the header row automatically on first run, so you don't need to paste headers manually.

### 8.2 Install the Apps Script

1. In the Sheet: **Extensions → Apps Script**.
2. Delete the placeholder code; paste the entire contents of `apps-script/parse-bank-emails.gs` (this skill folder).
3. Fill in the constants at the top of the file:
   - `ZIP_PASSWORD` — the AmBank-issued password for the daily ZIP.
   - `SHEET_ID` — from §8.1.
4. Save (`Ctrl+S`). Project name: **Bank Ledger Importer**.

### 8.3 Set the Web App token

1. Apps Script editor → **gear icon (Project Settings)** → **Script properties → Add script property**.
2. Property name: `WEB_APP_TOKEN`.
3. Property value: a long random string (≥32 chars). Generate at <https://passwordsgenerator.net/>; save it somewhere safe — you'll paste it into Claude memory in §8.6.
4. Save.

### 8.4 Schedule the daily 06:00 trigger

1. In the Apps Script editor, select function **`setupTrigger`** from the dropdown.
2. **Run**. Grant Gmail / Sheets / external request permissions on first consent (one-time).
3. The script wipes any existing triggers in this project and creates a single daily 06:00 trigger calling `fetchAmBankToSheet`. Verify in the **clock icon (Triggers)** sidebar that exactly one trigger exists.

### 8.5 Deploy as a Web App (the query API)

1. Apps Script editor → top-right **Deploy → New deployment**.
2. Click the gear next to **Select type → Web app**.
3. Description: `Bank Ledger Query API v0.3`. Execute as: **Me**. Who has access: **Anyone** (the token gates access).
4. **Deploy**, grant the additional permissions Google asks for, copy the **Web app URL**.

> **Re-deploying after future code edits** — do not Deploy → New deployment again; instead, **Deploy → Manage deployments → pencil → Version: New version → Deploy**. The URL stays the same and Claude memory does not need updating.

### 8.6 Verify the Web App responds

Open in a browser, replacing `<URL>` and `<TOKEN>`:

```
<URL>?token=<TOKEN>
```

Expect `{"ok":true,"ping":"bank-ledger","row_count":<int>}`. If you see `invalid token`, re-check §8.3. If you see a Google error page, the deployment didn't succeed — re-do §8.5.

### 8.7 Tell Claude

In a chat, say:

```
Set up bank ledger.
Sheet ID: <ID from §8.1>
Web App URL: <URL from §8.5>
Web App token: <TOKEN from §8.3>
```

The skill stores all three as `reference` memories and confirms connectivity by pinging the Web App.

## 9. Limitations and known issues (v0.3.0)

- **AmBank only.** Maybank ingestion is **not implemented**. `sale-audit` clearance lookups for MBB-prefixed accounts will return `total_count: 0` until MBB ingestion is added; sale-audit treats that as a finding and flags the slip for manual review. Adding MBB requires a separate ingestion pattern (Maybank typically does not email password-protected daily CSVs the same way), to be designed when needed.
- **Remote unzip dependency.** The daily ingestion offloads ZIP unlocking to <https://ambank-unzip.onrender.com/unzip>. If that service is offline, the daily run fails with `Unzip failed: ...` in the execution log — the script does not write partial rows; it simply skips that email and tries again the next day. Long-term, host the unzipper somewhere we control.
- **No MDR netting.** The audit reconciles against `TRAN AMT` (gross). If you ever switch to `NET AMT`, update sale-audit §6 rule 11 and the doGet helper consistently.
- **Direction inference relies on `TRAN DESC`.** Rows where `TRAN DESC` lacks an unambiguous `CR` / `DR` token (rare for AmBank) are filtered out as `direction = UNKNOWN`. If you start seeing such rows, expand the inference rules.
- **No write-back from skill.** The skill is read-only on the sheet from chat; only the Apps Script writes (avoids races with the daily trigger).

## 10. Non-negotiables

- Never write to the sheet from the skill (only the Apps Script writes).
- Never invent account mappings — if a row's `Account No` doesn't match any of the six in §2, sale-audit treats it as out-of-scope.
- Never modify a row already in the sheet — the ledger is append-only.
- Never re-process an email already in the `doneIds` script property.
- Never log or echo the Web App token outside the user's own session.
