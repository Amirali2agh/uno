import React, { useMemo, useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from './Card';
import type { Card as CardType } from '../types/uno';

interface CardHandProps {
  hand: CardType[]; // List of cards in the player's active hand
  onPlayCard: (index: number) => void; // Triggered when a card from hand is selected
  customAssets?: Record<string, string>; // Dynamic skins lookup dictionary
}

export const CardHand: React.FC<CardHandProps> = ({
  hand,
  onPlayCard,
  customAssets = {},
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(320);

  // Measure container width on mount and resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setContainerWidth(el.offsetWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Compress array beforehand to avoid math anomalies with empty slots
  const validCards = useMemo(() => hand.filter(Boolean), [hand]);

  // Trigonometric arc calculations memorized to prevent heavy layout recalculation
  const positionedCards = useMemo(() => {
    const N = validCards.length;
    if (N === 0) return [];

    const cardWidth = 64; // w-16 in px — includes card width + gap
    const padding = 16; // keep a gap from screen edges

    // Available width for the fan spread (85% of container to leave breathing room)
    const availableWidth = Math.max(cardWidth * 3, containerWidth * 0.85 - padding * 2);
    const halfWidth = availableWidth / 2;

    // Maximum spread angle: reduce when many cards so they overlap more
    // Start at 50° for few cards, shrink to 30° for many cards
    const maxSpread = Math.max(30, Math.min(50, 8 * (N - 1)));

    // Compute radius so that the outermost card fits within halfWidth
    // Edge card angle = maxSpread / 2; its center is at sin(angle) * radius
    // We want: sin(halfAngle) * radius + cardWidth/2 <= halfWidth
    const halfAngleRad = ((maxSpread / 2) * Math.PI) / 180;
    const maxRadius = (halfWidth - cardWidth / 2) / Math.sin(halfAngleRad);
    const radius = Math.max(cardWidth * 2, Math.min(350, maxRadius));

    const angleStep = N > 1 ? maxSpread / (N - 1) : 0;
    const midIndex = (N - 1) / 2;

    return validCards.map((card, index) => {
      // Calculate relative degrees from the midpoint
      const cardAngleDeg = (index - midIndex) * angleStep;
      // Convert degrees to radians for mathematical functions
      const cardAngleRad = (cardAngleDeg * Math.PI) / 180;

      // Trigonometry calculation for absolute 2D arc coordinate mapping
      const x = Math.sin(cardAngleRad) * radius;
      const y = (Math.cos(cardAngleRad) - 1) * radius; // Depresses the Y-axis symmetrically away from the midpoint
      const rotate = cardAngleDeg; // Aligns card rotation with the circle tangent

      return {
        card,
        originalIndex: index, // Track original index for action callbacks
        transform: { x, y, rotate },
      };
    });
  }, [validCards, containerWidth]);

  return (
    <div ref={containerRef} className="relative w-full h-40 max-w-md mx-auto flex items-end justify-center overflow-visible pb-4">
      {/* Absolute center zero-point anchor container for trigonometric projection */}
      <div className="absolute bottom-4 flex items-center justify-center w-0 h-0 overflow-visible">
        <AnimatePresence mode="popLayout">
          {positionedCards.map(({ card, originalIndex, transform }) => {
            // Dynamic skin resolve key construction
            const assetKey = `${card.color}_${card.value}`;
            const customAssetUrl = customAssets[assetKey];

            return (
              <motion.div
                key={`${card.color}-${card.value}-${originalIndex}`}
                layout // Smoothly slides adjacent cards when gap transitions occur
                initial={{ opacity: 0, scale: 0.2, y: 100 }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  x: transform.x,
                  y: transform.y,
                  rotate: transform.rotate,
                }}
                exit={{ opacity: 0, scale: 0.5, y: -80, rotate: 0 }}
                transition={{
                  type: 'spring',
                  stiffness: 140,
                  damping: 18,
                  mass: 0.8,
                }}
                style={{
                  position: 'absolute',
                  transformOrigin: 'bottom center', // Crucial: anchor scaling relative to the hand base
                }}
              >
                <Card
                  card={card}
                  onClick={() => onPlayCard(originalIndex)}
                  customAssetUrl={customAssetUrl}
                />
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};