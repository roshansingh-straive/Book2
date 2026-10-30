import React, { useEffect, useRef } from 'react';
import { X, ShieldCheck } from 'lucide-react';
import type { ScanResult } from '../types';

interface TrustModalProps { isOpen: boolean; onClose: () => void; scan: ScanResult; }
export const TrustModal: React.FC<TrustModalProps> = ({ isOpen, onClose, scan }) => {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (isOpen) dialog.current?.showModal(); else dialog.current?.close(); }, [isOpen]);
  return <dialog ref={dialog} onCancel={onClose} aria-labelledby="accuracy-title" className="m-auto bg-white rounded-2xl max-w-xl w-[calc(100%-2rem)] border border-slate-200 shadow-2xl p-0 max-h-[90dvh] backdrop:bg-slate-900/60">
    <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50"><div className="flex items-center gap-2.5"><ShieldCheck className="w-5 h-5 text-blue-600" /><div><h3 id="accuracy-title" className="font-bold text-slate-900 text-sm">Recognition &amp; accuracy</h3><p className="text-xs text-slate-500">What the analysis can tell you</p></div></div><button aria-label="Close accuracy information" onClick={onClose} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200"><X className="w-5 h-5" /></button></div>
    <div className="p-5 space-y-5 text-xs text-slate-600 leading-relaxed">
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl"><strong className="text-slate-900">{scan.source_kind === 'upload' ? 'Your uploaded photograph' : scan.mode === 'replay' ? 'Saved sample analysis' : 'New sample analysis'}</strong><p className="mt-1">{scan.source_kind === 'upload' ? 'Your original photo is used for recognition. Sample readings are never substituted for an uploaded photo.' : scan.mode === 'replay' ? 'This view uses a saved recognition reply from the reference benchmark. Loading it does not perform a new scan.' : 'This view uses a fresh reading of the selected sample photograph.'}</p></div>
      <div><strong className="block text-slate-900 mb-1">A closer look at every section</strong><p>New analyses correct camera orientation and read each overlapping section once at its original resolution. There is no rotated reread. Clear title text is matched to the catalogue; this is not independent verification. Earlier saved runs may include a second reading, which remains identified in their title details.</p></div>
      <div><strong className="block text-slate-900 mb-1">Uncertainty stays visible</strong><p>Title identity, estimated box location and shelf assignment are checked separately. A correct title remains matched when its box is uncertain. Unreliable boxes are hidden. Single-pass or ambiguous text still needs confirmation. A title that was not read may be obscured or too small to identify.</p></div>
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900"><strong>Review the original photo.</strong> The reference benchmark covers six photos and its answer key has known limitations. Historical scores do not measure this app’s current live model/harness or accuracy on your uploaded photo. No guaranteed accuracy percentage is claimed for this analysis.</div>
      <div><strong className="block text-slate-900 mb-1">You confirm the next step</strong><p>Planograms, inventory counts and sales data in this demo are simulated. Suggested checks never automatically change inventory. Reviewing a task does not establish that a shelf issue has been physically fixed.</p></div>
      {scan.source && <a className="text-blue-700 underline" href={`https://github.com/atharva-729/bookshelf-benchmark/blob/main/${scan.source.source_path}`} target="_blank" rel="noreferrer">View the saved recognition source</a>}
    </div>
    <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-3 text-xs text-slate-500"><a href="https://atharva-729.github.io/bookshelf-benchmark/" target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">Read the reference benchmark</a><button onClick={onClose} className="px-4 py-1.5 rounded-lg bg-slate-900 text-white">Close</button></div>
  </dialog>;
};
