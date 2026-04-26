/**
 * Evergreen Bank Ledger — parse incoming MBB and AmBank transaction
 * alert emails from `evergreenkk.sabah@gmail.com` and append rows to
 * the Bank Ledger Google Sheet.
 *
 * Setup:
 *   1. Open the Bank Ledger sheet → Extensions → Apps Script.
 *   2. Replace contents of Code.gs with this entire file.
 *   3. Set SHEET_ID below (the long string in the sheet URL).
 *   4. Run parseAllBankEmails once manually to grant Gmail + Sheets
 *      permissions; verify at least one row is written.
 *   5. Triggers (clock icon) → Add Trigger →
 *        Function:        parseAllBankEmails
 *        Event source:    Time-driven
 *        Type:            Minutes timer
 *        Interval:        Every 30 minutes
 *
 * Tuning:
 *   The regex inside parseMBBEmail() and parseAMBEmail() targets
 *   typical alert formats. If your bank emails look different, the
 *   message will land in the `parse_failures` tab. Forward 5-10
 *   samples per bank to Kui Shung for tuning, and a new
 *   bank-ledger version will ship with corrected regex.
 */

// ---------- Configuration ----------

const SHEET_ID = 'PUT-YOUR-SHEET-ID-HERE';
const TXN_TAB = 'transactions';
const FAIL_TAB = 'parse_failures';
const PROCESSED_LABEL = 'bank-ledger-processed';

// The doGet query API requires a shared secret token. Set it once via
// Apps Script editor → Project Settings → Script properties → add
// property name WEB_APP_TOKEN with a long random string. Never hard-code
// the token here — keep it in script properties so it does not leak via
// the GitHub source.
const TOKEN_PROPERTY_KEY = 'WEB_APP_TOKEN';

// Allowed bank accounts — last 4 digits → bank-prefixed code (mirrors
// sale-audit §2). Anything else becomes "OTHER".
const ACCOUNT_LOOKUP = {
  '5366': 'MBB-5366',
  '9415': 'MBB-9415',
  '9422': 'MBB-9422',
  '8135': 'AMB-8135',
  '8146': 'AMB-8146',
  '8157': 'AMB-8157',
};

// Per-bank sender + subject filter, plus the parser to use.
const BANK_RULES = [
  {
    code: 'MBB',
    senderQuery: 'from:(maybank2u OR maybank.com.my OR mbb.com.my)',
    subjectRegex: /(transaction|notification|credit|debit|received|transfer|alert)/i,
    parser: parseMBBEmail,
  },
  {
    code: 'AMB',
    senderQuery: 'from:(ambankgroup.com OR ambank.com.my OR amonline.com.my OR ambonline)',
    subjectRegex: /(transaction|notification|alert|received|transfer|credit|debit|paid|menerima|memindah|telah|akaun|duit)/i,
    parser: parseAMBEmail,
  },
];

// ---------- Entry point (run by the 30-min trigger) ----------

function parseAllBankEmails() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const txnSheet = ss.getSheetByName(TXN_TAB);
  if (!txnSheet) throw new Error(`Tab "${TXN_TAB}" not found in sheet ${SHEET_ID}`);

  const failSheet = ss.getSheetByName(FAIL_TAB) || ss.insertSheet(FAIL_TAB);
  if (failSheet.getLastRow() === 0) {
    failSheet.appendRow(['logged_at', 'bank', 'message_id', 'subject', 'reason']);
  }

  const existingTxnIds = new Set(getColumnValues(txnSheet, 1, 2));
  const label = getOrCreateLabel(PROCESSED_LABEL);

  let appended = 0;
  let failed = 0;

  for (const rule of BANK_RULES) {
    const query = `${rule.senderQuery} -label:${PROCESSED_LABEL} newer_than:14d`;
    const threads = GmailApp.search(query, 0, 100);

    for (const thread of threads) {
      let threadAllProcessed = true;

      for (const msg of thread.getMessages()) {
        const subject = msg.getSubject() || '';
        if (!rule.subjectRegex.test(subject)) continue;

        try {
          const txn = rule.parser(msg);
          if (!txn) {
            logFailure_(failSheet, rule.code, msg, 'parser returned null');
            failed++;
            threadAllProcessed = false;
            continue;
          }

          if (existingTxnIds.has(txn.txn_id)) {
            // Duplicate — do not append, but the email is still considered
            // processed.
            continue;
          }

          appendTxnRow_(txnSheet, txn);
          existingTxnIds.add(txn.txn_id);
          appended++;
        } catch (err) {
          logFailure_(failSheet, rule.code, msg, String(err));
          failed++;
          threadAllProcessed = false;
        }
      }

      if (threadAllProcessed) {
        thread.addLabel(label);
      }
    }
  }

  Logger.log(`Bank-ledger run complete: appended ${appended}, failures ${failed}`);
}

// ---------- Maybank parser ----------

/**
 * Typical MBB alert (subject + body):
 *   Subject: "Maybank2u Transaction Notification"
 *   Body excerpt:
 *     "Dear Customer,
 *      You have received MYR 350.00 from JOHN DOE
 *      to your account 51016xxxxx5366
 *      on 26/04/2026 at 14:30.
 *      Reference: IBG12345"
 *
 * NOTE: Real emails vary by product (savings/current/business), channel
 * (IBG / DuitNow / Instant / CDM), and bank format updates. Tune as you
 * collect failures from the parse_failures tab.
 */
function parseMBBEmail(msg) {
  const body = msg.getPlainBody() || '';

  const acctMatch = body.match(/account\s+(?:no\.?|number)?\s*[:\-]?\s*[\d\sxX*]*?(\d{4})\b/i);
  const amtMatch = body.match(/(?:RM|MYR)\s*([\d,]+\.\d{2})/i);
  const dirMatch = body.match(/\b(received|debited|transferred|credit(?:ed)?|debit|deducted|paid)\b/i);
  const dateMatch = body.match(/(\d{2})[\/\-](\d{2})[\/\-](\d{4})/);
  const refMatch = body.match(/(?:reference|ref\.?|trans(?:action)?\s*id)\s*[:\-]?\s*([A-Z0-9\-_]+)/i);

  if (!acctMatch || !amtMatch || !dateMatch) return null;

  const last4 = acctMatch[1];
  const account = ACCOUNT_LOOKUP[last4] || 'OTHER';
  const amount = parseFloat(amtMatch[1].replace(/,/g, ''));
  const dirRaw = (dirMatch && dirMatch[1]) ? dirMatch[1].toLowerCase() : 'received';
  const direction = /(received|credit|paid\s*to)/.test(dirRaw) ? 'CR' : 'DR';
  const value_date = `${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`;
  const narrative = (msg.getSubject() || '').slice(0, 100);
  const source_ref = refMatch ? refMatch[1] : '';

  return buildTxn_({
    bankCode: 'MBB',
    account,
    value_date,
    posting_date: formatDate_(msg.getDate()),
    amount,
    direction,
    narrative,
    source_ref,
    messageId: msg.getId(),
    source: 'email-mbb',
  });
}

// ---------- AmBank parser ----------

/**
 * AmBank alert format (bilingual EN + BM in the same email body).
 * Sample (credit / fund transfer in):
 *
 *   Dear Sir/Madam,
 *   Greetings from AmBank/AmBank Islamic!
 *   We are pleased to inform that you have received the following fund
 *   transfer credited to your Current/Savings Account/-i. The details
 *   are as below:
 *     Date & Time: 26/04/2026 07:24:09
 *     Transfer From: ROHANI
 *     To Current/Savings Account/-i No.: ***8146
 *     Bank Name: AmBank/AmBank Islamic
 *     Amount: MYR 59.70
 *     Transfer Details: Pindahan Dana
 *
 * The same body repeats in Bahasa Melayu lower down with labels like
 * "Tarikh & Masa", "Pemindahan Dari", "Akaun Semasa/Simpanan/-i No.",
 * "Amaun", "Butiran Pemindahan". The regex below matches either
 * language; first-match wins, and EN sits first in the body so EN is
 * preferred. Direction is inferred from the surrounding prose
 * ("credited to" → CR, "debited from" / "memindahkan" → DR), default
 * CR (safer for clearance: a missed credit is worse than a misclassed
 * debit).
 */
function parseAMBEmail(msg) {
  const body = msg.getPlainBody() || '';
  const subject = msg.getSubject() || '';

  // Account — match either "To/From <something> Account/-i No.: ***1234"
  // (EN) or "Akaun ... No.: ***1234" (BM). Stars are sometimes literal *
  // and sometimes the unicode bullet ●; allow either.
  const acctMatch =
    body.match(/(?:To|From|Kepada|Dari)\b[^:]{0,80}?Account[^:]*No\.?\s*:\s*[*•●xX]+\s*(\d{4})/i) ||
    body.match(/Akaun[^:]{0,80}?No\.?\s*:\s*[*•●xX]+\s*(\d{4})/i) ||
    body.match(/[*•●xX]{2,}\s*(\d{4})\b/);

  // Amount — "Amount: MYR 59.70" / "Amaun: RM 1,234.56"
  const amtMatch = body.match(/(?:Amount|Amaun)\s*:\s*(?:MYR|RM)\s*([\d,]+\.\d{2})/i);

  // Date & Time — "Date & Time: 26/04/2026 07:24:09" / "Tarikh & Masa: ..."
  const dtMatch = body.match(
    /(?:Date\s*(?:&|and)?\s*Time|Tarikh\s*(?:&|dan)?\s*Masa)\s*:\s*(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::\d{2})?)?/i
  );

  // Counterparty — "Transfer From: ROHANI" or "Transfer To: ..." / BM equivalents
  const partyMatch =
    body.match(/(?:Transfer\s+From|Pemindahan\s+Dari)\s*:\s*([^\r\n]+)/i) ||
    body.match(/(?:Transfer\s+To|Pemindahan\s+Kepada)\s*:\s*([^\r\n]+)/i);

  // Transfer details / narrative free-text
  const detailsMatch = body.match(/(?:Transfer\s+Details|Butiran\s+Pemindahan)\s*:\s*([^\r\n]+)/i);

  if (!acctMatch || !amtMatch || !dtMatch) return null;

  const last4 = acctMatch[1];
  const account = ACCOUNT_LOOKUP[last4] || 'OTHER';
  const amount = parseFloat(amtMatch[1].replace(/,/g, ''));

  // Direction inference
  let direction = 'CR';
  if (/credited\s+to\s+your|received\s+the\s+following|menerima/i.test(body)) direction = 'CR';
  else if (/debited\s+from\s+your|transferred\s+from\s+your|memindahkan|telah\s+keluar/i.test(body)) direction = 'DR';

  const value_date = `${dtMatch[3]}-${dtMatch[2]}-${dtMatch[1]}`;
  const posting_time = (dtMatch[4] && dtMatch[5])
    ? `${value_date} ${dtMatch[4]}:${dtMatch[5]}`
    : formatDate_(msg.getDate());

  const counterparty = partyMatch ? partyMatch[1].trim() : '';
  const details = detailsMatch ? detailsMatch[1].trim() : '';
  const narrativeParts = [counterparty, details].filter(Boolean);
  const narrative = (narrativeParts.length ? narrativeParts.join(' / ') : subject).slice(0, 200);

  return buildTxn_({
    bankCode: 'AMB',
    account,
    value_date,
    posting_date: posting_time,
    amount,
    direction,
    narrative,
    source_ref: '',
    messageId: msg.getId(),
    source: 'email-amb',
  });
}

// ---------- Helpers ----------

function buildTxn_(p) {
  const seed = `${p.account}|${p.value_date}|${p.amount}|${p.narrative}|${p.messageId}`;
  return {
    txn_id: sha256_(seed),
    account: p.account,
    value_date: p.value_date,
    posting_date: p.posting_date,
    amount: p.amount,
    direction: p.direction,
    narrative: p.narrative,
    source_ref: p.source_ref,
    source: p.source,
    ingested_at: formatDate_(new Date()),
    matched_slip: '',
    status: 'new',
  };
}

function appendTxnRow_(sheet, t) {
  sheet.appendRow([
    t.txn_id,
    t.account,
    t.value_date,
    t.posting_date,
    t.amount,
    t.direction,
    t.narrative,
    t.source_ref,
    t.source,
    t.ingested_at,
    t.matched_slip,
    t.status,
  ]);
}

function logFailure_(sheet, bankCode, msg, reason) {
  sheet.appendRow([
    formatDate_(new Date()),
    bankCode,
    msg.getId(),
    (msg.getSubject() || '').slice(0, 200),
    reason.slice(0, 500),
  ]);
}

function getColumnValues(sheet, col, startRow) {
  const last = sheet.getLastRow();
  if (last < startRow) return [];
  return sheet.getRange(startRow, col, last - startRow + 1).getValues().flat();
}

function getOrCreateLabel(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function sha256_(s) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8);
  return bytes.map(function (b) {
    const v = (b < 0) ? b + 256 : b;
    return ('0' + v.toString(16)).slice(-2);
  }).join('');
}

function formatDate_(d) {
  const tz = Session.getScriptTimeZone() || 'Asia/Kuala_Lumpur';
  return Utilities.formatDate(d, tz, 'yyyy-MM-dd HH:mm');
}

// ---------- doGet — query API for sale-audit clearance verification ----------

/**
 * HTTP GET handler exposed when the Apps Script project is deployed as
 * a Web App. Used by `sale-audit` (running on the Win 11 server or in
 * scheduled Cowork) to verify whether a proof-of-fund slip cleared.
 *
 * Required query parameters:
 *   token        — must equal the WEB_APP_TOKEN script property
 *   value_date   — YYYY-MM-DD; the slip's expected settlement date
 *
 * Optional query parameters:
 *   account        — `MBB-5366` etc.; restrict to one account
 *   amount         — exact amount in RM; tolerance ±0.01
 *   direction      — `CR` (default) or `DR`
 *   tolerance_days — integer 0..7 (default 3); accept value_date up to
 *                    +N working days later, used for cheques
 *
 * Response is always JSON with HTTP 200; the `ok` field signals success.
 *   { "ok": true, "matches": [ {...row}, ... ], "total_count": N }
 *   { "ok": false, "error": "<reason>" }
 *
 * Health-check call (no value_date): returns
 *   { "ok": true, "ping": "bank-ledger", "row_count": <int> }
 * so sale-audit can ping at start of run to verify connectivity.
 */
function doGet(e) {
  try {
    const params = (e && e.parameter) ? e.parameter : {};

    // Token check — fail fast and never reveal the expected token.
    const expected = PropertiesService.getScriptProperties().getProperty(TOKEN_PROPERTY_KEY);
    if (!expected) {
      return jsonResponse_({ ok: false, error: 'WEB_APP_TOKEN script property not configured' });
    }
    if (params.token !== expected) {
      return jsonResponse_({ ok: false, error: 'invalid token' });
    }

    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(TXN_TAB);
    if (!sheet) {
      return jsonResponse_({ ok: false, error: `tab "${TXN_TAB}" not found` });
    }

    // Health-check mode — caller did not supply value_date.
    if (!params.value_date) {
      const lastRow = sheet.getLastRow();
      return jsonResponse_({
        ok: true,
        ping: 'bank-ledger',
        row_count: Math.max(0, lastRow - 1),
      });
    }

    const targetDate = String(params.value_date).trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
      return jsonResponse_({ ok: false, error: 'value_date must be YYYY-MM-DD' });
    }

    const targetAccount = params.account ? String(params.account).trim() : null;
    const targetAmount = params.amount ? parseFloat(params.amount) : null;
    const direction = params.direction ? String(params.direction).toUpperCase().trim() : 'CR';
    const toleranceDays = Math.max(0, Math.min(7, parseInt(params.tolerance_days || '3', 10) || 0));

    const dateStart = parseISODate_(targetDate);
    const dateEnd = new Date(dateStart);
    dateEnd.setDate(dateEnd.getDate() + toleranceDays);

    const lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      return jsonResponse_({ ok: true, matches: [], total_count: 0 });
    }

    const data = sheet.getRange(2, 1, lastRow - 1, 12).getValues();
    const matches = [];

    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      const txn_id = row[0];
      const account = row[1];
      const value_date = String(row[2]).trim();
      const posting_date = row[3];
      const amount = parseFloat(row[4]);
      const dir = row[5];
      const narrative = row[6];
      const source_ref = row[7];
      const source = row[8];
      const ingested_at = row[9];
      const matched_slip = row[10];
      const status = row[11];

      const rowDate = parseISODate_(value_date);
      if (!rowDate) continue;
      if (rowDate < dateStart || rowDate > dateEnd) continue;

      if (direction && dir !== direction) continue;
      if (targetAccount && account !== targetAccount) continue;
      if (targetAmount !== null && Math.abs(amount - targetAmount) > 0.01) continue;

      matches.push({
        txn_id, account, value_date,
        posting_date: typeof posting_date === 'string' ? posting_date : formatDate_(posting_date),
        amount, direction: dir,
        narrative, source_ref, source,
        ingested_at: typeof ingested_at === 'string' ? ingested_at : formatDate_(ingested_at),
        matched_slip, status,
      });
    }

    return jsonResponse_({ ok: true, matches, total_count: matches.length });
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'unhandled: ' + String(err) });
  }
}

function jsonResponse_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function parseISODate_(s) {
  const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
}
