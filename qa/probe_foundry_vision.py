"""One explicit vision probe. Credentials are read without echo and never saved.

This script sends exactly one POST, with no redirects or automatic retries.
Run manually only when a company gateway test is requested.
"""
import argparse
import base64
import getpass
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = 'https://llmfoundry.straivedemo.com/gemini/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent?alt=sse'
MODEL_ID = 'gemini-3.1-pro-preview'
PROJECT = 'llmproxy-playground'
IMAGE = ROOT / 'qa/foundry_probe_crop.jpg'
OUT = ROOT / 'qa/foundry_probe_result.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hi', action='store_true', help='Send only a simple Hi prompt, without an image.')
    args = parser.parse_args()
    raw = b'' if args.hi else IMAGE.read_bytes()
    body = {
        'contents': [{'role': 'user', 'parts': [
            {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(raw).decode('ascii')}},
            {'text': 'Read at most two different book titles visible in this image. Do not guess. List each title once. Include the author only if readable in the image; otherwise use null. Return only JSON of the form {"books":[{"title":"...","author":null}]}.'},
        ]}],
        'generationConfig': {'temperature': 1, 'maxOutputTokens': 2048, 'thinkingConfig': {'thinkingLevel': 'LOW'}},
    }
    if args.hi:
        body = {
            'system_instruction': {'parts': [{'text': 'You are a helpful assistant'}]},
            'contents': [{'role': 'user', 'parts': [{'text': 'Hi'}]}],
            'generationConfig': {'temperature': 1},
        }
    output_path = ROOT / 'qa/foundry_hi_result.json' if args.hi else OUT
    token = getpass.getpass('Foundry token (hidden; held in memory only): ').strip()
    if not token:
        print('No token provided. No request made.')
        return
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'endpoint': ENDPOINT,
              'post_attempts': 1, 'image': str(IMAGE.relative_to(ROOT)), 'image_bytes': len(raw),
              'http_status': None, 'status': 'started'}
    if args.hi:
        report.pop('image')
        report.pop('image_bytes')
        report['prompt'] = 'Hi'
    started = time.monotonic()
    parts, finish_reason, events = [], None, 0
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False, transport=httpx.HTTPTransport(retries=0)) as client:
            headers = {'Authorization': f'Bearer {token}:{PROJECT}', 'Content-Type': 'application/json'}
            with client.stream('POST', ENDPOINT, headers=headers, json=body) as response:
                report['http_status'] = response.status_code
                report['content_type'] = response.headers.get('content-type', '')
                if not 200 <= response.status_code < 300:
                    report['status'] = 'http_error'
                    report['error'] = f'Gateway returned HTTP {response.status_code}. No retry was attempted.'
                else:
                    for line in response.iter_lines():
                        if time.monotonic() - started > 120:
                            report['status'] = 'deadline_exceeded'
                            break
                        if not line.startswith('data:'):
                            continue
                        data = line[5:].strip()
                        if not data or data == '[DONE]':
                            continue
                        event = json.loads(data)
                        events += 1
                        if event.get('error'):
                            report['status'] = 'provider_error'
                            report['error'] = 'The inference service returned an error event.'
                            break
                        if 'usageMetadata' in event:
                            report['usage'] = event['usageMetadata']
                        if 'modelVersion' in event:
                            report['returned_model'] = event['modelVersion']
                        for candidate in event.get('candidates', []):
                            for part in candidate.get('content', {}).get('parts', []):
                                if part.get('text') and not part.get('thought'):
                                    parts.append(part['text'])
                            if candidate.get('finishReason'):
                                finish_reason = candidate['finishReason']
                    else:
                        if report['status'] == 'started':
                            report['status'] = 'incomplete'
                    report['sse_events'] = events
                    report['finish_reason'] = finish_reason
                    text = ''.join(parts).strip()
                    returned_model = report.get('returned_model', '')
                    if finish_reason == 'STOP' and text and (
                        returned_model == MODEL_ID or returned_model.startswith(MODEL_ID + '-')
                    ):
                        report['status'] = 'complete'
                    elif finish_reason == 'STOP' and text and returned_model:
                        report['status'] = 'model_mismatch'
                    # Responses may wrap JSON in a Markdown code fence.
                    cleaned = text
                    if cleaned.startswith('```'):
                        cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                    if text:
                        try:
                            report['result'] = json.loads(cleaned)
                        except ValueError:
                            report['response_text'] = text[:2000]
    except (httpx.HTTPError, ValueError) as exc:
        report['status'] = 'connection_or_format_error'
        report['error_type'] = type(exc).__name__
    finally:
        report['duration_seconds'] = round(time.monotonic() - started, 2)
        # Never persist or print the bearer, even if a provider unexpectedly echoes it.
        safe = json.dumps(report, ensure_ascii=False, indent=2).replace(token, '[REDACTED]')
        token = ''
        output_path.write_text(safe + '\n', encoding='utf-8')
        print(safe, flush=True)


if __name__ == '__main__':
    main()
