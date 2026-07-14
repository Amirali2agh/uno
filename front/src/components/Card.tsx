import React from 'react';
import type { Card as CardType } from '../types/uno';

interface CardProps {
  card: CardType;
  onClick?: () => void;
  customAssetUrl?: string;
  isHoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  card,
  onClick,
  customAssetUrl,
  isHoverable = true,
}) => {
  // رنگ پس‌زمینه اصلی کارت
  const getBgColor = (color: string) => {
    switch (color) {
      case 'red': return 'bg-red-500';
      case 'blue': return 'bg-blue-500';
      case 'green': return 'bg-green-500';
      case 'yellow': return 'bg-yellow-400';
      case 'black': return 'bg-gradient-to-br from-red-500 via-yellow-400 to-blue-500'; // رنگین‌کمان برای کارت Wild
      default: return 'bg-slate-800';
    }
  };

  // رنگ متن داخل بیضی سفید وسط کارت
  const getInnerTextColor = (color: string) => {
    switch (color) {
      case 'red': return 'text-red-500';
      case 'blue': return 'text-blue-500';
      case 'green': return 'text-green-500';
      case 'yellow': return 'text-yellow-500';
      case 'black': return 'text-slate-900';
      default: return 'text-slate-800';
    }
  };

  const getDisplayValue = (value: string) => {
    switch (value) {
      case 'skip': return '⊘';
      case 'reverse': return '⇄';
      case 'draw2': return '+2';
      case 'wild': return 'W';
      case 'wild4': return '+4';
      default: return value;
    }
  };

  const displayVal = getDisplayValue(card.value);

  return (
    <div
      onClick={onClick}
      className={`
        relative w-16 h-24 min-w-[4rem] rounded-xl border-[3px] border-white flex flex-col justify-between p-1 
        shadow-[0_4px_10px_rgba(0,0,0,0.3)] select-none cursor-pointer transform-gpu transition-all duration-200 origin-bottom
        ${getBgColor(card.color)}
        ${isHoverable ? 'hover:-translate-y-5 hover:scale-110 hover:shadow-[0_10px_20px_rgba(0,0,0,0.5)] hover:z-50' : ''}
      `}
    >
      {customAssetUrl ? (
        <img src={customAssetUrl} alt="card" className="w-full h-full object-contain" draggable={false} />
      ) : (
        <>
          {/* عدد کوچک بالا سمت چپ */}
          <span className="text-white text-[10px] font-black leading-none drop-shadow-md">
            {displayVal}
          </span>

          {/* بیضی سفید وسط کارت (طراحی کلاسیک اونو) */}
          <div className="absolute inset-0 m-auto w-11 h-16 bg-white rounded-[40%] transform -rotate-12 shadow-inner flex items-center justify-center">
            <span className={`text-2xl font-black tracking-tighter transform rotate-12 drop-shadow-sm ${getInnerTextColor(card.color)}`}>
              {displayVal}
            </span>
          </div>

          {/* عدد کوچک پایین سمت راست (برعکس شده) */}
          <span className="text-white text-[10px] font-black leading-none self-end rotate-180 drop-shadow-md">
            {displayVal}
          </span>
        </>
      )}
    </div>
  );
};