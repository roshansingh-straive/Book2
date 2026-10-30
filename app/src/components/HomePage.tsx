import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, ChevronRight, ImagePlus, Layers, LoaderCircle, ScanLine, Upload, X } from 'lucide-react';
import type { StoreData, UploadedPhoto } from '../types';
import type { FoundryAuthState } from '../foundryAuth';
import { FoundryStatus } from './FoundryStatus';

interface HomePageProps {
  store: StoreData | null;
  loadError: string | null;
  liveAvailable: boolean | null;
  auth: FoundryAuthState;
  onSignIn: () => void;
  onRefreshAuth: () => void;
  onAnalyze: (photo: UploadedPhoto, bayId: string) => void;
  onSample: (bayId: string) => void;
}
const MAX_BYTES = 20 * 1024 * 1024;
const FORMATS = new Set(['image/jpeg', 'image/png', 'image/webp']);

export const HomePage: React.FC<HomePageProps> = ({ store, loadError, liveAvailable, auth, onSignIn, onRefreshAuth, onAnalyze, onSample }) => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [bayId, setBayId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const bays = store?.bays.filter(bay => bay.scannable) ?? [];
  const selectedBay = bays.find(bay => bay.id === bayId);

  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => () => request.current?.abort(), []);

  const chooseFile = (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    const next = files[0];
    if (files.length !== 1) { setError('Please choose one shelf photo at a time.'); setFile(null); return; }
    if (!FORMATS.has(next.type)) { setError('Choose a JPG, PNG or WebP image.'); setFile(null); return; }
    if (next.size > MAX_BYTES) { setError('Choose an image smaller than 20 MB.'); setFile(null); return; }
    if (!next.size) { setError('This file is empty. Please choose another photo.'); setFile(null); return; }
    setFile(next);
  };
  const removeFile = () => {
    setFile(null);
    setPreview('');
    setError(null);
    if (input.current) input.current.value = '';
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !bayId || uploading) return;
    const controller = new AbortController();
    request.current = controller;
    setUploading(true);
    setError(null);
    try {
      const response = await fetch(`/api/uploads?filename=${encodeURIComponent(file.name)}`, {
        method: 'POST', headers: { 'Content-Type': file.type }, body: file, signal: controller.signal,
      });
      if (!response.ok) {
        if (response.status === 413) throw new Error('Choose an image smaller than 20 MB.');
        if (response.status === 422) throw new Error('This image could not be read. Choose a valid JPG, PNG or WebP photo under 40 megapixels.');
        throw new Error('The photo could not be uploaded. Please try again.');
      }
      const photo = await response.json() as UploadedPhoto;
      if (!photo.upload_id || !photo.photo_url) throw new Error('The upload did not finish. Please try again.');
      if (!controller.signal.aborted) onAnalyze(photo, bayId);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'The upload failed. Please try again.');
    } finally {
      if (!controller.signal.aborted) setUploading(false);
    }
  };

  return <div className="min-h-dvh bg-[#f7f9fc] text-slate-900 flex flex-col">
    <header className="bg-white border-b border-slate-200/80">
      <div className="max-w-6xl mx-auto px-5 sm:px-8 min-h-20 py-3 flex flex-wrap sm:flex-nowrap items-center justify-between gap-3 sm:gap-4 sm:h-20 sm:py-0">
        <div className="flex items-center gap-2.5"><span className="w-9 h-9 rounded-xl bg-blue-600 text-white grid place-items-center"><Layers className="w-5 h-5" /></span><span className="text-lg font-bold tracking-tight">Shelf Check</span></div>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 min-w-0">
          <button onClick={() => onSample('bay_f3')} title="Opens recorded results instantly, without a paid LLM request." className="text-xs sm:text-sm text-slate-600 hover:text-blue-700 flex items-center gap-1.5">Explore a sample <ChevronRight className="w-4 h-4" /></button>
          <FoundryStatus auth={auth} onSignIn={onSignIn} onRefresh={onRefreshAuth} />
        </div>
      </div>
    </header>
    <main className="w-full max-w-6xl mx-auto px-5 sm:px-8 py-10 sm:py-16 lg:py-20 flex-1">
      <div className="grid lg:grid-cols-[1fr_1.05fr] gap-10 lg:gap-20 items-start">
        <div className="lg:pt-8">
          <span className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-100 px-3 py-1.5 text-[11px] font-semibold tracking-wide text-blue-700"><ScanLine className="w-3.5 h-3.5" /> PHOTO TO PLANOGRAM</span>
          <h1 className="mt-6 text-4xl sm:text-5xl lg:text-[56px] leading-[1.08] font-semibold tracking-[-0.045em]">A clear picture<br />of your <span className="text-blue-600">shelf.</span></h1>
          <p className="mt-5 text-base leading-7 text-slate-500 max-w-sm">Upload a shelf photo. We’ll read the visible titles, compare them with your planogram, and bring possible mismatches into one view.</p>
          <ol className="hidden lg:block mt-9 space-y-5 max-w-sm">
            {[
              ['Add your photo', 'A clear, full-resolution view works best.'],
              ['Select the shelf', 'Choose the planogram to compare against.'],
              ['Review the analysis', 'Inspect recognized titles and possible discrepancies.'],
            ].map(([title, description], index) => <li key={title} className="flex gap-3.5 items-start"><span className="w-7 h-7 shrink-0 rounded-full bg-white border border-slate-200 grid place-items-center text-xs font-semibold text-slate-500">{index + 1}</span><div><div className="text-sm font-semibold">{title}</div><p className="text-sm leading-6 text-slate-500">{description}</p></div></li>)}
          </ol>
          <div className="hidden lg:flex mt-9 items-center gap-2 text-xs text-slate-500"><Check className="w-4 h-4 text-emerald-600" /> You review every suggested action.</div>
        </div>
        <form onSubmit={submit} className="bg-white rounded-2xl border border-slate-200 shadow-[0_12px_40px_-24px_rgba(15,23,42,0.3)] p-5 sm:p-7">
          <h2 className="text-lg font-semibold tracking-tight">Start a shelf check</h2>
          <p className="text-sm text-slate-500 mt-1 mb-5">One shelf. One photo. A closer look.</p>
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Shelf photo" disabled={uploading} onChange={e => chooseFile(e.target.files)} className="sr-only" />
          <div role="group" aria-label="Shelf photo upload" onDragOver={e => { e.preventDefault(); if (!uploading) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); if (!uploading) chooseFile(e.dataTransfer.files); }} className={`rounded-xl border-2 border-dashed transition-colors ${dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50/70'}`}>
            {preview ? <div className="p-3">
              <div className="relative rounded-lg overflow-hidden bg-slate-100"><img src={preview} alt="Selected shelf photo preview" className="w-full h-56 object-contain" onError={() => { setError('This image could not be opened. Please choose another photo.'); setFile(null); }} onLoad={e => { if (e.currentTarget.naturalWidth * e.currentTarget.naturalHeight > 40_000_000) { setError('Choose a photo under 40 megapixels.'); setFile(null); } }} /><button type="button" aria-label="Remove photo" onClick={removeFile} disabled={uploading} className="absolute top-2 right-2 p-1.5 rounded-full bg-white shadow-sm text-slate-600 disabled:opacity-40"><X className="w-4 h-4" /></button></div>
              <div className="flex items-center justify-between gap-3 mt-3"><div className="min-w-0"><p className="text-xs font-medium text-slate-700 truncate">{file?.name}</p><p className="text-[11px] text-slate-400 mt-0.5">{file ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : ''}</p></div><button type="button" onClick={() => input.current?.click()} disabled={uploading} className="text-xs font-semibold text-blue-600 shrink-0">Change photo</button></div>
            </div> : <div className="text-center px-4 py-9 sm:py-10"><span className="mx-auto w-12 h-12 rounded-xl border border-slate-200 bg-white grid place-items-center text-blue-600 mb-4"><ImagePlus className="w-6 h-6" /></span><p className="text-sm font-semibold">Drag your shelf photo here</p><p className="text-xs text-slate-400 mt-1">or choose one from your device</p><button type="button" onClick={() => input.current?.click()} disabled={uploading} className="mt-4 inline-flex gap-2 items-center px-4 py-2 rounded-lg border border-slate-200 bg-white text-sm font-medium hover:border-blue-300 hover:text-blue-700"><Upload className="w-4 h-4" /> Choose a photo</button><p className="mt-4 text-[11px] text-slate-400">JPG, PNG or WebP · Up to 20 MB</p></div>}
          </div>
          <label htmlFor="shelf-choice" className="block mt-5 text-sm font-medium">Shelf to check</label>
          <select id="shelf-choice" value={bayId} onChange={e => setBayId(e.target.value)} disabled={uploading || !store} required className="mt-2 w-full bg-white border border-slate-200 rounded-lg py-2.5 px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="" disabled>{store ? 'Choose a shelf' : 'Loading shelves…'}</option>
            {bays.map(bay => <option key={bay.id} value={bay.id}>{bay.name}</option>)}
          </select>
          <p className="text-[11px] text-slate-400 mt-2">Choose the matching reference shelf. This demo uses six fixed catalogues.</p>
          {selectedBay?.photo && <div className="mt-3 flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3"><img src={`/photos/${selectedBay.photo}`} alt={`Reference photo for ${selectedBay.code}`} className="w-14 h-16 object-cover rounded border border-slate-200" /><div className="min-w-0"><p className="text-xs font-semibold text-slate-700">{selectedBay.code} · Reference shelf</p><p className="text-[11px] text-slate-500 leading-5 mt-0.5">Compare a photo of this shelf. Other photos can be read, but these demo records may not describe their placement.</p></div></div>}
          {(error || loadError) && <div role="alert" className="mt-4 p-3 rounded-lg border border-red-200 bg-red-50 text-xs leading-5 text-red-800">{error || loadError}</div>}
          {liveAvailable === false && <p className="mt-4 rounded-lg bg-amber-50 border border-amber-100 p-3 text-xs leading-5 text-amber-800">
            {auth.status === 'signed-in'
              ? 'Live analysis is not ready on this server. Your photo can still be uploaded and kept without inventing results.'
              : auth.status === 'connection-error'
                ? 'Company sign-in could not be checked. Retry the status check above; uploads remain available without starting inference.'
              : 'Sign in with your company account to enable live photo analysis. You can still upload a photo or explore a saved sample.'}
          </p>}
          <button type="submit" disabled={!file || !bayId || uploading || !!loadError} className="mt-5 w-full inline-flex items-center justify-center gap-2 py-3 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed transition-colors">{uploading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Preparing your photo…</> : <>Analyze shelf <ArrowRight className="w-4 h-4" /></>}</button>
          <p className="mt-3 text-center text-[11px] leading-5 text-slate-400">Your photo is uploaded to this app for recognition.<br />No inventory records are changed automatically.</p>
        </form>
      </div>
    </main>
    <footer className="border-t border-slate-200/80 px-5 py-5 text-xs text-slate-400"><div className="max-w-6xl mx-auto flex flex-wrap gap-2 justify-between"><span>Shelf Check · Straive Innovation</span><span>Demo planograms and inventory records are simulated.</span></div></footer>
  </div>;
};
