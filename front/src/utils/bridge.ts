/**
 * Message bridge to parent app (Porteghal WebView/iframe).
 */
export function sendToParent(type: string, payload?: Record<string, any>): void {
  const message = JSON.stringify({ type, ...payload });

  // React Native WebView bridge
  if (typeof window !== 'undefined' && (window as any).ReactNativeWebView?.postMessage) {
    (window as any).ReactNativeWebView.postMessage(message);
  }
  // Standard iframe parent communication
  if (typeof window !== 'undefined' && window.parent && window.parent !== window) {
    window.parent.postMessage(message, '*');
  }
  // Standalone fallback
  else {
    console.log('[Bridge]', message);
  }
}

/**
 * Parse URL query parameters (supports ?key=value&key2=value2).
 */
export function getQueryParams(): Record<string, string> {
  const params: Record<string, string> = {};
  if (typeof window === 'undefined') return params;
  const search = window.location.search.substring(1);
  if (!search) return params;
  search.split('&').forEach((part) => {
    const [key, val] = part.split('=');
    if (key && val) params[decodeURIComponent(key)] = decodeURIComponent(val);
  });
  return params;
}

/**
 * Get dynamic WS base URL from the current page hostname.
 * This makes the game work from any deployment (not just localhost).
 */
export function getWsBaseUrl(port: number = 8000): string {
  const hostname = window.location.hostname || 'localhost';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${hostname}:${port}`;
}

/**
 * Get dynamic HTTP base URL from the current page hostname.
 */
export function getHttpBaseUrl(port: number = 8000): string {
  const hostname = window.location.hostname || 'localhost';
  const protocol = window.location.protocol || 'http:';
  return `${protocol}//${hostname}:${port}`;
}
