import React from 'react';
import { ArrowLeft, Info, Layers, ScanLine } from 'lucide-react';
import type { Bay } from '../types';
import type { FoundryAuthState } from '../foundryAuth';
import { FoundryStatus } from './FoundryStatus';

interface HeaderProps {
  bays: Bay[];
  selectedBayId: string;
  onSelectBay: (id: string) => void;
  onOpenInfo: () => void;
  onHome: () => void;
  isUpload: boolean;
  isScanning: boolean;
  resultMode: 'replay' | 'live';
  auth: FoundryAuthState;
  onSignIn: () => void;
  onRefreshAuth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  bays, selectedBayId, onSelectBay, onOpenInfo, onHome,
  isUpload, isScanning, resultMode, auth, onSignIn, onRefreshAuth,
}) => <header className="sticky top-0 z-30 border-b border-slate-200 bg-white shadow-xs">
  <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-3 px-4 py-3 sm:px-6 md:min-h-[76px] md:flex-row md:items-center md:justify-between md:gap-4 lg:px-8">
    <div className="flex shrink-0 items-center gap-3">
      <button type="button" onClick={onHome} aria-label="Go to homepage" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-600 text-white">
        <Layers className="h-5 w-5" />
      </button>
      <div className="whitespace-nowrap">
        <span className="text-lg font-bold tracking-tight text-slate-900">Shelf Check</span>
        <p className="text-xs text-slate-500">Shelf analysis · Simulated store records</p>
      </div>
    </div>

    <div className="flex w-full min-w-0 flex-1 items-center gap-3 md:w-auto md:justify-end">
      <nav aria-label="Shelf navigation" className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap py-1 md:justify-end">
        <div className="flex min-w-[180px] max-w-[340px] flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
          <span className="pl-2 text-xs font-medium text-slate-500">Shelf:</span>
          <select
            aria-label="Shelf bay"
            value={selectedBayId}
            disabled={isScanning}
            onChange={event => onSelectBay(event.target.value)}
            className="w-full min-w-0 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:text-slate-600"
          >
            {bays.filter(bay => bay.scannable).map(bay =>
              <option key={bay.id} value={bay.id}>{bay.name}</option>
            )}
          </select>
        </div>
        <a href="/model-comparison" className="shrink-0 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100">
          Model Comparison
        </a>
        <span className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-2 text-xs font-medium text-slate-600 xl:inline-flex">
          <ScanLine className="h-3.5 w-3.5" />
          {isUpload ? 'Your shelf photo' : resultMode === 'live' ? 'New sample analysis' : 'Saved sample'}
        </span>
        <button type="button" onClick={onOpenInfo} aria-label="About recognition and accuracy" className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100">
          <Info className="h-4 w-4" />
        </button>
        <button type="button" onClick={onHome} className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Upload a photo</span>
        </button>
      </nav>
      <FoundryStatus auth={auth} onSignIn={onSignIn} onRefresh={onRefreshAuth} />
    </div>
  </div>
</header>;
