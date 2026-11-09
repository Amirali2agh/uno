import { useEffect, useRef, useCallback, useState } from 'react';
import type { GameState, RoomMessage, GameAction, GameOverPayload } from '../types/uno';

// --- Type definition for our lightweight PubSub event map ---
type UnoEventMap = {
  state_update: (state: GameState) => void;
  player_status: (payload: { player_id: string; status: 'connected' | 'disconnected' }) => void;
  error: (message: string) => void;
  match_found: (gameId: string) => void;
  game_over: (payload: GameOverPayload) => void;
};

export type ConnectionStatus = 'idle' | 'connecting' | 'reconnecting' | 'open' | 'closed';

// Reconnection policy for the game room socket.
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 8000;

interface RoomConnectionConfig {
  gameId: string;
  playerId: string;
  playerName?: string;
  playerAvatar?: string;
}

export const useUnoSocket = () => {
  // --- Refs for managing WebSocket connection lifecycles ---
  const queueWsRef = useRef<WebSocket | null>(null);
  const roomWsRef = useRef<WebSocket | null>(null);

  // --- PubSub Listeners registry stored in a ref using flexible internal Sets to bypass React render ---
  const listenersRef = useRef<{ [K in keyof UnoEventMap]?: Set<any> }>({});

  // --- Cache the latest GameState in a ref to prevent Stale Closures inside WS callbacks ---
  const latestGameStateRef = useRef<GameState | null>(null);

  // --- Reconnection bookkeeping for the room socket ---
  const roomConfigRef = useRef<RoomConnectionConfig | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const [roomStatus, setRoomStatus] = useState<ConnectionStatus>('idle');

  // --- Origin-relative WS URL resolver ---
  // Sockets always target the origin the page was served from: the Vite dev server
  // proxies /ws to the backend (see vite.config.ts) and in production the reverse
  // proxy does the same. Using location.host (not hostname) keeps the dev port.
  const getWsUrl = useCallback((path: string): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:5173';
    return `${protocol}//${host}${path}`;
  }, []);

  // --- PubSub Subscribe mechanism ---
  const subscribe = useCallback(<K extends keyof UnoEventMap>(event: K, callback: UnoEventMap[K]) => {
    if (!listenersRef.current[event]) {
      listenersRef.current[event] = new Set<any>(); // Explicitly typed set to prevent empty inference
    }
    listenersRef.current[event]?.add(callback);

    // Return an unsubscribe function for React useEffect cleanups
    return () => {
      listenersRef.current[event]?.delete(callback);
    };
  }, []);

  // --- PubSub Emit helper with explicit any typing for the nested loop ---
  const emit = useCallback(<K extends keyof UnoEventMap>(event: K, ...args: Parameters<UnoEventMap[K]>) => {
    const targets = listenersRef.current[event];
    if (targets) {
      // Explicitly type "callback" as any to resolve TS7006 implicit any error
      targets.forEach((callback: any) => {
        try {
          // Cast arguments to bypass TypeScript tuple matching issues
          (callback as (...a: unknown[]) => void)(...args);
        } catch (err) {
          console.error(`[PubSub Emit Error] Exception in listener for event "${event}":`, err);
        }
      });
    }
  }, []);

  // --- Connect to Queue WebSoket (/ws/queue) ---
  const connectQueue = useCallback((playerCount: 2 | 4, playerId: string, playerName?: string, playerAvatar?: string) => {
    if (queueWsRef.current && queueWsRef.current.readyState === WebSocket.OPEN) return;

    const params = new URLSearchParams({ player_id: playerId });
    if (playerName) params.append('player_name', playerName);
    if (playerAvatar) params.append('player_avatar', playerAvatar);
    const path = `/ws/queue/${playerCount}?${params.toString()}`;
    const url = getWsUrl(path);

    console.log(`[Queue WS] Connecting to: ${url}`);
    const ws = new WebSocket(url);
    queueWsRef.current = ws;

   // Explicitly type the raw MessageEvent to eliminate TS7006
    ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);
        console.log('[Queue WS] Message Received:', message);
        
        // تغییر مهم: فقط چک می‌کنیم که game_id در پیام سرور وجود داشته باشد
        if (message.game_id) {
          emit('match_found', message.game_id);
        }
      } catch (err) {
        console.error('[Queue WS Data Parsing Error] Original Data:', event.data, 'Error:', err);
      }
    };

    // Explicitly type WebSocket error as Event
    ws.onerror = (error: Event) => {
      console.error('[Queue WS Connection Error]:', error);
      emit('error', 'Matchmaking queue connection failed.');
    };

    ws.onclose = () => {
      console.log('[Queue WS] Disconnected.');
    };
  }, [getWsUrl, emit]);

  // --- Clear a pending reconnection timer ---
  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  // --- Open (or re-open) the room socket for the current connection config ---
  const openRoomSocket = useCallback((config: RoomConnectionConfig) => {
    const params = new URLSearchParams({ player_id: config.playerId });
    if (config.playerName) params.append('player_name', config.playerName);
    if (config.playerAvatar) params.append('player_avatar', config.playerAvatar);
    const url = getWsUrl(`/ws/room/${config.gameId}?${params.toString()}`);

    setRoomStatus(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting');

    const ws = new WebSocket(url);
    roomWsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
      setRoomStatus('open');
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const payload: RoomMessage = JSON.parse(event.data);
        console.log('[Room WS] Event Dispatcher:', payload.type);

        switch (payload.type) {
          case 'state_update':
            latestGameStateRef.current = payload.state;
            emit('state_update', payload.state);
            break;
          case 'player_status':
            emit('player_status', payload);
            break;
          case 'error':
            emit('error', payload.message);
            break;
          case 'game_over':
            latestGameStateRef.current = payload.state;
            emit('game_over', { reason: payload.reason, state: payload.state });
            emit('state_update', payload.state);
            break;
          default:
            console.warn('[Room WS Warn] Unknown message type received:', payload);
        }
      } catch (err) {
        console.error('[Room WS Data Parsing Error] Original Data:', event.data, 'Error:', err);
      }
    };

    ws.onerror = (error: Event) => {
      console.error('[Room WS Connection Error]:', error);
    };

    ws.onclose = () => {
      // A socket that is no longer the current one was replaced or closed on
      // purpose (leave, unmount, StrictMode remount): never reconnect for it.
      if (roomWsRef.current !== ws) return;
      roomWsRef.current = null;

      if (intentionalCloseRef.current) {
        setRoomStatus('closed');
        return;
      }

      if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setRoomStatus('closed');
        emit('error', 'Lost connection to the game room. Please rejoin from the lobby.');
        return;
      }

      const attempt = reconnectAttemptRef.current;
      reconnectAttemptRef.current = attempt + 1;
      const delay = Math.min(RECONNECT_MAX_DELAY_MS, RECONNECT_BASE_DELAY_MS * 2 ** attempt);
      setRoomStatus('reconnecting');
      clearReconnectTimer();
      reconnectTimerRef.current = setTimeout(() => openRoomSocket(config), delay);
    };
  }, [clearReconnectTimer, emit, getWsUrl]);

  // --- Connect to Room WebSocket (/ws/room) ---
  const connectRoom = useCallback((
    gameId: string,
    playerId: string,
    playerName?: string,
    playerAvatar?: string,
  ) => {
    if (roomWsRef.current && roomWsRef.current.readyState === WebSocket.OPEN) return;

    const config: RoomConnectionConfig = { gameId, playerId, playerName, playerAvatar };
    roomConfigRef.current = config;
    intentionalCloseRef.current = false;
    reconnectAttemptRef.current = 0;
    openRoomSocket(config);
  }, [openRoomSocket]);

  // --- Send Client Action (Draw / Play Card) ---
  const sendAction = useCallback((action: GameAction) => {
    if (!roomWsRef.current || roomWsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[Room WS Warn] Action blocked, WebSocket is not open.');
      emit('error', 'Cannot communicate with server. Connection lost.');
      return;
    }

    try {
      console.log('[Room WS] Sending Client Action:', action.action);
      roomWsRef.current.send(JSON.stringify(action));
    } catch (err) {
      console.error('[Room WS Send Failure] Failed to send action payload:', action, 'Error:', err);
    }
  }, [emit]);

  // --- Cancel Matchmaking Queue ---
  const cancelQueue = useCallback(() => {
    if (queueWsRef.current && queueWsRef.current.readyState === WebSocket.OPEN) {
      console.log('[Queue WS] Sending cancel matchmaking action.');
      try {
        queueWsRef.current.send('cancel');
      } catch (err) {
        console.error('[Queue WS Cancel Error] Failed to send cancel payload:', err);
      }
    }
  }, []);

  // --- Safely disconnect all sockets on unmount ---
  const disconnectAll = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    const queueSocket = queueWsRef.current;
    queueWsRef.current = null;
    if (queueSocket) queueSocket.close();
    // Detach before closing so the close handler does not schedule a reconnect.
    const roomSocket = roomWsRef.current;
    roomWsRef.current = null;
    if (roomSocket) roomSocket.close();
    setRoomStatus('idle');
  }, [clearReconnectTimer]);

  useEffect(() => {
    return () => {
      disconnectAll();
    };
  }, [disconnectAll]);

  return {
    connectQueue,
    connectRoom,
    sendAction,
    cancelQueue,
    subscribe,
    disconnectAll,
    roomStatus,
    getLatestState: () => latestGameStateRef.current
  };
};