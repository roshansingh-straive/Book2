"""Recompare a saved analysis/audit with no network calls or credentials.

Accepts the pasted two-JSON-object format supplied in the issue, or an analysis
JSON plus --audit. The input and original audit are never modified.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.comparison import compare_books
from server.main import get_store, refreshed_analysis
from server.recognition import reprocess_audit, parse_readings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--first-pass-only', action='store_true', help='Use only saved read-phase replies; make no requests.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.input.resolve(), args.audit.resolve() if args.audit else None}:
        parser.error('Choose a separate output file; source evidence is preserved.')
    text = args.input.read_text(encoding='utf-8-sig')
    values = []
    decoder = json.JSONDecoder()
    while text.strip():
        value, offset = decoder.raw_decode(text.lstrip())
        values.append(value)
        text = text.lstrip()[offset:]
    result = next(value for value in values if isinstance(value,dict) and 'shelf_items' in value)
    audit = json.loads(args.audit.read_text()) if args.audit else next((value for value in values if isinstance(value,dict) and 'calls' in value and 'observations' in value), None)
    if audit and audit.get('run_id') != result.get('run_id'):
        parser.error('The audit and analysis have different run IDs.')
    store = get_store()
    bay = next(bay for bay in store['bays'] if bay['id'] == result['bay_id'])
    if args.first_pass_only and not audit:
        parser.error('--first-pass-only requires the original completed audit')
    selected_mode = 'single_pass' if args.first_pass_only else result.get('reading_mode', 'verified')
    updated = {**result, **compare_books(store,bay,reprocess_audit(audit, first_pass_only=args.first_pass_only), reading_mode=selected_mode)} if audit else refreshed_analysis(store,bay,result)
    if args.first_pass_only:
        selected = [call for call in audit['calls'] if call.get('pass') == 'read']
        parsed = [parse_readings(json.loads(call['response_text']), call['image_size']) for call in selected if call.get('complete')]
        updated['harness'] = {**result.get('harness', {}), 'calls_completed':len(selected), 'model_requests_made':len(selected), 'rotated_verification':False, 'reading_mode':'single_pass', 'source_calls_used':len(selected), 'source_total_calls':len(audit['calls']), 'new_model_requests_made':0,
                              'rejected_readings':sum(rejected for _, rejected in parsed),
                              'unlocated_readings':sum(book.box is None for readings, _ in parsed for book in readings.books)}
        # The original combined runtime/usage is not a measurement of this subset.
        updated['inference_duration_seconds'] = None
        updated['tokens_used'] = None
        updated['token_usage'] = None
        updated['mode'] = 'offline_reprocess'
        updated['disclosure'] = 'Offline selection of recorded first-pass replies; no new model calls or rotated rereading. Runtime and usage are not remeasured.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'before':result['metrics'],'after':updated['metrics'],'cleanup':updated['candidate_cleanup'],'output':str(args.output)},indent=2))


if __name__ == '__main__':
    main()
