/**
 * Resolves the player_id dynamically from external application entry points
 * supporting URL query parameters, with safe local storage fallbacks.
 *
 * Returns { playerId, playerName, playerAvatar } from URL query params.
 */
export const resolvePlayerId = (): string => {
  try {
    // 1. Try to parse external parameters from the browser URL (Standard for iframe integrations)
    const urlParams = new URLSearchParams(window.location.search);
    const externalId = 
      urlParams.get('player_id') || 
      urlParams.get('playerId') || 
      urlParams.get('username') || 
      urlParams.get('name');

    if (externalId && externalId.trim() !== '') {
      console.log('[User Resolver] Successfully resolved external player ID:', externalId);
      return externalId.trim();
    }
  } catch (err) {
    console.error('[User Resolver Error] Failed to read URL query parameters:', err);
  }

  // 2. Fallback to Local Storage inside a try-catch for Incognito/Private Browsing safety
  const storageKey = 'uno_cached_player_id';
  try {
    const cachedId = localStorage.getItem(storageKey);
    if (cachedId && cachedId.trim() !== '') {
      return cachedId.trim();
    }
  } catch (err) {
    console.warn('[User Resolver Warning] LocalStorage blocked (likely Incognito mode):', err);
  }

  // 3. Absolute fallback: Generate a unique temporary ID if no external data is found
  const fallbackId = `player_${Math.floor(1000 + Math.random() * 9000)}`;
  
  try {
    localStorage.setItem(storageKey, fallbackId);
  } catch (err) {
    // Silently catch write errors in restricted storage environments
  }

  console.log('[User Resolver] Generated local fallback player ID:', fallbackId);
  return fallbackId;
};

/**
 * Returns player display info extracted from URL query params.
 */
export interface PlayerInfo {
  playerId: string;
  playerName: string;
  playerAvatar: string;
}

export const resolvePlayerInfo = (): PlayerInfo => {
  const playerId = resolvePlayerId();
  let playerName = '';
  let playerAvatar = '';

  try {
    const urlParams = new URLSearchParams(window.location.search);
    playerName = urlParams.get('playerName') || urlParams.get('player_name') || '';
    playerAvatar = urlParams.get('playerAvatar') || urlParams.get('player_avatar') || '';
  } catch (err) {
    console.error('[User Resolver] Failed to read name/avatar from URL:', err);
  }

  return { playerId, playerName, playerAvatar };
};