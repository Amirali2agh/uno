import React, { useEffect, useState, useMemo } from 'react';
import { useUnoSocket } from '../hooks/useUnoSocket.ts';
import { CardHand } from './CardHand.tsx';
import { DiscardPile } from './DiscardPile.tsx';
import { OpponentSeat } from './OpponentSeat.tsx';
import type { GameState, PlayerState } from '../types/uno';

interface GameRoomProps {
  gameId: string;
  playerId: string;
  playerName: string;
  playerAvatar: string;
  onExit: () => void;
}

export const GameRoom: React.FC<GameRoomProps> = ({ gameId, playerId, playerName, playerAvatar, onExit }) => {
  const { connectRoom, sendAction, subscribe } = useUnoSocket();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [errorLog, setErrorLog] = useState<string | null>(null);
  const [showColorPicker, setShowColorPicker] = useState<boolean>(false);
  const [pendingCardIndex, setPendingCardIndex] = useState<number | null>(null);
  const [gameOver, setGameOver] = useState<{ reason: string } | null>(null);

  useEffect(() => {
    connectRoom(gameId, playerId, playerName, playerAvatar);
    const unsubscribeState = subscribe('state_update', (newState) => {
      setGameState(newState);
      setErrorLog(null);
      // If state says finished but no game_over event came, still show the overlay
      if (newState.status === 'finished' && !gameOver) {
        setGameOver({ reason: newState.winner ? `${newState.winner} won!` : 'Game finished' });
      }
    });
    const unsubscribeError = subscribe('error', (message) => {
      setErrorLog(message);
      setTimeout(() => setErrorLog(null), 3000);
    });
    const unsubscribeGameOver = subscribe('game_over', (payload) => {
      setGameOver({ reason: payload.reason });
    });
    return () => {
      unsubscribeState();
      unsubscribeError();
      unsubscribeGameOver();
    };
  }, [gameId, playerId, connectRoom, subscribe]);

  const myPlayerState = useMemo(() => gameState?.players.find((p) => p.player_id === playerId) || null, [gameState, playerId]);

  const sortedOpponents = useMemo(() => {
    if (!gameState) return [];
    const myIndex = gameState.players.findIndex((p) => p.player_id === playerId);
    if (myIndex === -1) return [];
    const opponents: PlayerState[] = [];
    for (let i = 1; i < gameState.players.length; i++) {
      opponents.push(gameState.players[(myIndex + i) % gameState.players.length]);
    }
    return opponents;
  }, [gameState, playerId]);

  const isMyTurn = useMemo(() => {
    if (!gameState) return false;
    return gameState.players[gameState.current_turn_index]?.player_id === playerId;
  }, [gameState, playerId]);

  const handlePlayCard = (index: number) => {
    if (!myPlayerState) return;
    const selectedCard = myPlayerState.hand[index];
    if (!selectedCard) return;

    if (selectedCard.color === 'black') {
      setPendingCardIndex(index);
      setShowColorPicker(true);
    } else {
      sendAction({ action: 'play_card', card_index: index, chosen_color: null });
    }
  };

  const handleColorSelect = (color: 'red' | 'blue' | 'green' | 'yellow') => {
    if (pendingCardIndex === null) return;
    sendAction({ action: 'play_card', card_index: pendingCardIndex, chosen_color: color });
    setShowColorPicker(false);
    setPendingCardIndex(null);
  };

  if (!gameState) return null;

  return (
    // بک‌گراند کاملاً تاریک و شیک
    <div className="relative flex flex-col w-full h-screen max-h-[640px] bg-slate-950 text-white overflow-hidden p-4 pt-4 pb-2 select-none">
      
      {/* هاله نوری نارنجی ملایم در مرکز میز */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(234,88,12,0.15)_0%,_transparent_60%)] pointer-events-none z-0"></div>

      {/* واترمارک مدرن، افقی و بسیار تمیز در مرکز */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
        <span className="text-6xl sm:text-7xl font-black text-white opacity-[0.03] tracking-[0.3em] uppercase">
          Porteghal
        </span>
        <span className="text-xl sm:text-2xl font-bold text-orange-500 opacity-[0.15] tracking-[0.8em] mt-2 ml-3">
          پرتغال
        </span>
      </div>

      {/* Header */}
      <header className="relative flex justify-between items-center h-10 shrink-0 z-10">
        <button onClick={onExit} className="text-xs font-bold text-slate-400 hover:text-white px-4 py-2 rounded-full bg-slate-900/80 border border-slate-800 backdrop-blur-md transition-all">
          ← Leave
        </button>
        <span className="text-xs font-mono font-bold text-orange-400/70 bg-slate-900/80 px-3 py-1 rounded-full border border-slate-800">
          ROOM: {gameId.substring(0, 8)}
        </span>
      </header>

      {errorLog && (
        <div className="absolute top-14 left-4 right-4 z-50 py-3 px-4 bg-rose-600/90 border border-rose-400 backdrop-blur-md rounded-2xl text-center shadow-2xl animate-fade-in">
          <p className="text-sm font-bold text-white">{errorLog}</p>
        </div>
      )}

      {/* Opponents */}
      <div className="relative flex justify-center items-center gap-6 h-16 shrink-0 overflow-visible mt-1 z-10">
        {sortedOpponents.map((opponent) => (
          <OpponentSeat key={opponent.player_id} player={opponent} isCurrentTurn={gameState.players[gameState.current_turn_index]?.player_id === opponent.player_id} />
        ))}
      </div>

      {/* Center Table */}
      <div className="relative flex flex-col items-center justify-center flex-1 min-h-0 z-10">
        <div className="flex items-center justify-center gap-10 overflow-visible">
          
          {/* Draw Deck */}
          <div 
            onClick={() => sendAction({ action: 'draw_card' })}
            className={`
              relative w-20 h-28 rounded-xl border-[3px] border-white bg-red-600 
              shadow-[0_8px_15px_rgba(0,0,0,0.5)] flex flex-col items-center justify-center cursor-pointer transform-gpu active:scale-95 transition-all
              ${isMyTurn ? 'ring-4 ring-orange-500 ring-offset-4 ring-offset-slate-950 animate-pulse' : 'opacity-90'}
            `}
          >
            <div className="absolute -bottom-2 -right-2 w-full h-full rounded-xl border-[3px] border-white bg-red-800 -z-10"></div>
            <div className="absolute -bottom-1 -right-1 w-full h-full rounded-xl border-[3px] border-white bg-red-700 -z-10"></div>
            
            <div className="w-14 h-20 bg-white rounded-[40%] transform -rotate-12 shadow-inner flex items-center justify-center">
              <span className="text-xl font-black text-red-500 transform rotate-12 tracking-tighter">UNO</span>
            </div>
          </div>

          <DiscardPile discardPile={gameState.discard_pile} activeColor={gameState.active_color} />
        </div>
      </div>

      {/* Player Hand & Turn Indicator */}
      <div className="relative flex flex-col items-center z-10">

        {/* Local Player Info */}
        <div className="flex items-center gap-2 px-3 py-0.5 rounded-full bg-slate-900/60 border border-slate-800/50 backdrop-blur-sm">
          <div className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700 overflow-hidden shrink-0">
            {playerAvatar ? (
              <img src={playerAvatar} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className="text-[10px] font-bold text-slate-300">
                {(playerName || playerId).substring(0, 2).toUpperCase()}
              </span>
            )}
          </div>
          <span className="text-xs font-semibold text-slate-200">{playerName || playerId}</span>
        </div>

        <div className="flex flex-col items-center mt-1">
          <div className={`
            px-5 py-1.5 rounded-full border-2 text-[11px] font-black tracking-widest flex items-center gap-2 transition-all shadow-xl
            ${isMyTurn 
              ? 'bg-orange-500 border-orange-400 text-white scale-110 animate-bounce' 
              : 'bg-slate-900/80 border-slate-800 text-slate-500 backdrop-blur-md'
            }
          `}>
            {isMyTurn ? 'YOUR TURN' : 'WAITING...'}
          </div>
        </div>

        {myPlayerState && (
          <div className="w-full overflow-visible -mt-1">
            <CardHand hand={myPlayerState.hand} onPlayCard={handlePlayCard} />
          </div>
        )}
      </div>

      {/* Game Over Overlay */}
      {gameOver && (
        <div className="absolute inset-0 z-40 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-8">
          <div className="bg-slate-900 border border-slate-700/50 p-8 rounded-3xl max-w-xs w-full text-center shadow-2xl">
            <div className="text-5xl mb-4">🏆</div>
            <h2 className="text-xl font-black text-white mb-2">Game Over</h2>
            <p className="text-sm text-slate-400 mb-6">{gameOver.reason}</p>
            <button
              onClick={onExit}
              className="w-full py-3 rounded-xl bg-orange-600 text-white font-bold text-sm hover:bg-orange-500 transition-all active:scale-95 shadow-lg"
            >
              ← Back to Lobby
            </button>
          </div>
        </div>
      )}

      {/* Color Picker Modal */}
      {showColorPicker && (
        <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-6">
          <div className="bg-slate-900 border border-slate-700 p-6 rounded-3xl max-w-xs w-full text-center shadow-2xl">
            <h3 className="text-sm font-black tracking-widest text-white mb-6">CHOOSE COLOR</h3>
            <div className="grid grid-cols-2 gap-4">
              <button onClick={() => handleColorSelect('red')} className="h-16 rounded-2xl bg-red-500 border-2 border-white shadow-lg active:scale-95 transition-all"></button>
              <button onClick={() => handleColorSelect('blue')} className="h-16 rounded-2xl bg-blue-500 border-2 border-white shadow-lg active:scale-95 transition-all"></button>
              <button onClick={() => handleColorSelect('green')} className="h-16 rounded-2xl bg-green-500 border-2 border-white shadow-lg active:scale-95 transition-all"></button>
              <button onClick={() => handleColorSelect('yellow')} className="h-16 rounded-2xl bg-yellow-400 border-2 border-white shadow-lg active:scale-95 transition-all"></button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};