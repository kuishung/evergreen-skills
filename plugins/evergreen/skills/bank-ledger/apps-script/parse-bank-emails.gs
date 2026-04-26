/**
 * Evergreen Bank Ledger — AmBank CSV ingestion + Web App query API.
 *
 * What this script does
 *   1. fetchAmBankToSheet()  — daily trigger at 06:00. Reads new
 *      AmBank notification emails (from notification@ambankgroup.com),
 *      downloads the password-protected ZIP attachments, sends them
 *      to a remote unzip helper, parses the resulting CSV, and
 *      appends rows to the `Transactions` tab. Dedup is by Gmail
 *      message-id stored in the `doneIds` script property.
 *   2. doGet()  — exposed when the project is deployed as a Web App.
 *      Accepts a token plus query parameters, scans the
 *      `Transactions` tab, and returns matching rows as JSON. Used
 *      by `sale-audit` to verify slip clearance from any environment
 *      without Google credentials.
 *
 * One-time setup
 *   1. Sheet → Extensions → Apps Script → paste this whole file.
 *   2. Fill in the constants in the FILL-THESE-IN block below.
 *   3. Run setupTrigger() once to create the daily 06:00 trigger.
 *   4. Project Settings → Script properties → add WEB_APP_TOKEN with
 *      a long random string (used only by doGet, not the daily
 *      ingestion).
 *   5. Deploy → New deployment → Web app → Execute as: Me / Who has
 *      access: Anyone → Deploy → copy the Web app URL.
 *   6. Tell Claude the URL, the token, and the Sheet ID — they all
 *      live as `reference` memories so the audit can call this API.
 *
 * Re-deploying after future code edits
 *   Deploy → Manage deployments → pencil → Version: New version →
 *   Deploy. URL stays the same; Claude's memory does not need to
 *   change.
 */

// ═════════════════════════ FILL THESE IN ═════════════════════════
const ZIP_PASSWORD = 'PUT-AMBANK-ZIP-PASSWORD-HERE';
const SHEET_ID     = 'PUT-SHEET-ID-HERE';
const SHEET_NAME   = 'Transactions';
const UNZIP_URL    = 'https://ambank-unzip.onrender.com/unzip';

// AmBank's transaction email subject embeds the account's last 2-3
// digits in parentheses (e.g., "*35)" or "35)"). Map suffix → full
// 13-digit account number. Suffixes here mirror sale-audit §2.
const ACCOUNTS = {
  '35': '8881058618135',
  '46': '8881058618146',
  '57': '8881058618157',
};

// Web App authentication. Set once via Project Settings → Script
// properties → add property `WEB_APP_TOKEN` with a random string.
// Never commit the token value; the property holds it on Google's
// side and the script reads it at request time.
const TOKEN_PROPERTY_KEY = 'WEB_APP_TOKEN';
// ═════════════════════════════════════════════════════════════════

// Sheet schema — 24 columns, set by the daily ingestion's first
// CSV write. Index here is 0-based for use with .getValues().
const COLS = {
  ACCOUNT_NO:    0,
  SEQ_NO:        1,
  QR_ID:         2,
  TRAN_DATE:     3,
  TRAN_TIME:     4,
  TRAN_CODE:     5,
  PROMO_CODE:    6,
  TRAN_DESC:     7,
  SENDER:        8,
  PAYMENT_REF:   9,
  PAYMENT_DET:  10,
  TRAN_AMT:     11,
  NET_AMT:      12,
  BAL:          13,
  MDR:          14,
  STAT:         15,
  CHEQUE_NO:    16,
  REF_ID:       17,
  STORE_LBL:    18,
  TERMINAL_LBL: 19,
  CONSUMER_LBL: 20,
  REF_LBL:      21,
  MDR_FLAT_FEE: 22,
  EMAIL_DATE:   23,
};
const SHEET_COL_COUNT = 24;

// ═════════════ Daily ingestion (runs at 06:00) ═════════════════════

function fetchAmBankToSheet() {
  const sheet = getOrCreateSheet_();
  const done  = getDoneIds_();
  const query = 'from:notification@ambankgroup.com has:attachment filename:zip newer_than:90d';
  const threads = GmailApp.search(query, 0, 20);
  let newCount = 0;

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (msg) {
      const msgId = msg.getId();
      if (done.has(msgId)) {
        Logger.log('Skipping already processed: ' + msg.getSubject());
        return;
      }

      const subject = msg.getSubject();
      const accountNo = getAccountNo_(subject);
      if (!accountNo) {
        Logger.log('No matching account in subject: ' + subject);
        return;
      }

      msg.getAttachments().forEach(function (att) {
        if (!att.getName().toLowerCase().endsWith('.zip')) return;
        try {
          const csvText = unzip_(att.copyBlob());
          const rows    = Utilities.parseCsv(csvText);
          const added   = writeRows_(sheet, rows, accountNo, msg.getDate());
          markDone_(msgId);
          newCount += added;
          Logger.log('✓ Processed: ' + subject + ' → ' + added + ' rows added');
        } catch (e) {
          Logger.log('✗ Error: ' + subject + ' → ' + e.message);
        }
      });
    });
  });

  Logger.log('Done. Total new rows added: ' + newCount);
}

function getAccountNo_(subject) {
  for (const suffix in ACCOUNTS) {
    if (subject.indexOf('*' + suffix + ')') !== -1 || subject.indexOf(suffix + ')') !== -1) {
      return ACCOUNTS[suffix];
    }
  }
  return null;
}

function unzip_(blob) {
  const b64 = Utilities.base64Encode(blob.getBytes());
  const res = UrlFetchApp.fetch(UNZIP_URL, {
    method:             'post',
    contentType:        'application/json',
    payload:            JSON.stringify({ data: b64, password: ZIP_PASSWORD }),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) {
    throw new Error('Unzip failed: ' + res.getContentText());
  }
  return res.getContentText();
}

function writeRows_(sheet, rows, accountNo, emailDate) {
  if (rows.length < 2) return 0;

  // Header on first run only.
  if (sheet.getLastRow() === 0) {
    const header = ['Account No'].concat(rows[0]).concat(['Email Date']);
    sheet.getRange(1, 1, 1, header.length)
         .setValues([header])
         .setFontWeight('bold')
         .setBackground('#f3f3f3');
  }

  const data = rows.slice(1)
    .filter(function (r) { return r.some(function (c) { return String(c).trim() !== ''; }); })
    .map(function (r) { return [accountNo].concat(r).concat([emailDate]); });

  if (data.length === 0) return 0;

  sheet.getRange(sheet.getLastRow() + 1, 1, data.length, data[0].length).setValues(data);
  return data.length;
}

function getOrCreateSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
}

// ── Email-id tracking via Script Properties ─────────────────────

function getDoneIds_() {
  const raw = PropertiesService.getScriptProperties().getProperty('doneIds') || '[]';
  return new Set(JSON.parse(raw));
}

function markDone_(id) {
  const prop = PropertiesService.getScriptProperties();
  const ids  = JSON.parse(prop.getProperty('doneIds') || '[]');
  if (ids.indexOf(id) === -1) {
    ids.push(id);
    prop.setProperty('doneIds', JSON.stringify(ids));
  }
}

// ── Run ONCE to create the daily 06:00 trigger ─────────────────

function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('fetchAmBankToSheet')
    .timeBased()
    .atHour(6)
    .everyDays(1)
    .create();
  Logger.log('Daily 06:00 trigger created.');
}

// ── Debug utilities ────────────────────────────────────────────

function showProcessedIds() {
  const raw = PropertiesService.getScriptProperties().getProperty('doneIds') || '[]';
  const ids = JSON.parse(raw);
  Logger.log('Total processed emails: ' + ids.length);
  ids.forEach(function (id) { Logger.log(id); });
}

function resetProcessedIds() {
  PropertiesService.getScriptProperties().deleteProperty('doneIds');
  Logger.log('Reset done. All emails will be reprocessed on next run.');
}

// ════════════ doGet — Web App query API for sale-audit ════════════

/**
 * HTTP GET handler. Used by `sale-audit` to verify whether a
 * proof-of-fund slip cleared.
 *
 * Required query parameters:
 *   token        — must equal the WEB_APP_TOKEN script property.
 *   value_date   — YYYY-MM-DD; the slip's expected settlement date.
 *
 * Optional query parameters:
 *   account        — full 13-digit (`8881058618135`), last-4
 *                    (`8135`), or branded (`AMB-8135`); the script
 *                    normalises and matches against the full
 *                    13-digit `Account No` column.
 *   amount         — exact RM amount; tolerance ±0.01.
 *   direction      — `CR` (default) or `DR`; inferred from
 *                    `\bCR\b` / `\bDR\b` in the row's `TRAN DESC`.
 *   tolerance_days — 0..7 (default 3); accept TRAN DATE up to +N
 *                    days later. Used for cheque-funded slips.
 *
 * Response (always HTTP 200; check the `ok` field):
 *   { "ok": true, "matches": [ ... ], "total_count": N }
 *   { "ok": false, "error": "..." }
 *
 * Health-check call (no value_date supplied) returns:
 *   { "ok": true, "ping": "bank-ledger", "row_count": N }
 * so sale-audit can ping at the start of every run.
 */
function doGet(e) {
  try {
    const params = (e && e.parameter) ? e.parameter : {};

    const expected = PropertiesService.getScriptProperties().getProperty(TOKEN_PROPERTY_KEY);
    if (!expected) {
      return jsonResponse_({ ok: false, error: 'WEB_APP_TOKEN script property not configured' });
    }
    if (params.token !== expected) {
      return jsonResponse_({ ok: false, error: 'invalid token' });
    }

    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      return jsonResponse_({ ok: false, error: 'tab "' + SHEET_NAME + '" not found' });
    }

    if (!params.value_date) {
      const lastRow = sheet.getLastRow();
      return jsonResponse_({
        ok: true,
        ping: 'bank-ledger',
        row_count: Math.max(0, lastRow - 1),
      });
    }

    const targetDateRaw = String(params.value_date).trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(targetDateRaw)) {
      return jsonResponse_({ ok: false, error: 'value_date must be YYYY-MM-DD' });
    }

    const targetAccount = params.account ? normalizeAccount_(params.account) : null;
    const targetAmount  = (params.amount !== undefined && params.amount !== '') ? parseFloat(params.amount) : null;
    const directionFilter = params.direction ? String(params.direction).toUpperCase().trim() : 'CR';
    const toleranceDays = Math.max(0, Math.min(7, parseInt(params.tolerance_days || '3', 10) || 0));

    const dateStart = parseISODate_(targetDateRaw);
    const dateEnd   = new Date(dateStart);
    dateEnd.setDate(dateEnd.getDate() + toleranceDays);

    const lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      return jsonResponse_({ ok: true, matches: [], total_count: 0 });
    }

    const data = sheet.getRange(2, 1, lastRow - 1, SHEET_COL_COUNT).getValues();
    const matches = [];

    for (let i = 0; i < data.length; i++) {
      const row = data[i];

      const tranDate = parseDMYDate_(row[COLS.TRAN_DATE]);
      if (!tranDate) continue;
      if (tranDate < dateStart || tranDate > dateEnd) continue;

      const desc = String(row[COLS.TRAN_DESC] || '').toUpperCase();
      const rowDir = /\bCR\b/.test(desc) ? 'CR' : (/\bDR\b/.test(desc) ? 'DR' : 'UNKNOWN');
      if (directionFilter && rowDir !== directionFilter) continue;

      if (targetAccount) {
        const rowAcc = normalizeAccount_(row[COLS.ACCOUNT_NO]);
        if (rowAcc !== targetAccount) continue;
      }

      const rowAmt = parseFloat(row[COLS.TRAN_AMT]);
      if (targetAmount !== null && Math.abs(rowAmt - targetAmount) > 0.01) continue;

      matches.push({
        account_no:      String(row[COLS.ACCOUNT_NO]),
        seq_no:          row[COLS.SEQ_NO],
        tran_date:       formatDate_(tranDate, 'yyyy-MM-dd'),
        tran_time:       String(row[COLS.TRAN_TIME] || '').trim(),
        tran_code:       row[COLS.TRAN_CODE],
        tran_desc:       String(row[COLS.TRAN_DESC] || '').trim(),
        sender_receiver: String(row[COLS.SENDER] || '').trim(),
        payment_ref:     String(row[COLS.PAYMENT_REF] || '').trim(),
        payment_det:     String(row[COLS.PAYMENT_DET] || '').trim(),
        amount:          rowAmt,
        net_amt:         parseFloat(row[COLS.NET_AMT]) || 0,
        bal:             parseFloat(row[COLS.BAL]) || 0,
        stat:            String(row[COLS.STAT] || '').trim(),
        cheque_no:       row[COLS.CHEQUE_NO],
        ref_id:          String(row[COLS.REF_ID] || '').trim(),
        direction:       rowDir,
      });
    }

    return jsonResponse_({ ok: true, matches: matches, total_count: matches.length });
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'unhandled: ' + String(err) });
  }
}

// ── doGet helpers ─────────────────────────────────────────────

/**
 * Normalize an incoming account identifier to the full 13-digit
 * AmBank number used in the sheet's Account No column.
 *   "8881058618135"  → "8881058618135"
 *   "AMB-8135"       → "8881058618135"   (looked up via ACCOUNTS)
 *   "8135"           → "8881058618135"
 *   "*35)"           → "8881058618135"
 *   anything else    → digits-only fallback (will not match)
 */
function normalizeAccount_(raw) {
  const digits = String(raw || '').replace(/\D/g, '');
  if (!digits) return '';
  if (digits.length >= 8) return digits;
  for (const suffix in ACCOUNTS) {
    if (ACCOUNTS[suffix].slice(-digits.length) === digits) {
      return ACCOUNTS[suffix];
    }
    if (suffix === digits) return ACCOUNTS[suffix];
  }
  return digits;
}

/**
 * Parse a "DD/MM/YYYY" or Date value coming from the sheet's
 * TRAN DATE column. Returns a Date, or null on failure.
 */
function parseDMYDate_(raw) {
  if (raw instanceof Date) return raw;
  const m = String(raw || '').match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m) return null;
  return new Date(parseInt(m[3], 10), parseInt(m[2], 10) - 1, parseInt(m[1], 10));
}

/** Parse "YYYY-MM-DD" → Date in script's timezone. */
function parseISODate_(s) {
  const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
}

function formatDate_(d, pattern) {
  const tz = Session.getScriptTimeZone() || 'Asia/Kuala_Lumpur';
  return Utilities.formatDate(d, tz, pattern || 'yyyy-MM-dd HH:mm');
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
