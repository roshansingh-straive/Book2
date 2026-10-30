import React, { useCallback, useEffect, useRef, useState } from 'react';
import { HomePage } from './components/HomePage';
import { AnalysisPage } from './components/AnalysisPage';
import { ModelComparisonPage } from './components/ModelComparisonPage';
import { FoundryLoginGate } from './components/FoundryLoginGate';
import type { ScanHealth, StoreData } from './types';
import { checkFoundrySession, foundryLoginUrl, type FoundryAuthState } from './foundryAuth';

export const App: React.FC = () => {
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
  const [store, setStore] = useState<StoreData | null>(null);
  const [health, setHealth] = useState<ScanHealth | null>(null);
  const [healthChecked, setHealthChecked] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [auth, setAuth] = useState<FoundryAuthState>({ status: 'checking' });
  const [continueWithoutSignIn, setContinueWithoutSignIn] = useState(false);
  const authCheckId = useRef(0);
  const refreshAuth = useCallback(async () => {
    const checkId = ++authCheckId.current;
    setAuth({ status: 'checking' });
    const result = await checkFoundrySession();
    if (checkId === authCheckId.current) setAuth(result);
  }, []);
  const authenticationFailure = useCallback(() => {
    authCheckId.current += 1;
    setAuth({ status: 'signed-out', message: 'Your company inference session has expired. Sign in again to continue.' });
  }, []);
  const signIn = useCallback(() => {
    window.location.assign(foundryLoginUrl(window.location.href));
  }, []);
  const navigate = (path: string) => {
    window.history.pushState(null, '', path);
    setLocation(window.location.pathname + window.location.search);
    window.scrollTo(0, 0);
  };
  useEffect(() => {
    const onPopState = () => setLocation(window.location.pathname + window.location.search);
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);
  // Check once on first load. Do not recheck when switching routes or browser tabs.
  useEffect(() => { void refreshAuth(); }, [refreshAuth]);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/data/store.json', { signal: controller.signal })
      .then(res => { if (!res.ok) throw new Error('Shelf records could not be loaded. Please reload to retry.'); return res.json(); })
      .then(setStore)
      .catch((err: Error) => { if (err.name !== 'AbortError') setLoadError(err.message); });
    fetch('/api/health', { signal: controller.signal })
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data?.live_available_by_difficulty) setHealth(data); })
      .catch(() => undefined)
      .finally(() => { if (!controller.signal.aborted) setHealthChecked(true); });
    return () => controller.abort();
  }, []);
  const url = new URL(location, window.location.origin);
  const bayId = url.searchParams.get('bay') || 'bay_f3';
  if (!continueWithoutSignIn && auth.status !== 'signed-in') return <FoundryLoginGate
    auth={auth} onSignIn={signIn} onRetry={() => void refreshAuth()}
    onContinue={() => setContinueWithoutSignIn(true)}
  />;
  if (url.pathname === '/model-comparison') return <ModelComparisonPage
    onHome={() => navigate('/')} auth={auth} onSignIn={signIn} onRefreshAuth={() => void refreshAuth()}
  />;
  if (url.pathname === '/analysis') return <AnalysisPage
    key={`${bayId}:${url.searchParams.get('upload') ?? 'sample'}`}
    bayId={bayId} uploadId={url.searchParams.get('upload')} store={store} health={health} healthChecked={healthChecked}
    auth={auth} onSignIn={signIn} onRefreshAuth={() => void refreshAuth()}
    onAuthenticationFailure={authenticationFailure}
    storeError={loadError} onHome={() => navigate('/') }
    onSelectBay={id => navigate(`/analysis?bay=${encodeURIComponent(id)}${url.searchParams.get('upload') ? `&upload=${encodeURIComponent(url.searchParams.get('upload')!)}` : ''}`)}
  />;
  return <><div className="fixed right-5 bottom-5 z-50"><button onClick={() => navigate('/model-comparison')} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:bg-blue-800">Model Comparison</button></div><HomePage store={store} loadError={loadError} liveAvailable={healthChecked && auth.status !== 'checking' ? !!health?.upload_analysis_available && auth.status === 'signed-in' : null}
    auth={auth} onSignIn={signIn} onRefreshAuth={() => void refreshAuth()}
    onAnalyze={(photo, id) => navigate(`/analysis?bay=${encodeURIComponent(id)}&upload=${photo.upload_id}`)}
    onSample={id => navigate(`/analysis?bay=${encodeURIComponent(id)}`)} /></>;
};
