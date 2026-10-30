import React from 'react';
import { Layers, LockKeyhole, RefreshCw, ArrowRight, Image as ImageIcon } from 'lucide-react';
import type { FoundryAuthState } from '../foundryAuth';

interface FoundryLoginGateProps {
  auth: FoundryAuthState;
  onSignIn: () => void;
  onRetry: () => void;
  onContinue: () => void;
}

/** First-load sign-in prompt: does not run inference or store a token. */
export const FoundryLoginGate: React.FC<FoundryLoginGateProps> = ({ auth, onSignIn, onRetry, onContinue }) => {
  const checking = auth.status === 'checking';
  const connectionError = auth.status === 'connection-error';
  return <main className="min-h-dvh bg-slate-50 px-4 py-10 flex items-center justify-center text-slate-900">
    <section aria-labelledby="foundry-login-title" className="w-full max-w-md overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
      <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-5">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-600 text-white"><Layers className="h-5 w-5" /></span>
        <div><p className="text-lg font-bold">Shelf Check</p><p className="text-xs text-slate-500">Straive Innovation · Bookshelf demo</p></div>
      </div>
      <div className="px-6 py-7">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
          {checking ? <RefreshCw className="h-6 w-6 animate-spin" /> : <LockKeyhole className="h-6 w-6" />}
        </div>
        <h1 id="foundry-login-title" className="text-2xl font-bold tracking-tight">
          {checking ? 'Checking LLM Foundry sign-in' : 'Sign in to LLM Foundry'}
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          {checking
            ? 'Checking your existing Straive session before opening the application.'
            : 'Sign in with your Straive account to enable live bookshelf recognition. This is checked when you first open the demo, not every time you switch views.'}
        </p>
        {connectionError && <p role="alert" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {auth.message} You can retry or continue to saved sample results without live AI recognition.
        </p>}
        {!checking && <div className="mt-6 space-y-3">
          <button type="button" onClick={onSignIn} className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700">
            Sign in with Straive <ArrowRight className="h-4 w-4" />
          </button>
          {connectionError && <button type="button" onClick={onRetry} className="w-full rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">Retry session check</button>}
          <button type="button" onClick={onContinue} className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
            <ImageIcon className="h-4 w-4" /> Continue with saved samples
          </button>
        </div>}
        <p className="mt-5 text-xs leading-5 text-slate-500">Saved samples and model comparison results are already recorded and make no new LLM calls. Live analysis requires a valid Foundry session.</p>
      </div>
    </section>
  </main>;
};
