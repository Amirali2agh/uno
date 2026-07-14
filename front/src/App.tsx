import React, { useState, useEffect } from 'react';
import { GameRoom } from './components/GameRoom.tsx';
import { useUnoSocket } from './hooks/useUnoSocket.ts';
import { resolvePlayerId } from './utils/userResolver.ts';

type ScreenState = 'lobby' | 'queueing' | 'playing';

export const App: React.FC = () => {
  // --- Application States ---
  const [screen, setScreen] = useState<ScreenState>('lobby');
  const [playerId, setPlayerId] = useState<string>('');
  const [playerCount, setPlayerCount] = useState<2 | 4>(2);
  const [gameId, setGameId] = useState<string | null>(null);

  // --- WebSocket Hook ---
  const { connectQueue, cancelQueue, subscribe, disconnectAll } = useUnoSocket();

  // 1. Resolve Player ID on initial load
  useEffect(() => {
    const resolvedId = resolvePlayerId();
    setPlayerId(resolvedId);
  }, []);

  // 2. Listen for Matchmaking Success Event
  useEffect(() => {
    const unsubscribeMatch = subscribe('match_found', (matchedGameId: string) => {
      console.log('[App] Match found! Transitioning to Game Room:', matchedGameId);
      setGameId(matchedGameId);
      setScreen('playing');
    });

    return () => {
      unsubscribeMatch();
    };
  }, [subscribe]);

  // --- Action Handlers ---
  const handleJoinQueue = () => {
    if (!playerId) return;
    setScreen('queueing');
    connectQueue(playerCount, playerId);
  };

  const handleCancelQueue = () => {
    cancelQueue(); // Send 'cancel' to backend
    disconnectAll(); // Close socket
    setScreen('lobby');
  };

  const handleExitGame = () => {
    disconnectAll();
    setGameId(null);
    setScreen('lobby');
  };

  // --- Render: Playing Screen ---
  if (screen === 'playing' && gameId) {
    return (
      <GameRoom 
        gameId={gameId} 
        playerId={playerId} 
        onExit={handleExitGame} 
      />
    );
  }

  // --- Render: Queueing Screen ---
  if (screen === 'queueing') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#1a2c34] text-white p-4 select-none">
        <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 p-8 rounded-3xl shadow-2xl flex flex-col items-center max-w-xs w-full text-center">
          <div className="relative w-16 h-16 mb-6">
            <div className="absolute inset-0 rounded-full border-t-4 border-emerald-500 animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-b-4 border-blue-500 animate-spin animation-delay-150"></div>
          </div>
          <h2 className="text-lg font-bold text-slate-200 tracking-tight mb-2">Searching for players...</h2>
          <p className="text-xs text-slate-400 mb-8">Mode: {playerCount} Players</p>
          
          <button
            onClick={handleCancelQueue}
            className="w-full py-3 rounded-xl bg-rose-950/50 text-rose-400 font-bold text-sm border border-rose-900/50 hover:bg-rose-900/50 transition-all active:scale-95"
          >
            Cancel Matchmaking
          </button>
        </div>
      </div>
    );
  }

  // --- Render: Lobby Screen ---
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#1a2c34] text-white p-4 select-none">
      <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 p-8 rounded-3xl shadow-2xl max-w-sm w-full">
        
        {/* Logo / Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-red-600 to-red-800 shadow-lg shadow-red-900/50 mb-4 transform rotate-3">
            <span className="text-2xl font-black tracking-tighter text-white -rotate-3">UNO</span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-100">Multiplayer</h1>
        </div>

        {/* Player Info */}
        <div className="mb-6 bg-slate-950/50 p-4 rounded-2xl border border-slate-800/50 flex justify-between items-center">
          <span className="text-xs font-semibold text-slate-400">Playing as:</span>
          <span className="text-sm font-bold text-emerald-400">{playerId || 'Loading...'}</span>
        </div>

        {/* Game Mode Selector */}
        <div className="mb-8">
          <label className="block text-xs font-bold text-slate-400 mb-3 uppercase tracking-wider">Select Game Mode</label>
          <div className="flex gap-3">
            {[2, 4].map((count) => (
              <button
                key={count}
                onClick={() => setPlayerCount(count as 2 | 4)}
                className={`flex-1 py-3 rounded-xl font-bold text-sm transition-all active:scale-95 ${
                  playerCount === count 
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/50 border border-emerald-500' 
                    : 'bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700'
                }`}
              >
                {count} Players
              </button>
            ))}
          </div>
        </div>

        {/* Start Button */}
        <button
          onClick={handleJoinQueue}
          disabled={!playerId}
          className="w-full py-4 rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 text-white font-extrabold text-sm shadow-lg shadow-blue-900/50 hover:from-blue-500 hover:to-blue-400 transition-all active:scale-95 disabled:opacity-50"
        >
          FIND MATCH
        </button>

      </div>
    </div>
  );
};

export default App;