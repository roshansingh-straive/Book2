import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ClipboardList, ShieldCheck } from 'lucide-react';
import { Header } from './Header';
import { Step1Planogram } from './Step1Planogram';
import { Step2ShelfScan } from './Step2ShelfScan';
import { Step3DiscrepancyView } from './Step3DiscrepancyView';
import { TrustModal } from './TrustModal';
import { consumeScanEvents } from '../scanStream';
import type { Bay, ScanHealth, ScanProgress, ScanResult, StoreData, UploadedPhoto } from '../types';
import type { FoundryAuthState } from '../foundryAuth';

interface AnalysisPageProps {
  bayId: string;
  uploadId: string | null;
  store: StoreData | null;
  health: ScanHealth | null;
  healthChecked: boolean;
  auth: FoundryAuthState;
  onSignIn: () => void;
  onRefreshAuth: () => void;
  onAuthenticationFailure: () => void;
  storeError: string | null;
  onHome: () => void;
  onSelectBay: (id: string) => void;
}
function emptyAnalysis(store: StoreData, bay: Bay, photo: UploadedPhoto): ScanResult {
  const assigned = Object.values(store.catalogue).filter(item => item.assigned_bay_id === bay.id);
  return { bay_id: bay.id, bay_code: bay.code, bay_name: bay.name, photo_filename: photo.filename,
    photo_url: photo.photo_url, upload_id: photo.upload_id, source_kind: 'upload', mode: 'live', reading_mode: 'single_pass', model: '', effort: '',
    scanned_at: null, inference_duration_seconds: null, tokens_used: null, estimated_cost_usd: null,
    metrics: { planogram_expected_items: assigned.length, shelf_items_detected: 0, matched_count: 0, missing_count: 0, misplaced_count: 0, planogram_compliance_pct: 0 },
    planogram_items: assigned, shelf_items: [], missing_items: [], misplaced_items: [], action_tasks: [] };
}
function analysisError(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (/does not have access|HTTP 403|permission/i.test(message)) {
    return 'Your company account does not have access to live analysis. Contact the LLM Foundry administrator; your photo and previous result are unchanged.';
  }
  if (/sign in|authentication|HTTP 401/i.test(message)) {
    return 'Your company sign-in is required for live analysis. Sign in again; your photo and previous result are unchanged.';
  }
  if (/unavailable|could not be reached|HTTP 5\d\d/i.test(message)) {
    return 'Live photo analysis is currently unavailable. Your photo and previous result are unchanged; try again later.';
  }
  if (/time limit|timed out|deadline/i.test(message)) {
    return 'A model reading took longer than the 4-minute limit, so the scan stopped. Your photo is still available; try again later.';
  }
  if (/response-size limit|output limit/i.test(message)) {
    return 'A photo section exceeded the response-size limit. No partial result was used. A retry starts again from the first section; oversized crops are split into smaller crops during that run.';
  }
  if (/no valid book readings|no usable readings/i.test(message)) {
    return 'A photo section still did not return usable title evidence, so the scan stopped without using partial results. Try a closer photo of fewer shelves.';
  }
  if (/already running|queued/i.test(message)) return 'Another shelf analysis is running. Please wait for it to finish, then try again.';
  if (/connection ended|before completion/i.test(message)) return 'The connection ended before analysis finished. Your photo is still available; please try again.';
  return 'The photo could not be analyzed. Your photo has been kept; please try again or contact the app administrator.';
}

export const AnalysisPage: React.FC<AnalysisPageProps> = ({ bayId, uploadId, store, health, auth, onSignIn, onRefreshAuth, onAuthenticationFailure, storeError, onHome, onSelectBay }) => {
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [photo, setPhoto] = useState<UploadedPhoto | null>(null);
  const [resultReady, setResultReady] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const comparisonController = useRef<AbortController | null>(null);
  const [mode, setMode] = useState<'replay' | 'live'>(uploadId ? 'live' : 'replay');
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hoveredItemId, setHoveredItemId] = useState<string | null>(null);
  const [highlightedSku, setHighlightedSku] = useState<string | null>(null);
  const [trustOpen, setTrustOpen] = useState(false);
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const scanController = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const bay = store?.bays.find(item => item.id === bayId && item.scannable);
  const liveAvailable = auth.status === 'signed-in' && (uploadId
    ? !!health?.upload_analysis_available
    : !!health?.live_available_by_difficulty[bay?.difficulty || 'hard']);

  useEffect(() => {
    if (!store || !bay) return;
    const controller = new AbortController();
    let active = true;
    async function load() {
      try {
        if (uploadId) {
          const [photoResponse, resultResponse] = await Promise.all([
            fetch(`/api/uploads/${encodeURIComponent(uploadId)}`, { signal: controller.signal }),
            fetch(`/api/uploads/${encodeURIComponent(uploadId)}/analysis/${bayId}`, { signal: controller.signal }),
          ]);
          if (!photoResponse.ok || !resultResponse.ok) throw new Error('This uploaded photo could not be found. Please upload it again.');
          const uploaded = await photoResponse.json() as UploadedPhoto;
          const saved = (await resultResponse.json()).result as ScanResult | null;
          if (saved && (saved.upload_id !== uploadId || saved.bay_id !== bayId || saved.photo_url !== uploaded.photo_url)) throw new Error('The saved analysis does not match this photo. Please upload it again.');
          if (active) { setPhoto(uploaded); setScan(saved ?? emptyAnalysis(store!, bay!, uploaded)); setResultReady(!!saved); }
        } else {
          const response = await fetch(`/data/scans/${bayId}.json`, { signal: controller.signal });
          if (!response.ok) throw new Error('The sample analysis could not be loaded. Please try again.');
          const saved = await response.json() as ScanResult;
          if (active) { setScan(saved); setResultReady(true); }
        }
      } catch (err) {
        if (active && !controller.signal.aborted) setLoadError(err instanceof Error ? err.message : 'This analysis could not be loaded.');
      }
    }
    void load();
    return () => { active = false; controller.abort(); scanController.current?.abort(); comparisonController.current?.abort(); generation.current += 1; };
  }, [store, bay, bayId, uploadId]);

  const runScan = async (requestedMode = mode) => {
    if (isScanning || isComparing || !scan) return;
    if (requestedMode === 'live' && auth.status !== 'signed-in') {
      setError(auth.status === 'connection-error'
        ? 'Company sign-in could not be checked. Retry the status check before starting analysis.'
        : 'Sign in to your company account before starting live analysis.');
      return;
    }
    if (requestedMode === 'live' && !liveAvailable) { setError(analysisError(new Error('unavailable'))); return; }
    const controller = new AbortController();
    scanController.current = controller;
    const current = ++generation.current;
    setIsScanning(true);
    setError(null);
    setProgress({ step: 0, status: 'preparing' });
    try {
      if (requestedMode === 'replay') {
        if (uploadId) throw new Error('Uploads cannot use sample results.');
        const response = await fetch(`/data/scans/${bayId}.json`, { signal: controller.signal });
        if (!response.ok) throw new Error('Sample unavailable');
        const result = await response.json() as ScanResult;
        if (generation.current === current) { setScan(result); setResultReady(true); }
      } else {
        const response = await fetch('/api/scan/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(auth.status === 'signed-in' ? { Authorization: `Bearer ${auth.token}` } : {}),
          },
          signal: controller.signal,
          body: JSON.stringify({ bay_id: bayId, mode: 'live', ...(uploadId ? { upload_id: uploadId } : {}) }),
        });
        await consumeScanEvents(response, event => {
          if (generation.current !== current) return;
          if (event.result) {
            if (event.result.bay_id !== bayId || (uploadId && (event.result.upload_id !== uploadId || event.result.photo_url !== photo?.photo_url))) throw new Error('Analysis does not match this photo.');
            setScan(event.result);
            setResultReady(true);
          }
          setProgress(event);
        }, onAuthenticationFailure);
      }
      if (generation.current === current) { setResolvedIds(new Set()); setHoveredItemId(null); setHighlightedSku(null); }
    } catch (err) {
      if (generation.current === current && !controller.signal.aborted) setError(analysisError(err));
    } finally {
      if (generation.current === current) { setIsScanning(false); setProgress(null); scanController.current = null; }
    }
  };
  const cancelScan = () => {
    generation.current += 1;
    scanController.current?.abort();
    scanController.current = null;
    setIsScanning(false);
    setProgress(null);
    setError('Analysis cancelled. Your photo is still available; you can run it again when you’re ready.');
  };

  const changeComparisonShelf = async (id: string) => {
    if (id === bayId || isScanning || isComparing) return;
    if (!uploadId || !resultReady) { onSelectBay(id); return; }
    setError(null);
    setIsComparing(true);
    const controller = new AbortController();
    comparisonController.current = controller;
    try {
      const response = await fetch(`/api/uploads/${uploadId}/recompare`, {
        signal: controller.signal,
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_bay_id: bayId, target_bay_id: id }),
      });
      if (!response.ok) throw new Error('Comparison could not be updated.');
      if (!controller.signal.aborted) onSelectBay(id);
    } catch { if (!controller.signal.aborted) setError('The comparison shelf could not be changed. Your completed result is unchanged; please try again.'); }
    finally { if (!controller.signal.aborted) setIsComparing(false); }
  };

  const loadingError = storeError || loadError || (store && !bay ? 'This shelf is unavailable. Please choose a shelf from the homepage.' : null);
  if (loadingError) return <div className="min-h-dvh bg-slate-50 flex flex-col items-center justify-center p-6 gap-4"><div role="alert" className="text-sm text-slate-700">{loadingError}</div><button onClick={onHome} className="inline-flex gap-2 text-sm text-blue-700 font-medium"><ArrowLeft className="w-4 h-4" /> Back to upload</button></div>;
  if (!store || !bay || !scan) return <div role="status" className="min-h-dvh bg-slate-50 flex flex-col items-center justify-center gap-3 text-sm text-slate-500"><div className="w-7 h-7 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />Preparing your shelf analysis…</div>;
  const tasks = scan.action_tasks.map(task => ({ ...task, resolved: resolvedIds.has(task.id) }));
  return <div className="min-h-dvh bg-slate-100/70 flex flex-col font-sans">
    <Header bays={store.bays} selectedBayId={bayId} onSelectBay={id => void changeComparisonShelf(id)} onHome={onHome} isUpload={!!uploadId} isScanning={isScanning || isComparing} resultMode={scan.mode}
      auth={auth} onSignIn={onSignIn} onRefreshAuth={onRefreshAuth}
      onOpenInfo={() => setTrustOpen(true)} />
    <main className="flex-1 max-w-[1700px] w-full mx-auto p-4 sm:p-6 lg:p-8">
      <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div><div className="text-[11px] text-slate-400 mb-1"><button onClick={onHome} className="hover:text-blue-700">Home</button><span className="mx-2">/</span>Analysis</div><h1 className="text-xl font-bold text-slate-900 tracking-tight">{uploadId ? 'Your shelf analysis' : bay.name}</h1><p className="text-xs text-slate-500 mt-1">{uploadId ? `Comparing your uploaded photo with ${bay.name}.` : 'Sample photograph and saved recognition, compared with a simulated planogram.'}</p></div>
        <button onClick={() => setTrustOpen(true)} className="inline-flex items-center self-start gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 text-xs font-medium"><ShieldCheck className="w-3.5 h-3.5 text-blue-600" /> Recognition &amp; accuracy</button>
      </div>
      {scan.comparison_suggestion && <div role="status" className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="text-sm font-semibold text-amber-950">Check the selected comparison shelf</p><p className="text-xs text-amber-800 leading-5 mt-1">{scan.comparison_suggestion.message} {scan.comparison_suggestion.matching_titles} titles match {scan.comparison_suggestion.bay_name}.</p></div>{uploadId && <button disabled={isScanning || isComparing} onClick={() => void changeComparisonShelf(scan.comparison_suggestion!.bay_id)} className="shrink-0 self-start rounded-lg bg-white border border-amber-300 px-3 py-2 text-xs font-semibold text-amber-950 disabled:opacity-50">{isComparing ? 'Updating comparison…' : 'Compare with suggested shelf'}</button>}</div>}
      {uploadId && resultReady && <p className="text-[11px] text-slate-500 mb-4">Change the shelf above to compare these same readings with another catalogue. No new image analysis is required.</p>}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        <div className="order-2 lg:order-1 lg:col-span-3 min-w-0"><Step1Planogram bay={bay} items={scan.planogram_items} highlightedSku={highlightedSku} onSelectSku={setHighlightedSku} /></div>
        <div className="order-1 lg:order-2 lg:col-span-5 min-w-0"><Step2ShelfScan scan={scan} mode={mode} onModeChange={setMode} liveAvailable={liveAvailable} isUpload={!!uploadId} resultReady={resultReady}
          progress={progress} error={error} onCancel={cancelScan} hoveredItemId={hoveredItemId} onHoverItem={setHoveredItemId} onSelectItem={item => { if (item.sku) setHighlightedSku(item.sku); }}
          isScanning={isScanning} comparisonBusy={isComparing} scanStep={Math.min(progress?.step ?? 0, 3)} onTriggerScan={() => void runScan()} /></div>
        <div className="order-3 lg:col-span-4 min-w-0">{resultReady ? <Step3DiscrepancyView tasks={tasks} metrics={scan.metrics} readingMode={scan.reading_mode} onResolveTask={id => setResolvedIds(previous => new Set([...previous, id]))} hoveredItemId={hoveredItemId} onHoverItem={setHoveredItemId} />
          : <section className="bg-white rounded-xl border border-slate-200 h-full min-h-64 flex flex-col"><div className="p-4 border-b border-slate-100 bg-slate-50/70 flex items-center gap-2"><span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 grid place-items-center text-xs font-bold">3</span><h2 className="text-sm font-bold">Review &amp; next steps</h2></div><div className="p-8 text-center my-auto"><ClipboardList className="w-8 h-8 text-slate-300 mx-auto mb-3" /><h3 className="text-sm font-semibold text-slate-700">{isScanning ? 'Reading your shelf' : 'Your results will appear here'}</h3><p className="text-xs text-slate-500 leading-6 mt-2">Recognized titles and possible discrepancies will appear when analysis completes.</p></div></section>}</div>
      </div>
    </main>
    <footer className="bg-white border-t border-slate-200 py-4 px-6 text-center text-xs text-slate-400">Shelf Check · Simulated planogram and inventory records · Actions require your review</footer>
    <TrustModal isOpen={trustOpen} onClose={() => setTrustOpen(false)} scan={scan} />
  </div>;
};
