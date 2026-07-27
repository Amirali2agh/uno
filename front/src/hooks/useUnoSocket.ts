import { useEffect, useRef, useCallback } from 'react';
import type { GameState, RoomMessage, GameAction, GameOverPayload } from '../types/uno';

// --- Type definition for our lightweight PubSub event map ---
type UnoEventMap = {
  state_update: (state: GameState) => void;
  player_status: (payload: { player_id: string; status: 'connected' | 'disconnected' }) => void;
  error: (message: string) => void;
  match_found: (gameId: string) => void;
  game_over: (payload: GameOverPayload) => void;
};

export const useUnoSocket = () => {
  // --- Refs for managing WebSocket connection lifecycles ---
  const queueWsRef = useRef<WebSocket | null>(null);
  const roomWsRef = useRef<WebSocket | null>(null);

  // --- PubSub Listeners registry stored in a ref using flexible internal Sets to bypass React render ---
  const listenersRef = useRef<{ [K in keyof UnoEventMap]?: Set<any> }>({});

  // --- Cache the latest GameState in a ref to prevent Stale Closures inside WS callbacks ---
  const latestGameStateRef = useRef<GameState | null>(null);

  // --- Dynamic WS URL Resolver to support WSL network bridge mobile testing ---
  const getWsUrl = useCallback((path: string): string => {
    try {
      const hostname = window.location.hostname || 'localhost';
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${hostname}${path}`;
    } catch (err) {
      console.error('[WS Resolution Error] Failed to resolve hostname:', err);
      return `ws://localhost${path}`;
    }
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

  // --- Connect to Room WebSocket (/ws/room) ---
  const connectRoom = useCallback((gameId: string, playerId: string, playerName?: string, playerAvatar?: string) => {
    if (roomWsRef.current && roomWsRef.current.readyState === WebSocket.OPEN) return;

    const params = new URLSearchParams({ player_id: playerId });
    if (playerName) params.append('player_name', playerName);
    if (playerAvatar) params.append('player_avatar', playerAvatar);
    const path = `/ws/room/${gameId}?${params.toString()}`;
    const url = getWsUrl(path);

    console.log(`[Room WS] Connecting to game room: ${url}`);
    const ws = new WebSocket(url);
    roomWsRef.current = ws;

    // Explicitly type MessageEvent to prevent implicit any errors
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

    // Explicitly type WebSocket error as Event
    ws.onerror = (error: Event) => {
      console.error('[Room WS Connection Error]:', error);
      emit('error', 'Connection to the game room failed.');
    };

    ws.onclose = () => {
      console.log('[Room WS] Connection closed.');
    };
  }, [getWsUrl, emit]);

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
    if (queueWsRef.current) {
      queueWsRef.current.close();
      queueWsRef.current = null;
    }
    if (roomWsRef.current) {
      roomWsRef.current.close();
      roomWsRef.current = null;
    }
  }, []);

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
    getLatestState: () => latestGameStateRef.current
  };
};