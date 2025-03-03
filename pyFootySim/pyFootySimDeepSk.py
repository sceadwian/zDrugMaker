import random
import time
import os
import math

# Constants
FIELD_WIDTH = 80
FIELD_HEIGHT = 20
GOAL_WIDTH = 3
GAME_DURATION = 300  # 5 minutes in seconds
UPDATE_DELAY = 0.1  # Delay between updates in seconds
BALL_DECELERATION = 0.95  # Simulate friction
BALL_BOUNCE_FACTOR = 0.8  # Simulate bounce

class Player:
    def __init__(self, symbol, base_position, team):
        self.symbol = symbol
        self.base_position = base_position
        self.position = list(base_position)
        self.team = team
        self.has_ball = False

    def move_toward(self, target):
        """Move the player toward a target position."""
        dx = target[0] - self.position[0]
        dy = target[1] - self.position[1]
        distance = math.hypot(dx, dy)

        if distance > 0:
            self.position[0] += dx / distance
            self.position[1] += dy / distance

    def move_randomly(self):
        """Move the player randomly within a small radius of their base position."""
        self.position[0] += random.uniform(-1, 1)
        self.position[1] += random.uniform(-1, 1)
        self.position[0] = max(0, min(FIELD_WIDTH - 1, self.position[0]))
        self.position[1] = max(0, min(FIELD_HEIGHT - 1, self.position[1]))

    def decide_action(self, ball, teammates):
        """Decide whether to pass, shoot, or move."""
        if self.has_ball:
            # Check if shooting is possible
            if self.team.is_in_shooting_position(self.position):
                self.shoot(ball)
            else:
                # Find a teammate in a better position
                best_teammate = None
                best_distance = float('inf')

                for teammate in teammates:
                    if teammate != self and self.team.is_forward(teammate.position, self.position):
                        distance = math.hypot(teammate.position[0] - self.position[0],
                                              teammate.position[1] - self.position[1])
                        if distance < best_distance:
                            best_teammate = teammate
                            best_distance = distance

                if best_teammate:
                    self.pass_ball(ball, best_teammate)
                else:
                    self.move_toward(self.team.goal_position)
        else:
            if ball.position:
                self.move_toward(ball.position)
            else:
                self.move_randomly()

    def pass_ball(self, ball, teammate):
        """Pass the ball to a teammate."""
        ball.velocity = [teammate.position[0] - self.position[0],
                         teammate.position[1] - self.position[1]]
        ball.velocity = [v * 2 for v in ball.velocity]  # Increase speed for pass
        self.has_ball = False
        teammate.has_ball = True

    def shoot(self, ball):
        """Shoot the ball toward the goal."""
        ball.velocity = [self.team.goal_position[0] - self.position[0],
                         self.team.goal_position[1] - self.position[1]]
        ball.velocity = [v * 3 for v in ball.velocity]  # Increase speed for shot
        self.has_ball = False


class Ball:
    def __init__(self):
        self.position = [FIELD_WIDTH // 2, FIELD_HEIGHT // 2]
        self.velocity = [0, 0]

    def update(self):
        """Update the ball's position based on velocity and deceleration."""
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        self.velocity[0] *= BALL_DECELERATION
        self.velocity[1] *= BALL_DECELERATION

        # Bounce off field boundaries
        if self.position[0] < 0 or self.position[0] >= FIELD_WIDTH:
            self.position[0] = max(0, min(FIELD_WIDTH - 1, self.position[0]))
            self.velocity[0] *= -BALL_BOUNCE_FACTOR
        if self.position[1] < 0 or self.position[1] >= FIELD_HEIGHT:
            self.position[1] = max(0, min(FIELD_HEIGHT - 1, self.position[1]))
            self.velocity[1] *= -BALL_BOUNCE_FACTOR


class Team:
    def __init__(self, name, symbol, goal_position):
        self.name = name
        self.symbol = symbol
        self.goal_position = goal_position
        self.score = 0
        self.players = [Player(symbol, (random.randint(0, FIELD_WIDTH - 1), random.randint(0, FIELD_HEIGHT - 1)), self)
                        for _ in range(11)]

    def is_in_shooting_position(self, position):
        """Check if a position is within shooting range of the goal."""
        return abs(position[0] - self.goal_position[0]) < 10 and abs(position[1] - self.goal_position[1]) < 5

    def is_forward(self, position1, position2):
        """Check if position1 is further forward than position2."""
        return abs(position1[0] - self.goal_position[0]) < abs(position2[0] - self.goal_position[0])


class Game:
    def __init__(self):
        self.field_width = FIELD_WIDTH
        self.field_height = FIELD_HEIGHT
        self.home_team = Team("Home", "H", (0, FIELD_HEIGHT // 2))
        self.away_team = Team("Away", "A", (FIELD_WIDTH - 1, FIELD_HEIGHT // 2))
        self.ball = Ball()
        self.time_remaining = GAME_DURATION
        self.current_possession = None

    def update(self):
        """Update the game state."""
        self.time_remaining -= 1

        # Update ball position
        self.ball.update()

        # Check for ball possession
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                if math.hypot(player.position[0] - self.ball.position[0],
                              player.position[1] - self.ball.position[1]) < 1:
                    player.has_ball = True
                    self.current_possession = team
                    self.ball.velocity = [0, 0]
                else:
                    player.has_ball = False

        # Update player actions
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                player.decide_action(self.ball, team.players)

        # Check for goals
        if self.ball.position[0] < 0:
            self.away_team.score += 1
            self.reset_positions()
        elif self.ball.position[0] >= FIELD_WIDTH:
            self.home_team.score += 1
            self.reset_positions()

    def reset_positions(self):
        """Reset player and ball positions after a goal."""
        self.ball.position = [FIELD_WIDTH // 2, FIELD_HEIGHT // 2]
        self.ball.velocity = [0, 0]
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                player.position = list(player.base_position)

    def render(self):
        """Render the field, players, and ball."""
        os.system('cls' if os.name == 'nt' else 'clear')

        # Initialize field grid
        field = [[' ' for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]

        # Draw borders
        for y in range(FIELD_HEIGHT):
            field[y][0] = '|'
            field[y][-1] = '|'
        for x in range(FIELD_WIDTH):
            field[0][x] = '-'
            field[-1][x] = '-'

        # Draw center line
        for y in range(FIELD_HEIGHT):
            field[y][FIELD_WIDTH // 2] = '|'

        # Draw goals
        for y in range(FIELD_HEIGHT // 2 - GOAL_WIDTH, FIELD_HEIGHT // 2 + GOAL_WIDTH):
            field[y][0] = 'G'
            field[y][-1] = 'G'

        # Draw players
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                x, y = int(player.position[0]), int(player.position[1])
                if 0 <= x < FIELD_WIDTH and 0 <= y < FIELD_HEIGHT:
                    field[y][x] = player.symbol

        # Draw ball
        x, y = int(self.ball.position[0]), int(self.ball.position[1])
        if 0 <= x < FIELD_WIDTH and 0 <= y < FIELD_HEIGHT:
            field[y][x] = 'o'

        # Print field
        for row in field:
            print(''.join(row))

        # Print status
        print(f"Time Remaining: {self.time_remaining} | Home: {self.home_team.score} - Away: {self.away_team.score}")
        print(f"Possession: {self.current_possession.name if self.current_possession else 'None'}")

    def run(self):
        """Run the game loop."""
        while self.time_remaining > 0:
            self.update()
            self.render()
            time.sleep(UPDATE_DELAY)

        print("Game Over!")
        print(f"Final Score: Home {self.home_team.score} - Away {self.away_team.score}")


if __name__ == "__main__":
    game = Game()
    game.run()