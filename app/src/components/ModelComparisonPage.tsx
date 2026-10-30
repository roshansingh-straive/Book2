import React, { useEffect, useState } from 'react';
import { ArrowLeft, BarChart3, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { FoundryStatus } from './FoundryStatus';
import type { FoundryAuthState } from '../foundryAuth';

type Reading = { title: string; author?: string | null; uncertain?: boolean };
type Call = {
  image: string; model: string; tile_id: string; status: string; error: string | null;
  readings: Reading[]; duration_seconds?: number; estimated_cost_usd?: number | null;
};
type Summary = {
  image: string; model: string; planned_tiles: number; attempted_calls: number;
  successful_calls: number; failed_calls: number; unique_titles: number;
  reference_title_overlap: number; reference_titles: number;
  total_duration_seconds: number; estimated_cost_usd: number | null;
  quality_status: string;
};
type Run = {
  name: string;
  metadata: { created_at: string; max_tiles?: number; photos?: string[] };
  summary: Summary[];
  calls: Call[];
};
type Results = { runs: Run[] };
type Sample = { row: Summary; run: Run; calls: Call[] };
const MODELS = [
  { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash', rate: '$0.50 / $3.00', detail: 'LOW thinking' },
  { id: 'gpt-5-mini', label: 'GPT-5 Mini', rate: '$0.25 / $2.00', detail: 'Low reasoning' },
  { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro', rate: '$2.00 / $12.00', detail: 'HIGH thinking (matches main demo)' },
];
const PHOTOS = [
  { id: 'a.jpg', category: 'Easy', planned: 1 },
  { id: 'b.jpg', category: 'Easy', planned: 1 },
  { id: 'c.png', category: 'Medium', planned: 2 },
  { id: 'd.jpg', category: 'Medium', planned: 20 },
  { id: 'e.jpg', category: 'Hard', planned: 20 },
  { id: 'f.jpg', category: 'Hard', planned: 20 },
];

function findSample(runs: Run[], image: string, model: string): Sample | null {
  let partial: Sample | null = null;
  for (const run of runs) {
    const row = run.summary.find(item => item.image === image && item.model === model);
    if (!row) continue;
    const value = { row, run, calls: run.calls.filter(c => c.image === image && c.model === model) };
    if (row.quality_status === 'complete_unverified') return value;
    if (!partial) partial = value;
  }
  return partial;
}
function stateText(sample: Sample | null, planned: number) {
  if (!sample) return 'Not yet tested';
  if (sample.row.quality_status === 'complete_unverified') return 'Complete';
  const { attempted_calls, failed_calls } = sample.row;
  if (failed_calls) return attempted_calls < planned ? 'Partial (errors)' : 'Finished with errors';
  return attempted_calls < planned ? 'Partial' : 'Incomplete';
}
function dollars(value: number | null | undefined) {
  return typeof value === 'number' ? '$' + value.toFixed(5) : 'Unavailable';
}

export const ModelComparisonPage: React.FC<{ onHome: () => void; auth: FoundryAuthState; onSignIn: () => void; onRefreshAuth: () => void }> = ({ onHome, auth, onSignIn, onRefreshAuth }) => {
  const [results, setResults] = useState<Results | null>(null);
  const [selected, setSelected] = useState('f.jpg');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [updated, setUpdated] = useState('');
  const load = () => {
    setLoading(true);
    fetch('/api/model-comparison', { cache: 'no-store' })
      .then(async response => {
        if (!response.ok) throw new Error('The comparison-results API returned HTTP ' + response.status);
        return response.json() as Promise<Results>;
      })
      .then(value => { setResults(value); setError(''); setUpdated(new Date().toLocaleTimeString()); })
      .catch(e => setError(e instanceof Error ? e.message : 'Unable to load comparison results'))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  const runs = results?.runs ?? [];
  const image = PHOTOS.find(photo => photo.id === selected) ?? PHOTOS[5];
  const samples = MODELS.map(model => ({ model, sample: findSample(runs, selected, model.id) }));
  return <div className="min-h-dvh bg-slate-50 text-slate-900">
    <header className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-5 py-5 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex gap-3 items-center"><BarChart3 className="text-blue-600 w-7 h-7" />
          <div><h1 className="text-xl font-bold">Model Comparison</h1><p className="text-xs text-slate-500">Book Shelf Recognition | Six reference photos | Real API responses</p></div>
        </div>
        <div className="flex gap-2 items-center">
          <button onClick={load} disabled={loading} className="border border-slate-300 bg-white hover:bg-slate-50 rounded-lg px-3 py-2 text-sm flex gap-2 items-center disabled:opacity-50"><RefreshCw className={'w-4 h-4 ' + (loading ? 'animate-spin' : '')}/>Refresh results</button>
          <button onClick={onHome} className="border border-slate-300 bg-white hover:bg-slate-50 rounded-lg px-3 py-2 text-sm flex gap-2 items-center"><ArrowLeft className="w-4 h-4"/>Back to demo</button>
          <FoundryStatus auth={auth} onSignIn={onSignIn} onRefresh={onRefreshAuth} />
        </div>
      </div>
    </header>
    <main className="max-w-7xl mx-auto p-5 space-y-6">
      <p className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-900">
        Results are from real requests, not simulated scores. Matching the saved catalogue is <strong>reference overlap, not verified accuracy</strong>. An image is complete only after every planned crop succeeds. Different model reasoning settings affect cost and latency.
      </p>
      {error && <p role="alert" className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3">{error}</p>}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div><h2 className="text-lg font-semibold">All six demo images</h2><p className="text-xs text-slate-500">Choose an image to compare three vision models. Missing rows mean requests have not completed.</p></div>
        <span className="text-xs text-slate-500">{updated ? 'Last refreshed at ' + updated : 'Loading saved runs...'}</span>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-600"><tr><th className="p-3 text-left">Photo</th>{MODELS.map(model=><th key={model.id} className="p-3 text-left">{model.label}</th>)}</tr></thead>
          <tbody>{PHOTOS.map(photo=><tr key={photo.id} className={'border-t border-slate-100 ' + (photo.id === selected ? 'bg-blue-50/60' : '')}>
            <td className="p-3 whitespace-nowrap"><button onClick={()=>setSelected(photo.id)} className="text-blue-700 font-semibold underline underline-offset-2">{photo.id}</button><span className="text-xs text-slate-400 block">{photo.category} · {photo.planned} crop{photo.planned>1?'s':''}</span></td>
            {MODELS.map(model=>{
              const sample=findSample(runs,photo.id,model.id);
              return <td key={model.id} className="p-3 align-middle">
                <button onClick={()=>setSelected(photo.id)} className="text-left hover:underline">
                  <span className={'block text-xs font-semibold ' + (sample?.row.quality_status==='complete_unverified'?'text-emerald-700':sample?'text-amber-700':'text-slate-400')}>{stateText(sample, photo.planned)}</span>
                  <span className="text-xs text-slate-600">{sample ? sample.row.successful_calls + '/' + photo.planned + ' successful · ' + sample.row.reference_title_overlap + ' ref. matches' : '—'}</span>
                </button>
              </td>
            })}
          </tr>)}</tbody>
        </table>
      </div>
      <section>
        <h2 className="text-lg font-semibold mb-3">Results for {selected} <span className="text-sm font-normal text-slate-500">({image.category} · {image.planned} image crops per model)</span></h2>
        <div className="grid md:grid-cols-3 gap-4">
          {samples.map(({model,sample})=><article key={model.id} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <h3 className="font-bold">{model.label}</h3><p className="text-xs text-slate-500 mt-1">Input / output: {model.rate} per million tokens</p>
            <p className="text-xs text-slate-500">{model.detail}</p>
            <p className={'mt-4 text-sm font-medium ' + (sample?.row.quality_status==='complete_unverified'?'text-emerald-700':sample?'text-amber-700':'text-slate-400')}>{sample?.row.quality_status==='complete_unverified'?<CheckCircle2 className="inline w-4 h-4 mr-1"/>:sample?<AlertTriangle className="inline w-4 h-4 mr-1"/>:null}{stateText(sample,image.planned)}</p>
            <div className="mt-2 text-3xl font-semibold text-slate-900">{sample?.row.unique_titles ?? '—'} <span className="text-sm font-normal text-slate-500">unique titles</span></div>
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-slate-500">Reference matches</dt><dd className="font-semibold text-right">{sample?.row.reference_title_overlap ?? '—'} / {sample?.row.reference_titles ?? '—'}</dd>
              <dt className="text-slate-500">Successful crops</dt><dd className="font-semibold text-right">{sample?.row.successful_calls ?? 0} / {image.planned}</dd>
              <dt className="text-slate-500">Elapsed time</dt><dd className="font-semibold text-right">{sample ? sample.row.total_duration_seconds.toFixed(1)+'s' : '—'}</dd>
              <dt className="text-slate-500">{sample?.row.quality_status==='complete_unverified'?'Estimated cost':'Cost for all crops'}</dt><dd className="font-semibold text-right">{dollars(sample?.row.estimated_cost_usd)}</dd>
            </dl>
            {sample && <p className="mt-3 text-[11px] text-slate-400">Source: {sample.run.name}</p>}
          </article>)}
        </div>
      </section>
      <div className="grid lg:grid-cols-2 gap-5">
        <section className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="font-semibold mb-3">Reference bookshelf photo</h2>
          <img src={'/photos/'+selected} alt={'Bookshelf '+selected} className="rounded-lg w-full max-h-[620px] object-contain bg-slate-100" />
        </section>
        <section className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="font-semibold mb-3">Identified book titles</h2>
          <div className="max-h-[620px] overflow-y-auto space-y-3">
            {samples.map(({model,sample})=><details key={model.id} open={model.id === 'gemini-3-flash-preview'} className="rounded-lg border border-slate-200 p-3">
              <summary className="cursor-pointer text-sm font-semibold">{model.label} · {sample?.row.unique_titles ?? 0} titles</summary>
              {sample ? <div className="mt-3 space-y-3">{sample.calls.map((call,i)=><div key={i} className="border-t border-slate-100 pt-2">
                <div className="flex items-center justify-between text-xs"><span className="font-medium text-slate-600">{call.tile_id}</span><span className={call.status==='ok'?'text-emerald-700':'text-red-700'}>{call.status==='ok'?'Success':call.error||'Error'}</span></div>
                <p className="text-xs text-slate-600 mt-1">{call.readings.length ? call.readings.map(item=>item.title).join(' · ') : 'No recognized titles in this crop'}</p>
              </div>)}</div> : <p className="text-sm text-slate-500 pt-3">No inference results saved for this model and photo yet.</p>}
            </details>)}
          </div>
        </section>
      </div>
      <p className="text-xs text-slate-500">Cost estimates use provider-reported token counts and your supplied rates. Failed or unfinished model runs do not receive fabricated complete-scan costs. The main application continues to use Gemini 3.1 Pro Preview.</p>
    </main>
  </div>;
};
