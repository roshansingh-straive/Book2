import React, { useEffect, useRef, useState } from 'react';
import { ScanProgress, ScanResult, ShelfItem } from '../types';
import { Camera, RefreshCw, ZoomIn, ZoomOut, X, Maximize2 } from 'lucide-react';

interface Step2ShelfScanProps {
  scan: ScanResult;
  mode: 'replay' | 'live';
  onModeChange: (mode: 'replay' | 'live') => void;
  liveAvailable: boolean;
  isUpload: boolean;
  resultReady: boolean;
  progress: ScanProgress | null;
  error: string | null;
  onCancel: () => void;
  hoveredItemId: string | null;
  onHoverItem: (id: string | null) => void;
  onSelectItem: (item: ShelfItem) => void;
  isScanning: boolean;
  comparisonBusy?: boolean;
  scanStep: number;
  onTriggerScan: () => void;
}

export const Step2ShelfScan: React.FC<Step2ShelfScanProps> = ({
  scan, mode, onModeChange, liveAvailable, isUpload, resultReady, progress, error, onCancel,
  hoveredItemId, onHoverItem, onSelectItem, isScanning, comparisonBusy = false, scanStep, onTriggerScan,
}) => {
  const [outlineFilter, setOutlineFilter] = useState<'all' | 'issues' | 'none'>('none');
  const [waitSeconds, setWaitSeconds] = useState(0);
  const [activeTooltip, setActiveTooltip] = useState<ShelfItem | null>(null);
  const [photoOpen, setPhotoOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    setActiveTooltip(null);
    setOutlineFilter('none');
  }, [scan, resultReady]);

  useEffect(() => {
    if (photoOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [photoOpen]);

  useEffect(() => {
    if (!isScanning || progress?.completed_calls == null) {
      setWaitSeconds(0);
      return;
    }
    setWaitSeconds(0);
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setWaitSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isScanning, progress?.completed_calls, progress?.message, progress?.status]);

  const selectItem = (item: ShelfItem) => {
    setActiveTooltip(item);
    onHoverItem(item.id);
    onSelectItem(item);
  };
  const verificationLabel = (item: ShelfItem) => item.verification_status === 'single_pass'
    ? 'Single reading · Not independently verified' : item.title_status === 'agreed'
    ? 'Title agreed across two readings' : item.title_status === 'single_read'
    ? 'Title readable in one pass' : item.title_status === 'uncertain'
    ? 'Title text uncertain' : item.verification_status === 'verified'
    ? 'Agreed across two readings' : item.verification_status === 'needs_review'
    ? 'Needs human review' : 'Saved benchmark reading';
  const located = (item: ShelfItem) => !!item.box && (item.position_status === 'agreed' || item.position_status === 'estimated' || (!item.position_status && item.verification_status === 'verified'));

  const outlines = () => outlineFilter !== 'none' && scan.shelf_items.map(item => {
    if (!located(item) || !item.box || (outlineFilter === 'issues' && item.status === 'matched')) return null;
    const colour = item.status === 'matched' ? 'border-emerald-400 bg-emerald-500/10'
      : item.status === 'misplaced' ? 'border-amber-400 bg-amber-500/20'
      : item.status === 'needs_review' ? 'border-sky-400 bg-sky-500/10'
      : 'border-purple-400 bg-purple-500/20';
    return <button
      key={item.id} aria-label={`${item.title}: ${item.status_label}`}
      onMouseEnter={() => { onHoverItem(item.id); setActiveTooltip(item); }}
      onMouseLeave={() => onHoverItem(null)}
      onFocus={() => { onHoverItem(item.id); setActiveTooltip(item); }}
      onClick={() => selectItem(item)}
      style={{ top: `${item.box.top * 100}%`, left: `${item.box.left * 100}%`, width: `${item.box.width * 100}%`, height: `${item.box.height * 100}%` }}
      className={`absolute cursor-pointer border-2 rounded-xs ${item.position_status === 'estimated' ? 'border-dashed' : ''} ${colour} ${hoveredItemId === item.id ? 'ring-2 ring-blue-400 z-10' : ''}`}
    />;
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden flex flex-col h-full min-w-0">
      <div className="p-4 border-b border-slate-100 bg-slate-50/70">
        <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">2</span>
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">Shelf Photo &amp; AI Recognition</h2>
          </div>
          <button onClick={onTriggerScan} disabled={isScanning || comparisonBusy || (mode === 'live' && !liveAvailable)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-500 disabled:cursor-not-allowed">
            {isScanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
            <span>{isScanning ? 'Analyzing…' : mode === 'live' ? (resultReady ? (isUpload ? 'Start fresh scan' : 'Analyze again') : 'Analyze photo') : 'Reload sample'}</span>
          </button>
        </div>
        {!isUpload && <div className="flex flex-wrap gap-2 items-center mb-2">
          <label className="text-xs text-slate-600 flex items-center gap-2">
            Scan mode
            <select aria-label="Scan mode" value={mode} disabled={isScanning || comparisonBusy} onChange={e => onModeChange(e.target.value as 'replay' | 'live')} className="text-xs border border-slate-300 rounded-md bg-white px-2 py-1.5">
              <option value="replay">Saved sample analysis</option>
              <option value="live" disabled={!liveAvailable}>Run a new analysis</option>
            </select>
          </label>
        </div>}
        <p className="text-xs text-slate-500 leading-relaxed">
          {mode === 'live'
            ? 'New analyses read each full-resolution section once, without rotation or a second reading.'
            : 'Saved sample: previously recorded recognition results with no new LLM call or charge. Select Run a new analysis only for a fresh model scan.'}
        </p>
        {isUpload && mode === 'live' && !resultReady && !isScanning && <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
          Ready when you are. Select Analyze photo to read each section once and match its titles to the catalogue. Refreshing this page will not start a new analysis.
        </p>}
        {!liveAvailable && !error && <p className="text-[11px] text-amber-800 mt-1">Company sign-in and inference access are required for live photo analysis.</p>}
        {error && <div role="alert" className="mt-2 p-2 text-xs text-red-800 border border-red-200 bg-red-50 rounded-md">{error}</div>}
        {resultReady && scan.reading_mode === 'single_pass' && <p className="text-[11px] text-blue-700 mt-2">Single-pass analysis · No rotated reread · Locations are estimates</p>}
        <div className="mt-3 pt-3 border-t border-slate-200/60 text-xs space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-slate-700">{resultReady ? (isUpload ? 'Your photo · Analysis complete' : scan.mode === 'live' ? 'Sample · New analysis' : 'Sample · Saved analysis') : 'Your photo · Awaiting analysis'}</span>
            <span className="text-slate-500">{resultReady ? `${scan.shelf_items.length} title candidates` : 'Photo uploaded'}</span>
          </div>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-emerald-700">{resultReady ? <>Matched: {scan.metrics.matched_count} <span className="text-slate-400">· Review: {scan.metrics.review_count ?? 0}</span></> : <span className="text-slate-400">Results pending</span>}</span>
            <div className="flex items-center gap-1">
              <span className="text-slate-400 text-[11px]">Outlines:</span>
              {(['all', 'issues', 'none'] as const).map(filter => <button key={filter} disabled={filter !== 'none' && (!resultReady || !scan.shelf_items.some(located))} aria-pressed={outlineFilter === filter} onClick={() => setOutlineFilter(filter)} className={`px-2 py-0.5 rounded text-[11px] font-medium ${outlineFilter === filter ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 disabled:opacity-40 disabled:cursor-not-allowed'}`}>{filter === 'all' ? 'All' : filter === 'issues' ? 'Issues' : 'Off'}</button>)}
            </div>
          </div>
        </div>
      </div>

      {resultReady && !!scan.metrics.location_review_count && <div className="px-4 py-2.5 border-b border-blue-100 bg-blue-50 text-[11px] text-blue-900 leading-5">{scan.metrics.location_review_count} location estimates are unavailable or unconfirmed. Titles are retained. {scan.reading_mode === 'single_pass' ? 'Available boxes are single-reading estimates.' : 'Only agreed location estimates can be outlined.'} Inspect individual titles below.</div>}
      <div className="relative flex-1 bg-slate-900 flex items-center justify-center overflow-hidden min-h-[380px] select-none">
        <button aria-label="Open photo zoom" onClick={() => { setZoom(1); setPhotoOpen(true); }} className="absolute top-3 right-3 z-10 flex items-center gap-1.5 px-2.5 py-1.5 bg-white/95 rounded-lg text-xs font-medium text-slate-800 shadow-sm"><Maximize2 className="w-3.5 h-3.5" /> Zoom photo</button>
        <div className="relative inline-block max-h-[520px] max-w-full my-auto">
          <img src={scan.photo_url} alt={scan.bay_name} className="max-h-[520px] max-w-full w-auto h-auto object-contain block mx-auto" />
          {!isScanning && outlines()}
        </div>
        {isScanning && <div role="status" aria-live="polite" className="absolute inset-0 bg-slate-950/90 z-20 flex flex-col items-center justify-center p-6 text-white text-center">
          <RefreshCw className="w-10 h-10 text-blue-400 animate-spin mb-4" />
          <div className="text-sm font-bold mb-2">{mode === 'live' ? ['Preparing image', 'Reading full-resolution sections', 'Independent verification', 'Comparing planogram'][scanStep] : 'Loading saved reply'}</div>
          <p className="text-xs text-blue-200 max-w-xs mb-4">{scanStep === 0 ? 'Preparing your photo for a detailed reading.' : scanStep === 1 ? 'Reading visible titles across the shelf.' : scanStep === 2 ? 'Taking a second look at each section.' : 'Comparing recognized titles with the shelf planogram.'}</p>
          {!!progress?.total_checks && <>
            <div className="text-xs mb-2">
              {progress.completed_calls ?? 0} of {progress.total_calls} reading checks completed
              {(progress.completed_calls ?? 0) < (progress.total_calls ?? 0) && ` · Check in progress · ${Math.floor(waitSeconds / 60)}m ${waitSeconds % 60}s`}
            </div>
            <progress className="w-64 max-w-full accent-blue-500" value={progress.completed_calls ?? 0} max={Math.max(progress.total_calls ?? 0, 1)} />
          </>}
          <p className="text-[11px] text-slate-400 mt-3">Each model check is limited to 4 minutes.</p>
          <button onClick={onCancel} className="mt-4 px-4 py-1.5 rounded border border-slate-500 text-xs">Cancel scan</button>
        </div>}
      </div>

      {activeTooltip && <div className="p-3 bg-blue-50 border-t border-blue-100 text-xs relative">
        <button onClick={() => { setActiveTooltip(null); onHoverItem(null); }} aria-label="Close title details" className="absolute top-2 right-2 p-1 text-slate-500"><X className="w-3.5 h-3.5" /></button>
        <div className="font-semibold text-slate-900 pr-6">{activeTooltip.title}</div>
        <div className="text-slate-600">{activeTooltip.author || 'Author unreadable / unspecified'}</div>
        <div className="flex flex-wrap gap-1.5 mt-2"><span className={`rounded px-2 py-1 text-[10px] font-medium ${activeTooltip.catalogue_status === 'matched' || activeTooltip.status === 'matched' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>{activeTooltip.status_label}</span><span className="rounded bg-white border border-blue-100 px-2 py-1 text-[10px] text-blue-800">{verificationLabel(activeTooltip)}</span>{activeTooltip.position_status && <span className="rounded bg-white border border-blue-100 px-2 py-1 text-[10px] text-slate-600">{activeTooltip.position_status === 'agreed' ? 'Estimated location agreed' : activeTooltip.position_status === 'estimated' ? 'Estimated location · Single reading' : 'Location unconfirmed · title retained'}</span>}</div>
        {activeTooltip.catalogue_title && activeTooltip.catalogue_title.toLocaleLowerCase() !== activeTooltip.title.toLocaleLowerCase() && <div className="text-emerald-800 mt-2">Catalogue match: {activeTooltip.catalogue_title}</div>}
        {!!activeTooltip.title_variants?.length && activeTooltip.title_variants.some(title => title !== activeTooltip.title) && <div className="text-slate-500 mt-2">Combined readings: {activeTooltip.title_variants.join(' · ')}</div>}
        {!!activeTooltip.unconfirmed_variants?.length && <div className="text-slate-500 mt-2">Possible alternate text (not used to establish agreement): {activeTooltip.unconfirmed_variants.join(' · ')}</div>}
        {activeTooltip.visible_text && <div className="text-slate-600 mt-1">Visible text: “{activeTooltip.visible_text}”</div>}
        {activeTooltip.misplaced_reason && <div className="text-amber-800 mt-1">{activeTooltip.misplaced_reason}</div>}
      </div>}
      {resultReady && <details className="border-t border-slate-200 text-xs">
        <summary className="p-3 cursor-pointer font-medium text-slate-700">Inspect {scan.shelf_items.length} title candidates</summary>
        <div className="max-h-48 overflow-y-auto divide-y divide-slate-100">
          {scan.shelf_items.map(item => <button key={item.id} onClick={() => selectItem(item)} className="block w-full text-left px-3 py-2 hover:bg-blue-50"><span className="font-medium text-slate-800">{item.title}</span><span className="block text-[11px] text-slate-500 mt-0.5">{item.status_label} · {item.position_status === 'needs_review' ? 'Location unconfirmed' : verificationLabel(item)}</span></button>)}
        </div>
      </details>}
      {resultReady && !!scan.unresolved_readings?.length && <details className="border-t border-slate-200 text-xs"><summary className="p-3 cursor-pointer font-medium text-slate-500">Unresolved text · {scan.unresolved_readings.length} groups excluded from title count</summary><p className="px-3 pb-2 text-[11px] text-slate-500 leading-5">Author-only text, placeholders, uncertain fragments and possible duplicate readings remain available for inspection. They are not claimed as additional books.</p><div className="max-h-40 overflow-y-auto divide-y divide-slate-100">{scan.unresolved_readings.map((item,index) => <div key={index} className="px-3 py-2 text-[11px] text-slate-500"><span className="font-medium">{item.visible_text || item.title}</span><span className="block">{item.exclusion_reason === 'author_only' ? 'Author-only text' : item.exclusion_reason === 'placeholder' ? 'No readable title' : item.exclusion_reason === 'possible_duplicate' ? `Possible alternate reading of ${item.related_title}` : 'Uncertain text'} · excluded from title count</span></div>)}</div></details>}
      <div className="p-2.5 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-500 space-y-1">
        <div className="break-words">{scan.photo_filename} · {resultReady ? (scan.mode === 'replay' ? 'Saved sample' : scan.reading_mode === 'single_pass' ? 'Single-reading location estimates; inspect the photo' : 'Confirmed location estimates only; outlines are optional') : 'Uploaded photo'}</div>
        {!!scan.harness?.unlocated_readings && <div className="text-slate-500">Some model boxes could not be validated. Readable titles are retained; uncertain locations are not outlined.</div>}
        {!!scan.harness?.rejected_readings && <div role="status" className="text-amber-800">{scan.harness.rejected_readings} invalid model reading{scan.harness.rejected_readings === 1 ? '' : 's'} omitted; review the photo for missed titles.</div>}
        <div>{resultReady && scan.inference_duration_seconds != null ? `Analysis time: ${scan.inference_duration_seconds}s` : 'Review readings against the original photo before taking action.'}</div>
      </div>

      <dialog ref={dialog} onClose={() => setPhotoOpen(false)} aria-label="Full-resolution shelf photo" className="fixed inset-0 m-0 w-screen h-dvh max-w-none max-h-none bg-slate-950 text-white backdrop:bg-slate-950/90 p-0">
        <div className="flex items-center justify-between gap-2 p-4 border-b border-slate-700">
          <span className="text-sm font-semibold">{scan.bay_code} · Inspect shelf photo</span>
          <div className="flex items-center gap-2">
            <button aria-label="Zoom out" onClick={() => setZoom(z => Math.max(1, z - 0.5))} disabled={zoom <= 1} className="p-2 rounded bg-slate-800 disabled:opacity-30"><ZoomOut className="w-4 h-4" /></button>
            <span className="text-xs tabular-nums w-10 text-center">{zoom * 100}%</span>
            <button aria-label="Zoom in" onClick={() => setZoom(z => Math.min(4, z + 0.5))} disabled={zoom >= 4} className="p-2 rounded bg-slate-800 disabled:opacity-30"><ZoomIn className="w-4 h-4" /></button>
            <button aria-label="Close photo zoom" onClick={() => setPhotoOpen(false)} className="p-2 rounded bg-slate-800"><X className="w-4 h-4" /></button>
          </div>
        </div>
        <div className="overflow-auto h-[calc(100dvh-74px)]"><div className="relative" style={{ width: `${zoom * 100}%` }}><img src={scan.photo_url} alt={`Full-resolution ${scan.bay_name}`} className="w-full h-auto block" />{outlines()}</div></div>
      </dialog>
    </div>
  );
};
