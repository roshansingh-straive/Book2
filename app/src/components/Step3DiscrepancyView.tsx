import React, { useState } from 'react';
import type { ActionTask, ScanMetrics } from '../types';
import { Check, CheckCircle2, ClipboardCheck, Eye } from 'lucide-react';

interface Props {
  tasks: ActionTask[];
  metrics: ScanMetrics;
  readingMode?: 'single_pass' | 'verified';
  onResolveTask: (taskId: string) => void;
  hoveredItemId?: string | null;
  onHoverItem?: (id: string | null) => void;
}
export const Step3DiscrepancyView: React.FC<Props> = ({ tasks, metrics, readingMode, onResolveTask, hoveredItemId, onHoverItem }) => {
  const [tab, setTab] = useState<'all' | 'placement' | 'reading' | 'unseen' | 'reviewed'>('all');
  const open = tasks.filter(task => !task.resolved);
  const reviewed = tasks.filter(task => task.resolved);
  const displayed = tasks.filter(task => tab === 'reviewed' ? task.resolved : !task.resolved && (
    tab === 'all' || tab === 'placement' && task.type === 'misplaced_item' ||
    tab === 'reading' && task.type === 'recognition_review' || tab === 'unseen' && task.type === 'missing_item'));
  const tabs = [
    ['all', 'All Checks', open.length],
    ['reading', 'Title checks', open.filter(task => task.type === 'recognition_review').length],
    ['placement', 'Shelf assignment', open.filter(task => task.type === 'misplaced_item').length],
    ['unseen', 'Not confirmed', open.filter(task => task.type === 'missing_item').length],
    ['reviewed', 'Reviewed', reviewed.length],
  ] as const;
  return <section className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden flex flex-col h-full">
    <div className="p-4 border-b border-slate-100 bg-slate-50/70">
      <div className="flex items-center justify-between gap-2 mb-2"><div className="flex items-center gap-2"><span className="grid place-items-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">3</span><h2 className="text-sm font-bold text-slate-900">Review &amp; next steps</h2></div><span className="text-[11px] px-2 py-1 rounded-full bg-slate-100 text-slate-600 font-medium whitespace-nowrap">{open.length} open checks</span></div>
      <p className="text-xs text-slate-500 leading-5">A readable title can have an uncertain location. Review checks explain each result before you act.</p>
      <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-slate-200/60">
        <div className="rounded-lg border border-slate-200 bg-white p-2.5"><div className="text-[10px] font-medium text-slate-500">{readingMode === 'single_pass' ? 'Catalogue coverage' : 'Shelf title coverage'}</div><div className="text-lg font-bold text-slate-900 tabular-nums mt-1">{metrics.planogram_compliance_pct}%</div></div>
        <div className="rounded-lg border border-slate-200 bg-white p-2.5"><div className="text-[10px] font-medium text-slate-500">Titles matched here</div><div className="text-lg font-bold text-emerald-700 tabular-nums mt-1">{metrics.matched_count}</div></div>
        <div className="rounded-lg border border-slate-200 bg-white p-2.5"><div className="text-[10px] font-medium text-slate-500">Presence unconfirmed</div><div className="text-lg font-bold text-slate-700 tabular-nums mt-1">{metrics.missing_count}</div></div>
      </div>
      {readingMode === 'single_pass' && <p className="text-[11px] text-blue-800 leading-5 mt-2">Single reading · Catalogue matches have not been independently verified.</p>}
      {!!metrics.provisional_count && <p className="text-[11px] text-blue-800 leading-5 mt-2">{metrics.provisional_count} additional catalogue matches are provisional until an independent reading confirms them.</p>}
      <p className="text-[10px] text-slate-400 leading-4 mt-2">Coverage compares identified titles with this demo shelf. It is not a recognition accuracy score or a stock count.</p>
    </div>
    <div className="p-3 border-b border-slate-100 flex flex-wrap gap-1.5" role="group" aria-label="Filter review checks">{tabs.map(([id, label, count]) => <button key={id} onClick={() => setTab(id)} aria-pressed={tab === id} className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium ${tab === id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{label}{id !== 'all' && ` (${count})`}</button>)}</div>
    <div className="flex-1 overflow-y-auto p-3 space-y-2.5 max-h-[580px]">
      {!displayed.length ? <div className="py-10 px-5 text-center"><CheckCircle2 className="w-8 h-8 mx-auto text-emerald-600 mb-3" /><p className="text-sm font-semibold text-slate-800">{tab === 'reviewed' ? 'No reviewed checks yet' : 'No open checks in this view'}</p><p className="text-xs text-slate-500 leading-5 mt-2">{tab === 'reviewed' ? 'Checks you acknowledge appear here.' : 'Check the recognized titles and the original photo before making inventory decisions.'}</p></div>
        : displayed.map(task => {
          const location = task.type === 'recognition_review' && task.badge.includes('Location');
          const amber = task.type === 'misplaced_item' || task.type === 'record_error';
          return <article key={task.id} onMouseEnter={() => onHoverItem?.(task.shelf_item_id ?? null)} onMouseLeave={() => onHoverItem?.(null)} className={`rounded-lg border p-3 transition-colors ${task.resolved ? 'border-emerald-200 bg-emerald-50/40' : amber ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200 bg-white'} ${hoveredItemId === task.shelf_item_id ? 'ring-2 ring-blue-200' : ''}`}>
            <div className="flex items-center gap-2 mb-2"><span className={`text-[10px] font-semibold px-2 py-1 rounded-md ${task.resolved ? 'bg-emerald-100 text-emerald-800' : location ? 'bg-blue-50 text-blue-800' : amber ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-600'}`}>{task.resolved ? 'Reviewed' : task.badge}</span></div>
            <h3 className="text-xs font-semibold text-slate-900 leading-5">{task.title}</h3><p className="text-[11px] text-slate-500">{task.author || 'Author not confirmed'}</p>
            <p className="text-[11px] text-slate-600 leading-5 my-2.5">{task.headline}</p>
            {task.resolved ? <div className="text-[11px] text-emerald-700 inline-flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Reviewed in this demo session</div>
              : <button onClick={() => onResolveTask(task.id)} className="inline-flex items-center justify-center gap-1.5 w-full rounded-md border border-slate-200 bg-white py-2 px-2.5 text-[11px] font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-700"><Eye className="w-3.5 h-3.5 shrink-0" />{task.suggested_action}</button>}
          </article>;
        })}
    </div>
    <div className="p-3 border-t border-slate-200 bg-slate-50 flex gap-2 items-start text-[10px] text-slate-500 leading-4"><ClipboardCheck className="w-3.5 h-3.5 shrink-0 mt-0.5" />Review only · Acknowledging a check does not change inventory, confirm an uncertain reading or increase coverage.</div>
  </section>;
};
