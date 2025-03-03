import random
import time
import os
import math

class Player:
    """Represents an individual soccer player"""
    def __init__(self, symbol, base_x, base_y, team):
        self.symbol = symbol
        self.x = base_x
        self.y = base_y
        self.base_x = base_x
        self.base_y = base_y
        self.team = team
        self.has_ball = False

    def move(self, ball):
        """Handle player movement based on game state"""
        if self.has_ball:
            # Move toward opponent's goal or pass
            target_x = self.team.goal_x
            self.x += 1 if target_x > self.x else -1
            if abs(self.x - target_x) < 10 and random.random() < 0.2:
                self.shoot(ball)
            elif random.random() < 0.3:
                self.pass_ball(ball)
        elif abs(self.x - ball.x) < 5 and abs(self.y - ball.y) < 3:
            # Move toward ball if nearby
            self.x += 1 if ball.x > self.x else -1
            self.y += 1 if ball.y > self.y else -1
            if abs(self.x - ball.x) < 2 and abs(self.y - ball.y) < 1:
                self.has_ball = True
                ball.vx, ball.vy = 0, 0
        else:
            # Wander near base position
            self.x += random.randint(-1, 1)
            self.y += random.randint(-1, 1)
            self.x = max(1, min(self.team.game.width - 2, self.x))
            self.y = max(1, min(self.team.game.height - 2, self.y))

    def pass_ball(self, ball):
        """Pass ball to a teammate closer to goal"""
        teammates = [p for p in self.team.players if p != self]
        forward_players = [p for p in teammates if abs(p.x - self.team.goal_x) < abs(self.x - self.team.goal_x)]
        if forward_players:
            target = random.choice(forward_players)
            self.has_ball = False
            ball.x, ball.y = self.x, self.y
            ball.vx = (target.x - self.x) * 0.5
            ball.vy = (target.y - self.y) * 0.5

    def shoot(self, ball):
        """Shoot toward opponent's goal"""
        self.has_ball = False
        ball.x, ball.y = self.x, self.y
        ball.vx = (self.team.goal_x - self.x) * 0.3
        ball.vy = random.uniform(-1, 1)

class Ball:
    """Represents the soccer ball with position and velocity"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0

    def update(self, game):
        """Update ball position with physics"""
        if not any(p.has_ball for team in (game.home_team, game.away_team) for p in team.players):
            self.x += self.vx
            self.y += self.vy
            # Friction
            self.vx *= 0.95
            self.vy *= 0.95
            # Bounce off boundaries
            if self.x <= 1 or self.x >= game.width - 2:
                self.vx = -self.vx
            if self.y <= 1 or self.y >= game.height - 2:
                self.vy = -self.vy
            self.x = max(1, min(game.width - 2, self.x))
            self.y = max(1, min(game.height - 2, self.y))

class Team:
    """Represents a soccer team with players and goal"""
    def __init__(self, name, symbol, goal_x, game):
        self.name = name
        self.symbol = symbol
        self.score = 0
        self.goal_x = goal_x
        self.game = game
        self.players = self.create_players()

    def create_players(self):
        """Initialize 11 players in a 4-4-2 formation"""
        positions = [
            (10, 10), (20, 5), (20, 15), (30, 3), (30, 7),  # Defenders
            (30, 13), (30, 17), (45, 5), (45, 15),          # Midfielders
            (60, 8), (60, 12)                                # Forwards
        ]
        if self.goal_x > 40:  # Away team, mirror positions
            positions = [(80 - x, y) for x, y in positions]
        return [Player(self.symbol, x, y, self) for x, y in positions]

class Game:
    """Manages the soccer simulation"""
    def __init__(self, width=80, height=20, duration=300):
        self.width = width
        self.height = height
        self.time = 0
        self.duration = duration
        self.home_team = Team("Home", "H", 0, self)
        self.away_team = Team("Away", "A", width - 1, self)
        self.ball = Ball(width // 2, height // 2)
        # Random initial possession
        random.choice(self.home_team.players + self.away_team.players).has_ball = True

    def update(self):
        """Update game state"""
        self.time += 1
        self.ball.update(self)
        for team in (self.home_team, self.away_team):
            for player in team.players:
                player.move(self.ball)
        self.check_goal()

    def check_goal(self):
        """Check if a goal is scored and reset if so"""
        if self.ball.y >= 8 and self.ball.y <= 12:  # Goal height
            if self.ball.x <= 1:
                self.away_team.score += 1
                print(f"GOAL! {self.away_team.name} scores!")
                self.reset()
            elif self.ball.x >= self.width - 2:
                self.home_team.score += 1
                print(f"GOAL! {self.home_team.name} scores!")
                self.reset()

    def reset(self):
        """Reset positions after a goal"""
        self.ball.x, self.ball.y = self.width // 2, self.height // 2
        self.ball.vx, self.ball.vy = 0, 0
        for team in (self.home_team, self.away_team):
            for player in team.players:
                player.x, player.y = player.base_x, player.base_y
                player.has_ball = False
        random.choice(self.home_team.players + self.away_team.players).has_ball = True

    def render(self):
        """Render the game field"""
        os.system('cls' if os.name == 'nt' else 'clear')
        field = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        # Borders and center line
        for x in range(self.width):
            field[0][x] = field[self.height - 1][x] = '-'
        for y in range(self.height):
            field[y][0] = field[y][self.width - 1] = '|'
        for y in range(self.height):
            field[y][self.width // 2] = '|'
        # Goals
        for y in range(8, 13):
            field[y][0] = field[y][self.width - 1] = 'G'
        # Players and ball
        for team in (self.home_team, self.away_team):
            for player in team.players:
                field[int(player.y)][int(player.x)] = player.symbol
        field[int(self.ball.y)][int(self.ball.x)] = 'o'
        # Print field
        for row in field:
            print(''.join(row))
        # Status
        possession = "Home" if any(p.has_ball for p in self.home_team.players) else "Away" if any(p.has_ball for p in self.away_team.players) else "Loose"
        print(f"Time: {self.time}s | Score: {self.home_team.name} {self.home_team.score} - {self.away_team.score} {self.away_team.name} | Possession: {possession}")

def main():
    """Run the soccer simulation"""
    game = Game()
    while game.time < game.duration:
        game.update()
        game.render()
        time.sleep(0.1)
    print(f"Final Score: {game.home_team.name} {game.home_team.score} - {game.away_team.score} {game.away_team.name}")

if __name__ == "__main__":
    main()