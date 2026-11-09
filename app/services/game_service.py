import random
from typing import List, Optional
from pydantic import BaseModel
from redis.asyncio import Redis
from app.utils.redis_keys import get_game_state_key, get_game_lock_key

# ==========================================
# Models (ساختار داده‌های بازی)
# ==========================================

class Card(BaseModel):
    color: str
    value: str

class PlayerState(BaseModel):
    player_id: str
    player_name: str = ""
    player_avatar: str = ""
    hand: List[Card] = []

class GameState(BaseModel):
    game_id: str
    players: List[PlayerState]
    current_turn_index: int = 0
    direction: int = 1
    draw_pile: List[Card]
    discard_pile: List[Card] = []
    active_color: str = ""
    status: str = "active"
    winner: Optional[str] = None

# ==========================================
# Game Service (منطق اصلی بازی)
# ==========================================

class GameService:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _generate_uno_deck(self) -> List[Card]:
        """تولید و بُر زدن ۱۰۸ کارت استاندارد اونو"""
        colors = ['red', 'blue', 'green', 'yellow']
        deck = []
        for color in colors:
            deck.append(Card(color=color, value='0'))
            for value in ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'skip', 'reverse', 'draw2']:
                deck.append(Card(color=color, value=value))
                deck.append(Card(color=color, value=value))
        for _ in range(4):
            deck.append(Card(color='black', value='wild'))
            deck.append(Card(color='black', value='wild4'))
        random.shuffle(deck)
        return deck

    async def create_game(self, game_id: str, players_data: list[dict]) -> GameState:
        """ساخت بازی جدید و پخش کارت‌ها"""
        deck = self._generate_uno_deck()
        players = [
            PlayerState(
                player_id=p["player_id"],
                player_name=p.get("player_name", ""),
                player_avatar=p.get("player_avatar", ""),
                hand=[deck.pop() for _ in range(7)]
            )
            for p in players_data
        ]
        
        discard_pile = []
        while True:
            first_card = deck.pop()
            if first_card.color != 'black':
                discard_pile.append(first_card)
                break
            deck.insert(random.randint(0, len(deck)), first_card)

        game_state = GameState(
            game_id=game_id,
            players=players,
            draw_pile=deck,
            discard_pile=discard_pile,
            active_color=discard_pile[-1].color
        )
        await self.save_game_state(game_state)
        return game_state

    async def get_game_state(self, game_id: str) -> Optional[GameState]:
        """گرفتن وضعیت بازی از ردیس"""
        data = await self.redis.get(get_game_state_key(game_id))
        return GameState.model_validate_json(data) if data else None

    async def save_game_state(self, game_state: GameState) -> None:
        """ذخیره وضعیت بازی در ردیس"""
        await self.redis.set(get_game_state_key(game_state.game_id), game_state.model_dump_json())

    def _next_turn(self, state: GameState, steps: int = 1) -> None:
        """محاسبه نوبت نفر بعدی"""
        num_players = len(state.players)
        state.current_turn_index = (state.current_turn_index + (state.direction * steps)) % num_players

    def _holds_active_color(self, player: PlayerState, excluded_index: int, active_color: str) -> bool:
        """آیا بازیکن کارتی هم‌رنگ رنگ فعال دارد؟ (کارت در حال بازی نادیده گرفته می‌شود)"""
        return any(
            card.color == active_color
            for index, card in enumerate(player.hand)
            if index != excluded_index
        )

    def _draw_cards_from_pile(self, state: GameState, count: int) -> List[Card]:
        """برداشتن کارت از زمین (اگر کارت‌ها تمام شد، کارت‌های سوخته را بُر می‌زند)"""
        drawn = []
        for _ in range(count):
            if not state.draw_pile:
                top_card = state.discard_pile.pop()
                state.draw_pile = state.discard_pile
                random.shuffle(state.draw_pile)
                state.discard_pile = [top_card]
                if not state.draw_pile:
                    break
            drawn.append(state.draw_pile.pop())
        return drawn

    async def draw_card(self, game_id: str, player_id: str) -> bool:
        """بازیکن یک کارت از زمین برمی‌دارد"""
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return False
                
            current_player = state.players[state.current_turn_index]
            if current_player.player_id != player_id:
                return False # نوبت این بازیکن نیست
                
            drawn_cards = self._draw_cards_from_pile(state, 1)
            current_player.hand.extend(drawn_cards)
            
            self._next_turn(state)
            await self.save_game_state(state)
            return True

    async def play_card(self, game_id: str, player_id: str, card_index: int, chosen_color: Optional[str] = None) -> bool:
        """بازیکن یک کارت را بازی می‌کند"""
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return False
                
            current_player = state.players[state.current_turn_index]
            if current_player.player_id != player_id:
                return False # نوبت این بازیکن نیست
                
            if card_index < 0 or card_index >= len(current_player.hand):
                return False
                
            card_to_play = current_player.hand[card_index]
            top_card = state.discard_pile[-1]
            
            # بررسی اینکه آیا کارت مجاز است یا خیر
            is_valid_play = (
                card_to_play.color == 'black' or 
                card_to_play.color == state.active_color or 
                card_to_play.value == top_card.value
            )
            
            if not is_valid_play:
                return False
                
            if card_to_play.color == 'black' and not chosen_color:
                return False # برای کارت مشکی باید رنگ انتخاب شود

            # Wild Draw Four is only legal when the player holds no card that
            # matches the active colour (the card being played excluded).
            if card_to_play.value == 'wild4' and self._holds_active_color(current_player, card_index, state.active_color):
                return False
                
            # بازی کردن کارت
            current_player.hand.pop(card_index)
            state.discard_pile.append(card_to_play)
            state.active_color = chosen_color if card_to_play.color == 'black' else card_to_play.color

            # Apply the card effect *before* checking for a win: a Draw Two or Wild
            # Draw Four played as the last card still forces the next player to draw.
            steps = self._apply_card_effect(state, card_to_play)
            self._next_turn(state, steps)

            # بررسی برنده شدن
            if len(current_player.hand) == 0:
                state.status = "finished"
                state.winner = player_id

            await self.save_game_state(state)
            return True

    def _apply_card_effect(self, state: GameState, card: Card) -> int:
        """اعمال اثر کارت بازی‌شده و برگرداندن تعداد گام تا نوبت بعدی"""
        steps = 1

        if card.value == 'reverse':
            state.direction *= -1
            if len(state.players) == 2:
                steps = 2  # در بازی دو نفره، ریورس مثل پرش عمل می‌کند
        elif card.value in ('skip', 'draw2', 'wild4'):
            steps = 2
            draw_count = {'draw2': 2, 'wild4': 4}.get(card.value, 0)
            if draw_count:
                victim = state.players[
                    (state.current_turn_index + state.direction) % len(state.players)
                ]
                victim.hand.extend(self._draw_cards_from_pile(state, draw_count))

        return steps