import sys
import os
import pygame
import requests

API_BASE_URL = "http://127.0.0.1:8000"

COLOR_BG = (18, 18, 19)
COLOR_TEXT = (255, 255, 255)
COLOR_EMPTY = (58, 58, 60)
COLOR_CORRECT = (83, 141, 78)
COLOR_PRESENT = (181, 159, 59)
COLOR_ABSENT = (58, 58, 60)
COLOR_HARD = (220, 80, 80)

pygame.init()
GAME_WIDTH = 500
WIDTH, HEIGHT = 700, 650
MAX_TRIES = 6
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame Wordle + FastAPI Client")
font = pygame.font.SysFont("Arial", 36, bold=True)

_font_cache = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("Arial", size, bold=bold)
    return _font_cache[key]


def render_fit(text, max_width, start_size=18, color=COLOR_TEXT, bold=False, min_size=8):
    size = start_size
    while size > min_size and get_font(size, bold).size(text)[0] > max_width:
        size -= 1
    return get_font(size, bold).render(text, True, color)


class WordleGame:
    def __init__(self):
        self.game_id = None
        self.hard_mode = False
        self.stats = {"total_games": 0, "wins": 0, "win_rate": 0.0}
        self.history = []
        self.grid = [["" for _ in range(5)] for _ in range(6)]
        self.colors = [[COLOR_EMPTY for _ in range(5)] for _ in range(6)]
        self.row = 0
        self.col = 0
        self.game_over = False
        self.message = "Press ENTER to submit, R to restart"
        self.start_new_game()

    def start_new_game(self):
        try:
            res = requests.post(
                f"{API_BASE_URL}/api/new-game",
                json={"hard_mode": self.hard_mode},
                timeout=60,
            )
            if res.status_code == 200:
                data = res.json()
                self.game_id = data["game_id"]
                self.stats = data.get("stats", self.stats)
                self.history = []
                self.grid = [["" for _ in range(5)] for _ in range(6)]
                self.colors = [[COLOR_EMPTY for _ in range(5)] for _ in range(6)]
                self.row = 0
                self.col = 0
                self.game_over = False
                self.message = "New game started!"
            else:
                self.message = "Server error starting new game."
        except requests.exceptions.RequestException:
            self.message = "Cannot connect to FastAPI server!"

    def submit_guess(self):
        if self.col < 5:
            self.message = "Not enough letters!"
            return

        guess_word = "".join(self.grid[self.row])
        try:
            payload = {"game_id": self.game_id, "guess": guess_word}
            res = requests.post(f"{API_BASE_URL}/api/guess", json=payload, timeout=60)

            if res.status_code == 200:
                data = res.json()
                feedback = data["feedback"]

                for i in range(5):
                    if feedback[i] == "correct":
                        self.colors[self.row][i] = COLOR_CORRECT
                    elif feedback[i] == "present":
                        self.colors[self.row][i] = COLOR_PRESENT
                    else:
                        self.colors[self.row][i] = COLOR_ABSENT

                self.history.append(guess_word)
                self.stats = data.get("stats", self.stats)

                if data["is_correct"]:
                    self.message = "Congratulations! You won! Press R to restart."
                    self.game_over = True
                else:
                    self.row += 1
                    self.col = 0
                    if self.row == MAX_TRIES:
                        answer = data.get("target_word") or "?"
                        self.message = f"Game Over! The word was {answer}. Press R to restart."
                        self.game_over = True
                    else:
                        self.message = f"Keep guessing! ({MAX_TRIES - self.row} tries left)"
            else:
                try:
                    detail = res.json().get("detail")
                except ValueError:
                    detail = None
                if not isinstance(detail, str):
                    detail = "Error processing guess"

                if res.status_code == 400 and detail == "Word not in dictionary":
                    self.message = "Not in word list!"
                else:
                    self.message = detail
        except requests.exceptions.RequestException:
            self.message = "Network error during guess!"

    def hotkeys_active(self):
        return self.game_over or (self.row == 0 and self.col == 0)

    def handle_keydown(self, event):
        if event.key == pygame.K_r and self.hotkeys_active():
            self.start_new_game()
            return

        if event.key == pygame.K_h and self.hotkeys_active():
            self.hard_mode = not self.hard_mode
            self.start_new_game()
            return

        if self.game_over:
            return

        if event.key == pygame.K_BACKSPACE:
            if self.col > 0:
                self.col -= 1
                self.grid[self.row][self.col] = ""
        elif event.key == pygame.K_RETURN:
            self.submit_guess()
        elif event.unicode.isalpha() and len(event.unicode) == 1:
            if self.col < 5:
                self.grid[self.row][self.col] = event.unicode.upper()
                self.col += 1

    def draw_sidebar(self, surface):
        pygame.draw.line(surface, (80, 80, 80), (GAME_WIDTH, 0), (GAME_WIDTH, HEIGHT), 2)
        pad = 6
        max_w = WIDTH - GAME_WIDTH - 2 * pad

        mode_text = "Mode: HARD" if self.hard_mode else "Mode: Normal"
        mode_color = COLOR_HARD if self.hard_mode else COLOR_TEXT
        mode_surf = render_fit(mode_text, max_w, 20, mode_color, bold=True)
        surface.blit(mode_surf, mode_surf.get_rect(topright=(WIDTH - pad, 10)))

        st = self.stats
        stats_text = f"Total: {st['total_games']} | Wins: {st['wins']} | Win Rate: {st['win_rate']}%"
        stats_surf = render_fit(stats_text, max_w, 16)
        surface.blit(stats_surf, (GAME_WIDTH + pad, 48))

        title = render_fit("History", max_w, 22, bold=True)
        surface.blit(title, (GAME_WIDTH + pad, 95))
        for idx, word in enumerate(self.history):
            line = get_font(24, True).render(f"{idx + 1}. {word}", True, COLOR_TEXT)
            surface.blit(line, (GAME_WIDTH + pad + 4, 135 + idx * 36))

    def draw(self, surface):
        surface.fill(COLOR_BG)
        margin_x, margin_y = 75, 50
        box_size = 60
        gap = 10

        for r in range(6):
            for c in range(5):
                x = margin_x + c * (box_size + gap)
                y = margin_y + r * (box_size + gap)
                rect = pygame.Rect(x, y, box_size, box_size)

                pygame.draw.rect(surface, self.colors[r][c], rect, border_radius=4)
                if self.colors[r][c] == COLOR_EMPTY:
                    pygame.draw.rect(surface, (80, 80, 80), rect, width=2, border_radius=4)

                char = self.grid[r][c]
                if char:
                    text_surface = font.render(char, True, COLOR_TEXT)
                    text_rect = text_surface.get_rect(center=rect.center)
                    surface.blit(text_surface, text_rect)

        msg_surface = render_fit(self.message, GAME_WIDTH - 20, 18)
        msg_rect = msg_surface.get_rect(center=(GAME_WIDTH // 2, HEIGHT - 40))
        surface.blit(msg_surface, msg_rect)

        self.draw_sidebar(surface)


def main():
    clock = pygame.time.Clock()
    game = WordleGame()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                game.handle_keydown(event)

        game.draw(screen)
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    main()