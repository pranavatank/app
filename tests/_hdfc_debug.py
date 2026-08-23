import sys
sys.path.insert(0, r"B:\Study\App\App")

from engines.statement_parser import GenericPDFParser, parse_statement_with_debug, extract_statement_text
from engines.statement_metadata_extractor import extract_account_metadata

path = r"D:\New folder\2026-27\2025-26\PAT\Statement\HDFC.pdf"
pwd = "291377566"

text = extract_statement_text(path, "PDF", password=pwd)
meta = extract_account_metadata(text)
print("=== METADATA ===")
for k, v in meta.items():
    if v:
        print(f"  {k}: {v}")
print("any values:", any(meta.values()))

txns, debug = parse_statement_with_debug(path, "PDF", "HDFC Bank", password=pwd)
print(f"\n=== PARSE: {len(txns)} txns ===")
for t in txns[:5]:
    print(f"  {t['transaction_date']} | {t['transaction_type']} | {t['amount']} | {t['description'][:60]}")
print("...")
for t in txns[-3:]:
    print(f"  {t['transaction_date']} | {t['transaction_type']} | {t['amount']} | {t['description'][:60]}")
print(f"\nIssues ({len(debug['issues'])}):")
for i in debug["issues"][:8]:
    print(f"  {i}")
