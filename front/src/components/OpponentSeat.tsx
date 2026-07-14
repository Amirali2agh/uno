import React, { useMemo } from 'react';
import type { PlayerState } from '../types/uno';

interface OpponentSeatProps {
  player: PlayerState; // Opponent player state received from backend
  isCurrentTurn: boolean; // Is it currently this opponent's turn?
  customCardBack?: string; // Optional custom asset URL for the back of cards
}

export const OpponentSeat: React.FC<OpponentSeatProps> = ({
  player,
  isCurrentTurn,
  customCardBack,
}) => {
  const cardCount = player.hand.length;

  // Generate array representation of card back indices for rendering loop
  const cardBacks = useMemo(() => {
    return Array.from({ length: Math.min(10, cardCount) }); // Cap visual fan representation at 10 items max
  }, [cardCount]);

  return (
    <div className="flex flex-col items-center gap-2 select-none">
      {/* Player Glassmorphic Profile Card with active turn indicators */}
      <div className={`
        relative flex items-center gap-3 px-4 py-2 rounded-2xl border backdrop-blur-md transition-all duration-300
        ${isCurrentTurn 
          ? 'bg-emerald-950/40 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)] scale-105' 
          : 'bg-slate-900/50 border-slate-800'
        }
      `}>
        {/* Profile Avatar Frame */}
        <div className="relative w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700">
          <span className="text-xs font-bold text-slate-300">
            {player.player_id.substring(0, 2).toUpperCase()}
          </span>
          {/* Active Turn Pulsing Dot */}
          {isCurrentTurn && (
            <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          )}
        </div>

        {/* Username & Card Count */}
        <div className="flex flex-col items-start leading-none">
          <span className="text-xs font-semibold text-slate-200 tracking-tight">{player.player_id}</span>
          <span className="text-[10px] font-bold text-slate-400 mt-1 flex items-center gap-1">
            🃏 <span className="text-emerald-400">{cardCount}</span> Cards
          </span>
        </div>
      </div>

      {/* Opponent overlapping miniature card backs fan layout pointing downwards */}
      {cardCount > 0 && (
        <div className="flex items-center justify-center h-8 overflow-visible mt-1">
          <div className="flex -space-x-3 overflow-visible justify-center">
            {cardBacks.map((_, idx) => {
              // Mathematical rotation calculation to curve card backs inwards
              const mid = (cardBacks.length - 1) / 2;
              const rot = (idx - mid) * 4; // Slight fan rotation

              return (
                <div
                  key={idx}
                  className="w-5 h-8 rounded-md border border-slate-100 flex-shrink-0 shadow-md bg-gradient-to-br from-red-700 to-red-900"
                  style={{
                    transform: `rotate(${rot}deg)`,
                    transformOrigin: 'bottom center',
                    backgroundImage: customCardBack ? `url(${customCardBack})` : undefined,
                    backgroundSize: 'cover',
                  }}
                />
              );
            })}
            
            {/* Show plus count offset if actual card count exceeds capped fanned list */}
            {cardCount > 10 && (
              <div className="w-5 h-8 rounded-md bg-slate-800 border border-slate-700 flex items-center justify-center shadow-md">
                <span className="text-[8px] font-bold text-slate-300">+{cardCount - 10}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};