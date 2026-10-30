import React from 'react';
import { RefreshCw } from 'lucide-react';
import { foundryInitials, type FoundryAuthState } from '../foundryAuth';

interface FoundryStatusProps {
  auth: FoundryAuthState;
  onSignIn: () => void;
  onRefresh: () => void;
}

/** Compact initials avatar; the email appears only on hover/focus. */
export const FoundryStatus: React.FC<FoundryStatusProps> = ({ auth, onSignIn, onRefresh }) => {
  if (auth.status === 'signed-in') {
    return <div className="group relative shrink-0" aria-label="LLM Foundry account">
      <span
        tabIndex={0}
        role="img"
        aria-label={`Signed in as ${auth.email}`}
        title={auth.email}
        className="relative inline-flex h-9 w-9 cursor-default items-center justify-center rounded-full bg-blue-700 text-xs font-bold tracking-wide text-white ring-2 ring-blue-100 outline-offset-2 focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        {foundryInitials(auth.email)}
        <span aria-hidden="true" className="absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
      </span>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute right-0 top-full z-50 mt-2 max-w-72 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        {auth.email}
      </span>
    </div>;
  }

  if (auth.status === 'checking') {
    return <div role="status" aria-live="polite" className="flex items-center gap-2 text-xs font-medium text-slate-500">
      <RefreshCw className="h-4 w-4 animate-spin" /> Checking sign-in…
    </div>;
  }

  return <div className="flex shrink-0 items-center gap-2" aria-label="Company sign-in">
    <button type="button" onClick={onSignIn} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:border-blue-400">
      Sign in
    </button>
    {auth.status === 'connection-error' && <button type="button" onClick={onRefresh} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:text-blue-700" title={auth.message}>
      Retry
    </button>}
  </div>;
};
