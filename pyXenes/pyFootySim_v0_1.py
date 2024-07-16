import random
import time
import os
import math

class Player:
    def __init__(self, symbol, x, y, team):
        self.symbol = symbol
        self.x = x
        self.y = y
        self.base_x = x
        self.base_y = y
        self.team = team

class Ball:
    def __init__(self):
        self.x = 40
        self.y = 10
        self.vx = 0
        self.vy = 0

class Team:
    def __init__(self, name, symbol, goal_x):
        self.name = name
        self.score = 0
        self.symbol = symbol
        self.players = [Player(symbol, 0, 0, self) for _ in range(11)]
        self.goal_x = goal_x

class Game:
    def __init__(self):
        self.width = 80
        self.height = 20
        self.home_team = Team("Home", "H", 79)
        self.away_team = Team("Away", "A", 0)
        self.ball = Ball()
        self.time = 0
        self.max_time = 300  # 5 minutes in seconds
        self.possession = random.choice([self.home_team, self.away_team])
        self.ball_holder = None
        self.initialize_positions()

    def initialize_positions(self):
        # Set initial positions for home team
        positions = [(10, 10), (20, 5), (20, 15), (30, 3), (30, 17), (40, 8), (40, 12), (50, 5), (50, 15), (60, 8), (60, 12)]
        for i, pos in enumerate(positions):
            self.home_team.players[i].x = self.home_team.players[i].base_x = pos[0]
            self.home_team.players[i].y = self.home_team.players[i].base_y = pos[1]

        # Set initial positions for away team
        positions = [(70, 10), (60, 5), (60, 15), (50, 3), (50, 17), (40, 8), (40, 12), (30, 5), (30, 15), (20, 8), (20, 12)]
        for i, pos in enumerate(positions):
            self.away_team.players[i].x = self.away_team.players[i].base_x = pos[0]
            self.away_team.players[i].y = self.away_team.players[i].base_y = pos[1]

    def play(self):
        print("Game starts!")
        while self.time < self.max_time:
            self.time += 1
            self.move_players()
            self.handle_ball()
            self.draw_field()
            if self.time % 30 == 0:  # Print score every 30 seconds
                self.print_score()
            time.sleep(0.1)  # Slow down the simulation

        print("Game over!")
        self.print_score()

    def move_players(self):
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                if math.hypot(player.x - self.ball.x, player.y - self.ball.y) < 10:
                    # Move towards the ball if it's close
                    dx = 1 if self.ball.x > player.x else -1 if self.ball.x < player.x else 0
                    dy = 1 if self.ball.y > player.y else -1 if self.ball.y < player.y else 0
                else:
                    # Move randomly within a small radius of base position
                    dx = random.randint(-1, 1)
                    dy = random.randint(-1, 1)

                player.x = max(player.base_x - 5, min(player.base_x + 5, player.x + dx))
                player.y = max(player.base_y - 5, min(player.base_y + 5, player.y + dy))

                # Ensure player stays within field bounds
                player.x = max(0, min(self.width - 1, player.x))
                player.y = max(0, min(self.height - 1, player.y))

    def handle_ball(self):
        if self.ball_holder:
            self.pass_ball()
        else:
            self.move_ball()
            self.check_possession()

    def pass_ball(self):
        team = self.ball_holder.team
        target = self.find_forward_teammate(self.ball_holder)
        if target:
            print(f"{team.name} team passes the ball forward!")
            angle = math.atan2(target.x - self.ball_holder.x, target.y - self.ball_holder.y)
            pass_strength = random.uniform(2, 4)
            self.ball.vx = pass_strength * math.sin(angle)
            self.ball.vy = pass_strength * math.cos(angle)
            self.ball_holder = None
        else:
            self.shoot()

    def find_forward_teammate(self, player):
        teammates = [p for p in player.team.players if 
                     (player.team.goal_x > 40 and p.x > player.x) or 
                     (player.team.goal_x < 40 and p.x < player.x)]
        return random.choice(teammates) if teammates else None

    def shoot(self):
        team = self.ball_holder.team
        print(f"{team.name} team shoots!")
        angle = math.atan2(team.goal_x - self.ball_holder.x, 10 - self.ball_holder.y)
        shot_strength = random.uniform(3, 5)
        self.ball.vx = shot_strength * math.sin(angle)
        self.ball.vy = shot_strength * math.cos(angle)
        self.ball_holder = None

    def move_ball(self):
        self.ball.x += self.ball.vx
        self.ball.y += self.ball.vy
        self.ball.vx *= 0.95
        self.ball.vy *= 0.95

        if self.ball.x <= 0 or self.ball.x >= self.width - 1:
            self.ball.vx *= -0.8
        if self.ball.y <= 0 or self.ball.y >= self.height - 1:
            self.ball.vy *= -0.8

        self.ball.x = max(0, min(self.width - 1, self.ball.x))
        self.ball.y = max(0, min(self.height - 1, self.ball.y))

        # Check for goal
        if self.ball.x <= 1 and 8 <= self.ball.y <= 12:
            self.away_team.score += 1
            print(f"GOAL! {self.away_team.name} team scores!")
            self.reset_positions()
        elif self.ball.x >= self.width - 2 and 8 <= self.ball.y <= 12:
            self.home_team.score += 1
            print(f"GOAL! {self.home_team.name} team scores!")
            self.reset_positions()

    def check_possession(self):
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                if math.hypot(player.x - self.ball.x, player.y - self.ball.y) < 2:
                    if team != self.possession:
                        print(f"{team.name} team gains possession!")
                    self.possession = team
                    self.ball_holder = player
                    self.ball.x, self.ball.y = player.x, player.y
                    self.ball.vx, self.ball.vy = 0, 0
                    return

    def reset_positions(self):
        self.initialize_positions()
        self.ball.x, self.ball.y = 40, 10
        self.ball.vx, self.ball.vy = 0, 0
        self.possession = random.choice([self.home_team, self.away_team])
        self.ball_holder = None

    def draw_field(self):
        field = [[' ' for _ in range(self.width)] for _ in range(self.height)]

        # Draw borders, goals, and center line
        for i in range(self.height):
            field[i][0] = field[i][-1] = '|'
            field[i][self.width // 2] = '|'
        for i in range(self.width):
            field[0][i] = field[-1][i] = '-'
        for i in range(8, 13):
            field[i][0] = field[i][-1] = 'G'

        # Draw players
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                field[int(player.y)][int(player.x)] = player.symbol

        # Draw ball
        field[int(self.ball.y)][int(self.ball.x)] = 'o'

        # Clear screen and draw the field
        os.system('cls' if os.name == 'nt' else 'clear')
        print('\n'.join(''.join(row) for row in field))

    def print_score(self):
        minutes = self.time // 60
        seconds = self.time % 60
        print(f"\nTime: {minutes:02d}:{seconds:02d}")
        print(f"Score: {self.home_team.name} {self.home_team.score} - {self.away_team.score} {self.away_team.name}")
        print(f"Possession: {self.possession.name} team")

if __name__ == "__main__":
    game = Game()
    game.play()