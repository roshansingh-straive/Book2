import type { ScanProgress } from './types';

// fetch supports POST and AbortController; EventSource only supports GET.
export async function consumeScanEvents(
  response: Response,
  onEvent: (event: ScanProgress) => void,
  onAuthenticationFailure?: () => void,
) {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401) onAuthenticationFailure?.();
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Scan request failed (${response.status}).`);
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('The scanning server did not return a progress stream.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || '';
      for (const frame of frames) {
        const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!data) continue; // heartbeat
        const event = JSON.parse(data) as ScanProgress;
        if (event.status === 'error') {
          if (event.code === 'authentication') onAuthenticationFailure?.();
          throw new Error(event.message || 'Live scan failed.');
        }
        if (event.status === 'complete' && !event.result) throw new Error('Scan finished without a result.');
        onEvent(event);
        if (event.status === 'complete') completed = true;
      }
      if (done) break;
    }
    if (!completed) throw new Error('The scan connection ended before completion. Please retry.');
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
