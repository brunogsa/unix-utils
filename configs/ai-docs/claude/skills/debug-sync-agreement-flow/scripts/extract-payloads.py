#!/usr/bin/env python3
"""Extract the request/response/callback payloads of one transaction from a CloudWatch Insights CSV.

The CSVs produced by scripts/rotation-support/aws/logs/get-logs-from-insights.js hold one row per
log line, with the full raw JSON log line in the `@message` column. A single transaction produces
hundreds of rows, most of them unrelated HTTP calls (Salesforce, DynamoDB, SQS), because every
outbound call is logged by the same `AxiosHttpClient.executeRequest`. Isolating the calls that
matter therefore needs two filters: the transaction id, then an `httpUrl` substring.

Modes:
  --list-transactions   discover transaction ids in a CSV (optionally narrowed by --grep)
  (default)             extract one transaction's payloads

Usage:
    # 1. Discover the transaction id for a contract version
    extract-payloads.py --csv core.csv --list-transactions --grep 766128

    # 2. Pull that transaction's payloads (pretty JSON, one ###section### per payload —
    #    paste each body into a fenced ```json block in the notes file)
    extract-payloads.py --csv core.csv --middleware-csv middleware.csv \\
        --transaction-id 525e14b8-a0ba-4ef0-9bac-b22aad5c674b \\
        --erp-url-filter SalesAgreements --callback-url-filter contract_callback \\
        --trim-field DetalhesContrato --trim-field KIT

Exit codes: 0 on success, 1 on a usage/IO error, 2 when the transaction id matched no rows.
"""
import argparse
import csv
import json
import sys
from typing import Any, Dict, Optional

# Emitted by AxiosHttpClient.executeRequest for every outbound HTTP call.
REQUEST_MSG = "HTTP request body"
RESPONSE_MSG = "HTTP response details"
FAILURE_MSG = "HTTP request failed with 4XX or 5XX"

# The inbound webhook, as logged by the middleware. Either message carries the payload; the first
# one found wins, since they are two renderings of the same body.
WEBHOOK_FIELDS = {
    "Message to be queued": "messageBody",
    "SQS message details": "payload",
}

SECTIONS = (
    "webhook",
    "erp_request",
    "erp_response",
    "erp_error",
    "callback_request",
    "callback_response",
)


def raise_csv_field_limit():
    """A raw `@message` holding a full contract body exceeds the 131072-char default and raises."""
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_log_line(row):
    """Return the parsed `@message` JSON, or None when the line is not JSON.

    Not every log line is structured — plain-text lines exist and must not abort the run.
    """
    raw = row.get("@message")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def row_transaction_id(row, parsed):
    """Prefer the CSV column, fall back to the log line — the query may not have selected it."""
    return row.get("transactionId") or (parsed or {}).get("transactionId")


def row_message(row, parsed):
    return row.get("message") or (parsed or {}).get("message")


def iter_transaction(rows, transaction_id):
    """Yield (row, parsed) for the rows belonging to one transaction, in file order."""
    for row in rows:
        parsed = parse_log_line(row)
        if row_transaction_id(row, parsed) == transaction_id:
            yield row, parsed


def trim_fields(node, field_names):
    """Recursively replace any array whose key matches `field_names` with a count-bearing note.

    Bulky line-item arrays (contract details, kit SKUs) crowd out the fields under investigation
    and can push a Jira comment past a readable size. Matching is case-insensitive so one flag
    covers both a request's `DetalhesContrato` and a response's `detalhesContrato`.
    """
    if not field_names:
        return node
    wanted = {name.lower() for name in field_names}
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key.lower() in wanted and isinstance(value, list):
                result[key] = f"[omitido: {len(value)} itens — preservado no CSV bruto]"
            else:
                result[key] = trim_fields(value, field_names)
        return result
    if isinstance(node, list):
        return [trim_fields(item, field_names) for item in node]
    return node


def extract_webhook(rows, transaction_id) -> Optional[Any]:
    for row, parsed in iter_transaction(rows, transaction_id):
        message = row_message(row, parsed)
        field = WEBHOOK_FIELDS.get(message) if message else None
        if field and parsed and parsed.get(field) is not None:
            return parsed[field]
    return None


def extract_http_calls(rows, transaction_id, url_filter) -> Dict[str, Any]:
    """Collect the request/response/error of the calls whose `httpUrl` contains `url_filter`.

    A transaction may repeat a call (retries); the last occurrence wins, which is the outcome the
    callback reports.
    """
    found: Dict[str, Any] = {"request": None, "response": None, "error": None}
    if not url_filter:
        return found
    for row, parsed in iter_transaction(rows, transaction_id):
        if not parsed or url_filter not in (parsed.get("httpUrl") or ""):
            continue
        message = row_message(row, parsed)
        if message == REQUEST_MSG:
            found["request"] = {
                "method": parsed.get("httpMethod"),
                "url": parsed.get("httpUrl"),
                "body": parsed.get("body"),
            }
        elif message == RESPONSE_MSG:
            found["response"] = parsed.get("responseBody")
        elif message == FAILURE_MSG:
            found["error"] = {
                "statusCode": parsed.get("statusCode"),
                "errorResponse": parsed.get("errorResponse"),
            }
    return found


def list_transactions(rows, grep):
    """Summarise the transactions present in a CSV, newest activity last."""
    summary = {}
    for row in rows:
        raw = row.get("@message") or ""
        if grep and grep not in raw:
            continue
        parsed = parse_log_line(row)
        transaction_id = row_transaction_id(row, parsed)
        if not transaction_id:
            continue
        timestamp = row.get("@timestamp") or ""
        entry = summary.setdefault(
            transaction_id, {"first": timestamp, "last": timestamp, "rows": 0}
        )
        entry["rows"] += 1
        entry["first"] = min(entry["first"], timestamp) if entry["first"] else timestamp
        entry["last"] = max(entry["last"], timestamp) if entry["last"] else timestamp
    return dict(sorted(summary.items(), key=lambda item: item[1]["first"]))


def build_evidence(args):
    core_rows = load_rows(args.csv)
    webhook_rows = load_rows(args.middleware_csv) if args.middleware_csv else core_rows

    erp = extract_http_calls(core_rows, args.transaction_id, args.erp_url_filter)
    callback = extract_http_calls(core_rows, args.transaction_id, args.callback_url_filter)

    evidence = {
        "transactionId": args.transaction_id,
        "webhook": extract_webhook(webhook_rows, args.transaction_id),
        "erp_request": erp["request"],
        "erp_response": erp["response"],
        "erp_error": erp["error"],
        "callback_request": callback["request"]["body"] if callback["request"] else None,
        "callback_response": callback["response"],
    }
    return {
        key: trim_fields(value, args.trim_field) if key in SECTIONS else value
        for key, value in evidence.items()
    }


def emit(evidence, minified):
    # One section per header. Pretty by default — paste each body straight into a fenced
    # ```json block in the notes file. --minified collapses it to one line instead.
    for section in SECTIONS:
        print(f"###{section}###")
        value = evidence.get(section)
        if value is None:
            print("NULL")
        elif minified:
            print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        else:
            print(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Extract one transaction's payloads from a CloudWatch Insights CSV."
    )
    parser.add_argument("--csv", required=True, help="CSV holding the core log rows")
    parser.add_argument(
        "--middleware-csv",
        help="CSV holding the middleware rows (the inbound webhook); defaults to --csv",
    )
    parser.add_argument("--transaction-id", help="transaction id to extract")
    parser.add_argument(
        "--list-transactions",
        action="store_true",
        help="list the transaction ids in the CSV instead of extracting",
    )
    parser.add_argument(
        "--grep", help="with --list-transactions, only count rows whose raw log line contains this"
    )
    parser.add_argument(
        "--erp-url-filter",
        default="SalesAgreements",
        help="httpUrl substring identifying the ERP call (default: SalesAgreements)",
    )
    parser.add_argument(
        "--callback-url-filter",
        default="contract_callback",
        help="httpUrl substring identifying the callback (default: contract_callback)",
    )
    parser.add_argument(
        "--trim-field",
        action="append",
        default=[],
        help="replace this array field with a count note; repeatable, case-insensitive",
    )
    parser.add_argument(
        "--minified",
        action="store_true",
        help="single-line JSON per section instead of the pretty (indent=2) default",
    )
    args = parser.parse_args()

    raise_csv_field_limit()

    try:
        if args.list_transactions:
            found = list_transactions(load_rows(args.csv), args.grep)
            if not found:
                print("No transactions matched.", file=sys.stderr)
                return 2
            for transaction_id, info in found.items():
                print(f"{transaction_id}  {info['first']} .. {info['last']}  ({info['rows']} rows)")
            return 0

        if not args.transaction_id:
            parser.error("--transaction-id is required unless --list-transactions is used")

        evidence = build_evidence(args)
    except OSError as error:
        print(f"Error reading CSV: {error}", file=sys.stderr)
        return 1

    if all(evidence.get(section) is None for section in SECTIONS):
        print(
            f"No rows matched transactionId {args.transaction_id}. "
            "Check the id, the CSV, and the date range of the query.",
            file=sys.stderr,
        )
        return 2

    for section in SECTIONS:
        if evidence.get(section) is None:
            print(f"Warning: no {section} found for this transaction.", file=sys.stderr)

    emit(evidence, args.minified)
    return 0


if __name__ == "__main__":
    sys.exit(main())
