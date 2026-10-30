export const FOUNDRY_AUTH_ORIGIN = 'https://llmfoundry.straivedemo.com';

export type FoundryAuthState =
  | { status: 'checking' }
  | { status: 'signed-out'; message: string }
  | { status: 'connection-error'; message: string }
  | { status: 'signed-in'; email: string; token: string };

export async function checkFoundrySession(
  request: typeof fetch = fetch,
): Promise<FoundryAuthState> {
  try {
    const response = await request(`${FOUNDRY_AUTH_ORIGIN}/token`, {
      credentials: 'include',
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    });
    if (response.status === 401 || response.status === 403) {
      return { status: 'signed-out', message: 'Sign in to enable photo analysis.' };
    }
    if (!response.ok) {
      return { status: 'connection-error', message: 'Company sign-in could not be checked.' };
    }

    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      return { status: 'connection-error', message: 'Company sign-in returned an invalid response.' };
    }
    const session = data as { email?: unknown; token?: unknown };
    if (typeof session.email !== 'string' || !session.email.trim()
      || typeof session.token !== 'string' || !session.token.trim()) {
      return { status: 'signed-out', message: 'A usable company inference session is required.' };
    }
    return { status: 'signed-in', email: session.email.trim(), token: session.token.trim() };
  } catch {
    return { status: 'connection-error', message: 'Could not connect to company sign-in. Check your network and try again.' };
  }
}

/** Two-letter profile initials derived from a signed-in Foundry email. */
export function foundryInitials(email: string): string {
  const local = (email.split('@')[0] || '').trim();
  const parts = local.split(/[._+\-\s]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (local.slice(0, 2) || 'US').toUpperCase();
}

export function foundryLoginUrl(returnUrl: string): string {
  const login = new URL('/login', FOUNDRY_AUTH_ORIGIN);
  login.searchParams.set('next', returnUrl);
  return login.toString();
}
