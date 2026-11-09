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

class PlayerView(BaseModel):
    """نمای یک بازیکن از بازیکنان دیگر: بدون دست حریف"""

    player_id: str
    player_name: str = ""
    player_avatar: str = ""
    hand: List[Card] = []
    hand_size: int = 0
    uno_declared: bool = False


class GameView(BaseModel):
    """نمای امن وضعیت بازی برای یک بازیکن مشخص"""

    game_id: str
    players: List[PlayerView]
    current_turn_index: int
    direction: int
    discard_pile: List[Card] = []
    active_color: str
    status: str
    winner: Optional[str] = None
    drawn_card_index: Optional[int] = None
    uno_window: Optional[str] = None
    draw_pile_size: int = 0


class PlayerState(BaseModel):
    player_id: str
    player_name: str = ""
    player_avatar: str = ""
    hand: List[Card] = []
    # True once the player has announced UNO while holding one card.
    uno_declared: bool = False

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
    # Set while the current player has drawn and may still play that card.
    # ``None`` means the player must play from hand or draw.
    drawn_card_index: Optional[int] = None
    # Player who went down to one card and can still be challenged for not
    # announcing UNO. Cleared as soon as the next player acts.
    uno_window: Optional[str] = None

    def for_player(self, player_id: str) -> GameView:
        """Project the state for one viewer: only their own hand, opponents as counts.

        The draw pile is reduced to its size: the order of future draws must never
        leave the server.
        """
        return GameView(
            game_id=self.game_id,
            players=[
                PlayerView(
                    player_id=p.player_id,
                    player_name=p.player_name,
                    player_avatar=p.player_avatar,
                    hand=list(p.hand) if p.player_id == player_id else [],
                    hand_size=len(p.hand),
                    uno_declared=p.uno_declared,
                )
                for p in self.players
            ],
            current_turn_index=self.current_turn_index,
            direction=self.direction,
            discard_pile=list(self.discard_pile),
            active_color=self.active_color,
            status=self.status,
            winner=self.winner,
            drawn_card_index=self.drawn_card_index,
            uno_window=self.uno_window,
            draw_pile_size=len(self.draw_pile),
        )

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

        # The card that opens the game applies its effect immediately.
        start_steps = self._apply_starting_card(game_state, discard_pile[-1])
        if start_steps:
            self._next_turn(game_state, start_steps)

        await self.save_game_state(game_state)
        return game_state

    def _apply_starting_card(self, state: GameState, card: Card) -> int:
        """اعمال اثر کارت شروع بازی و برگرداندن تعداد گام از صندلی صفر"""
        if card.value == 'skip':
            return 1  # صندلی صفر می‌سوزد و بازی از صندلی یک شروع می‌شود

        if card.value == 'reverse':
            state.direction *= -1
            if len(state.players) == 2:
                return 1  # در بازی دو نفره ریورس مثل پرش است
            return 0  # ترتیب برعکس می‌شود ولی همان بازیکن اول شروع می‌کند

        if card.value == 'draw2':
            state.players[0].hand.extend(self._draw_cards_from_pile(state, 2))
            return 1  # دو کارت می‌گیرد و نوبتش می‌سوزد

        return 0

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

    def _card_matches(self, state: GameState, card: Card) -> bool:
        """آیا کارت با رنگ فعال یا کارت روی زمین هم‌خوانی دارد؟"""
        top_card = state.discard_pile[-1]
        return (
            card.color == 'black'
            or card.color == state.active_color
            or card.value == top_card.value
        )

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
        """بازیکن یک کارت از زمین برمی‌دارد (اگر کارت قابل بازی باشد نوبتش می‌ماند)"""
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return False

            # Only one draw per turn: the player is deciding whether to play it.
            if state.drawn_card_index is not None:
                return False

            current_player = state.players[state.current_turn_index]
            if current_player.player_id != player_id:
                return False # نوبت این بازیکن نیست

            state.uno_window = None
            drawn_cards = self._draw_cards_from_pile(state, 1)

            if not drawn_cards:
                # Nothing left in either pile: the turn simply passes.
                self._next_turn(state)
                await self.save_game_state(state)
                return True

            current_player.hand.extend(drawn_cards)
            drawn_index = len(current_player.hand) - 1

            if self._card_matches(state, drawn_cards[0]):
                # Official rule: after drawing a playable card the player may play
                # it (or pass). The turn is kept until play_card / pass_turn.
                state.drawn_card_index = drawn_index
            else:
                self._next_turn(state)

            await self.save_game_state(state)
            return True

    async def say_uno(self, game_id: str, player_id: str) -> bool:
        """اعلام «اونو» توسط بازیکنی که یک کارت دارد"""
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return False

            player = next((p for p in state.players if p.player_id == player_id), None)
            if player is None or len(player.hand) != 1:
                return False

            player.uno_declared = True
            await self.save_game_state(state)
            return True

    async def challenge_uno(self, game_id: str, challenger_id: str) -> Optional[str]:
        """اعتراض به بازیکنی که اونو اعلام نکرده است

        برمی‌گرداند: شناسه بازیکنی که دو کارت جریمه گرفت، یا None در صورت رد اعتراض.
        """
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return None

            offender_id = state.uno_window
            if offender_id is None or offender_id == challenger_id:
                return None

            offender = next((p for p in state.players if p.player_id == offender_id), None)
            if offender is None or len(offender.hand) != 1:
                return None

            # A wrong challenge costs the challenger two cards.
            penalised_player_id = challenger_id if offender.uno_declared else offender_id
            penalised = next(p for p in state.players if p.player_id == penalised_player_id)
            penalised.hand.extend(self._draw_cards_from_pile(state, 2))

            state.uno_window = None
            await self.save_game_state(state)
            return penalised_player_id

    async def pass_turn(self, game_id: str, player_id: str) -> bool:
        """بازیکن پس از برداشتن کارت، از بازی کردن آن صرف‌نظر می‌کند"""
        lock_key = get_game_lock_key(game_id)
        async with self.redis.lock(lock_key, timeout=5):
            state = await self.get_game_state(game_id)
            if not state or state.status != "active":
                return False

            current_player = state.players[state.current_turn_index]
            if current_player.player_id != player_id:
                return False

            if state.drawn_card_index is None:
                return False  # نوبت را فقط بعد از برداشتن کارت می‌توان رد کرد

            state.drawn_card_index = None
            state.uno_window = None
            self._next_turn(state)
            await self.save_game_state(state)
            return True

    async def play_card(
        self,
        game_id: str,
        player_id: str,
        card_index: int,
        chosen_color: Optional[str] = None,
        say_uno: bool = False,
    ) -> bool:
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

            # After drawing, only the drawn card may be played.
            if state.drawn_card_index is not None and card_index != state.drawn_card_index:
                return False

            # بررسی اینکه آیا کارت مجاز است یا خیر
            if not self._card_matches(state, card_to_play):
                return False

            if card_to_play.color == 'black' and not chosen_color:
                return False # برای کارت مشکی باید رنگ انتخاب شود

            # Wild Draw Four is only legal when the player holds no card that
            # matches the active colour (the card being played excluded).
            if card_to_play.value == 'wild4' and self._holds_active_color(current_player, card_index, state.active_color):
                return False
                
            # Any action by the player on turn closes the previous UNO window.
            state.uno_window = None

            # بازی کردن کارت
            current_player.hand.pop(card_index)
            state.drawn_card_index = None
            state.discard_pile.append(card_to_play)
            state.active_color = chosen_color if card_to_play.color == 'black' else card_to_play.color

            # Apply the card effect *before* checking for a win: a Draw Two or Wild
            # Draw Four played as the last card still forces the next player to draw.
            steps = self._apply_card_effect(state, card_to_play)
            self._next_turn(state, steps)

            # UNO announcement: going down to one card opens a challenge window
            # unless the player announced it together with the play.
            if len(current_player.hand) == 1:
                current_player.uno_declared = bool(say_uno)
                state.uno_window = None if current_player.uno_declared else player_id
            elif current_player.hand:
                current_player.uno_declared = False

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