import React, { useEffect, useState, useMemo } from 'react';
import { useUnoSocket } from '../hooks/useUnoSocket.ts';
import { CardHand } from './CardHand.tsx';
import { DiscardPile } from './DiscardPile.tsx';
import { OpponentSeat } from './OpponentSeat.tsx';
import type { GameState, PlayerState } from '../types/uno';

interface GameRoomProps {
  gameId: string;
  playerId: string;
  onExit: () => void;
}

export const GameRoom: React.FC<GameRoomProps> = ({ gameId, playerId, onExit }) => {
  const { connectRoom, sendAction, subscribe } = useUnoSocket();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [errorLog, setErrorLog] = useState<string | null>(null);
  const [showColorPicker, setShowColorPicker] = useState<boolean>(false);
  const [pendingCardIndex, setPendingCardIndex] = useState<number | null>(null);

  useEffect(() => {
    connectRoom(gameId, playerId);
    const unsubscribeState = subscribe('state_update', (newState) => {
      setGameState(newState);
      setErrorLog(null);
    });
    const unsubscribeError = subscribe('error', (message) => {
      setErrorLog(message);
      setTimeout(() => setErrorLog(null), 3000);
    });
    return () => {
      unsubscribeState();
      unsubscribeError();
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
    // تم اختصاصی پرتغال: گرادیانت شعاعی از نارنجی روشن به مشکی
    <div className="relative flex flex-col justify-between w-full h-screen max-h-[640px] bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-orange-600 via-orange-900 to-black text-white overflow-hidden p-4 select-none shadow-inner">
      
      {/* واترمارک بزرگ پس‌زمینه (لوگو/اسم پرتغال) */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
        <div className="transform -rotate-12 flex flex-col items-center opacity-[0.06]">
          <span className="text-[10rem] leading-none font-black text-white drop-shadow-2xl">پرتغال</span>
          <span className="text-4xl font-black tracking-[0.8em] text-white ml-4 mt-2">PORTEGHAL</span>
        </div>
      </div>

      {/* Header */}
      <header className="relative flex justify-between items-center h-10 z-10">
        <button onClick={onExit} className="text-xs font-bold text-orange-200 hover:text-white px-4 py-2 rounded-full bg-black/30 border border-orange-500/30 backdrop-blur-md transition-all">
          ← Leave
        </button>
        <span className="text-xs font-mono font-bold text-orange-300 bg-black/40 px-3 py-1 rounded-full border border-orange-500/30">
          ROOM: {gameId.substring(0, 8)}
        </span>
      </header>

      {errorLog && (
        <div className="absolute top-14 left-4 right-4 z-50 py-3 px-4 bg-rose-600/90 border border-rose-400 backdrop-blur-md rounded-2xl text-center shadow-2xl animate-fade-in">
          <p className="text-sm font-bold text-white">{errorLog}</p>
        </div>
      )}

      {/* Opponents */}
      <div className="relative flex justify-center items-center gap-6 h-20 overflow-visible mt-2 z-10">
        {sortedOpponents.map((opponent) => (
          <OpponentSeat key={opponent.player_id} player={opponent} isCurrentTurn={gameState.players[gameState.current_turn_index]?.player_id === opponent.player_id} />
        ))}
      </div>

      {/* Center Table */}
      <div className="relative flex flex-col items-center justify-center flex-1 my-4 z-10">
        <div className="flex items-center justify-center gap-10 overflow-visible">
          
          {/* Draw Deck */}
          <div 
            onClick={() => sendAction({ action: 'draw_card' })}
            className={`
              relative w-20 h-28 rounded-xl border-[3px] border-white bg-red-600 
              shadow-[0_8px_15px_rgba(0,0,0,0.5)] flex flex-col items-center justify-center cursor-pointer transform-gpu active:scale-95 transition-all
              ${isMyTurn ? 'ring-4 ring-emerald-400 ring-offset-4 ring-offset-orange-900 animate-pulse' : 'opacity-90'}
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
      <div className="relative flex flex-col items-center gap-2 h-48 overflow-visible z-10">
        <div className="flex flex-col items-center mb-2">
          <div className={`
            px-6 py-2 rounded-full border-2 text-xs font-black tracking-widest flex items-center gap-2 transition-all shadow-xl
            ${isMyTurn 
              ? 'bg-emerald-500 border-emerald-400 text-white scale-110 animate-bounce' 
              : 'bg-black/40 border-orange-500/30 text-orange-200 backdrop-blur-md'
            }
          `}>
            {isMyTurn ? 'YOUR TURN' : 'WAITING...'}
          </div>
        </div>

        {myPlayerState && (
          <div className="w-full h-32 overflow-visible">
            <CardHand hand={myPlayerState.hand} onPlayCard={handlePlayCard} />
          </div>
        )}
      </div>

      {/* Color Picker Modal */}
      {showColorPicker && (
        <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-6">
          <div className="bg-orange-950 border border-orange-800 p-6 rounded-3xl max-w-xs w-full text-center shadow-2xl">
            <h3 className="text-sm font-black tracking-widest text-orange-200 mb-6">CHOOSE COLOR</h3>
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