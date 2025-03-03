import random
import time
import os
import math

# Constants (unchanged)
FIELD_WIDTH = 80
FIELD_HEIGHT = 20
GOAL_WIDTH = 3
GAME_DURATION = 300
UPDATE_DELAY = 0.1
BALL_DECELERATION = 0.95
BALL_BOUNCE_FACTOR = 0.8

class Ball:
    """Enhanced ball physics with friction and bounce."""
    def __init__(self, x, y):
        self.position = [x, y]
        self.velocity = [0, 0]

    def update(self, game):
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        self.velocity[0] *= BALL_DECELERATION
        self.velocity[1] *= BALL_DECELERATION

        if self.position[0] < 0 or self.position[0] >= FIELD_WIDTH:
            self.position[0] = max(0, min(FIELD_WIDTH - 1, self.position[0]))
            self.velocity[0] *= -BALL_BOUNCE_FACTOR
        if self.position[1] < 0 or self.position[1] >= FIELD_HEIGHT:
            self.position[1] = max(0, min(FIELD_HEIGHT - 1, self.position[1]))
            self.velocity[1] *= -BALL_BOUNCE_FACTOR

class Player:
    """Player with role-based movement and positional discipline."""
    def __init__(self, symbol, base_position, team):
        self.symbol = symbol
        self.base_position = list(base_position)
        self.position = list(base_position)
        self.team = team
        self.has_ball = False
        # Assign role based on x-position: defenders near own goal, attackers near opponent goal
        if self.team.goal_position[0] == FIELD_WIDTH - 1:  # Home team (right goal)
            if base_position[0] < FIELD_WIDTH * 0.33:
                self.role = "defender"
            elif base_position[0] < FIELD_WIDTH * 0.66:
                self.role = "midfielder"
            else:
                self.role = "attacker"
        else:  # Away team (left goal)
            if base_position[0] > FIELD_WIDTH * 0.66:
                self.role = "defender"
            elif base_position[0] > FIELD_WIDTH * 0.33:
                self.role = "midfielder"
            else:
                self.role = "attacker"

    def move_toward(self, target):
        dx = target[0] - self.position[0]
        dy = target[1] - self.position[1]
        distance = math.hypot(dx, dy)
        if distance > 0:
            step = 1.0  # Reduced step size for smoother movement
            self.position[0] += (dx / distance) * step
            self.position[1] += (dy / distance) * step
            # Keep players within bounds
            self.position[0] = max(1, min(FIELD_WIDTH - 2, self.position[0]))
            self.position[1] = max(1, min(FIELD_HEIGHT - 2, self.position[1]))

    def move_randomly(self):
        self.position[0] += random.uniform(-0.5, 0.5)  # Smaller random steps
        self.position[1] += random.uniform(-0.5, 0.5)
        self.position[0] = max(1, min(FIELD_WIDTH - 2, self.position[0]))
        self.position[1] = max(1, min(FIELD_HEIGHT - 2, self.position[1]))

    def distance_to(self, target):
        return math.hypot(target[0] - self.position[0], target[1] - self.position[1])

    def decide_action(self, ball, teammates, opponents):
        ball_distance = self.distance_to(ball.position)
        # Define role-specific distance thresholds for chasing the ball
        chase_distance = {"defender": 15, "midfielder": 20, "attacker": 25}

        if self.has_ball:
            if self.team.is_in_shooting_range(self.position):
                self.shoot(ball)
            else:
                best_teammate = None
                for mate in teammates:
                    if mate != self and self.team.is_forward(mate.position, self.position):
                        best_teammate = mate
                        break
                if best_teammate:
                    self.pass_ball(ball, best_teammate)
                else:
                    self.move_toward(self.team.goal_position)
        else:
            # Check if an opponent has the ball
            opp_with_ball = next((opp for opp in opponents if opp.has_ball), None)
            if opp_with_ball:
                opp_distance = self.distance_to(opp_with_ball.position)
                # Defenders and midfielders try to intercept if opponent is close
                if (self.role in ["defender", "midfielder"] and opp_distance < chase_distance[self.role]):
                    self.move_toward(opp_with_ball.position)
                elif self.role == "attacker" and opp_distance < 10:  # Attackers defend less
                    self.move_toward(opp_with_ball.position)
                else:
                    # Return to base position if not engaging
                    self.move_toward(self.base_position)
            else:
                # If ball is free, move toward it only if within role-specific range
                if ball_distance < chase_distance[self.role]:
                    self.move_toward(ball.position)
                else:
                    # Otherwise, drift toward base position with slight randomness
                    if self.distance_to(self.base_position) > 5:  # Allow some flexibility
                        self.move_toward(self.base_position)
                    else:
                        self.move_randomly()  # Small random movement near base

    def pass_ball(self, ball, teammate):
        ball.velocity = [
            (teammate.position[0] - self.position[0]) * 0.5,
            (teammate.position[1] - self.position[1]) * 0.5
        ]
        self.has_ball = False
        teammate.has_ball = True

    def shoot(self, ball):
        ball.velocity = [
            (self.team.goal_position[0] - self.position[0]) * 0.3,
            (self.team.goal_position[1] - self.position[1]) * 0.3 + random.uniform(-1, 1)
        ]
        self.has_ball = False

class Team:
    """Team with fixed formation; positions are mirrored depending on which goal to attack."""
    def __init__(self, name, symbol, goal_position, formation=None):
        self.name = name
        self.symbol = symbol
        self.goal_position = goal_position
        self.score = 0
        self.players = self.create_players(formation)

    def create_players(self, formation):
        if formation is None:
            formation = [
                (10, 10), (20, 5), (20, 15), (30, 3), (30, 7),
                (30, 13), (30, 17), (45, 5), (45, 15), (60, 8), (60, 12)
            ]
        if self.goal_position[0] == 0:
            formation = [(FIELD_WIDTH - x, y) for x, y in formation]
        return [Player(self.symbol, pos, self) for pos in formation]

    def is_in_shooting_range(self, position):
        return abs(position[0] - self.goal_position[0]) < 10 and abs(position[1] - self.goal_position[1]) < 5

    def is_forward(self, pos1, pos2):
        if self.goal_position[0] == FIELD_WIDTH - 1:
            return pos1[0] > pos2[0]
        else:
            return pos1[0] < pos2[0]

class Game:
    """Manages the soccer simulation, scoring, and reset after goals."""
    def __init__(self):
        self.field_width = FIELD_WIDTH
        self.field_height = FIELD_HEIGHT
        self.home_team = Team("Home", "H", (FIELD_WIDTH - 1, FIELD_HEIGHT // 2))
        self.away_team = Team("Away", "A", (0, FIELD_HEIGHT // 2))
        self.ball = Ball(FIELD_WIDTH // 2, FIELD_HEIGHT // 2)
        self.time = 0
        random.choice(self.home_team.players + self.away_team.players).has_ball = True

    def update(self):
        self.time += 1
        self.ball.update(self)

        for team in (self.home_team, self.away_team):
            for player in team.players:
                distance = math.hypot(player.position[0] - self.ball.position[0],
                                      player.position[1] - self.ball.position[1])
                if distance < 1:
                    player.has_ball = True
                    self.ball.velocity = [0, 0]

        for team in (self.home_team, self.away_team):
            opponents = self.away_team.players if team == self.home_team else self.home_team.players
            for player in team.players:
                player.decide_action(self.ball, team.players, opponents)

        for team in (self.home_team, self.away_team):
            opponents = self.away_team.players if team == self.home_team else self.home_team.players
            for player in team.players:
                if player.has_ball:
                    for opp in opponents:
                        if math.hypot(player.position[0] - opp.position[0],
                                      player.position[1] - opp.position[1]) < 2:
                            if random.random() < 0.3:
                                player.has_ball = False
                                opp.has_ball = True
                                self.ball.velocity = [0, 0]
                                break

        self.check_goal()

    def check_goal(self):
        goal_zone_min = (FIELD_HEIGHT // 2) - GOAL_WIDTH
        goal_zone_max = (FIELD_HEIGHT // 2) + GOAL_WIDTH
        x, y = self.ball.position
        if x < 1 and goal_zone_min <= y <= goal_zone_max:
            self.away_team.score += 1
            print("GOAL! Away team scores!")
            self.reset_positions()
        elif x > FIELD_WIDTH - 2 and goal_zone_min <= y <= goal_zone_max:
            self.home_team.score += 1
            print("GOAL! Home team scores!")
            self.reset_positions()

    def reset_positions(self):
        self.ball.position = [FIELD_WIDTH // 2, FIELD_HEIGHT // 2]
        self.ball.velocity = [0, 0]
        for team in (self.home_team, self.away_team):
            for player in team.players:
                player.position = list(player.base_position)
                player.has_ball = False
        random.choice(self.home_team.players + self.away_team.players).has_ball = True

    def render(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        field = [[' ' for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
        for x in range(FIELD_WIDTH):
            field[0][x] = '-'
            field[FIELD_HEIGHT - 1][x] = '-'
        for y in range(FIELD_HEIGHT):
            field[y][0] = '|'
            field[y][FIELD_WIDTH - 1] = '|'
        for y in range(FIELD_HEIGHT):
            field[y][FIELD_WIDTH // 2] = '|'
        for y in range((FIELD_HEIGHT // 2) - GOAL_WIDTH, (FIELD_HEIGHT // 2) + GOAL_WIDTH):
            field[y][0] = 'G'
            field[y][FIELD_WIDTH - 1] = 'G'
        for team in (self.home_team, self.away_team):
            for player in team.players:
                x = int(player.position[0])
                y = int(player.position[1])
                if 0 <= x < FIELD_WIDTH and 0 <= y < FIELD_HEIGHT:
                    field[y][x] = player.symbol
        bx, by = int(self.ball.position[0]), int(self.ball.position[1])
        if 0 <= bx < FIELD_WIDTH and 0 <= by < FIELD_HEIGHT:
            field[by][bx] = 'o'
        for row in field:
            print(''.join(row))
        possession = None
        for team in (self.home_team, self.away_team):
            if any(p.has_ball for p in team.players):
                possession = team.name
                break
        print(f"Time: {self.time} | Score: Home {self.home_team.score} - Away {self.away_team.score} | Possession: {possession or 'None'}")

    def run(self):
        while self.time < GAME_DURATION:
            self.update()
            self.render()
            time.sleep(UPDATE_DELAY)
        print(f"Final Score: Home {self.home_team.score} - Away {self.away_team.score}")

def main():
    game = Game()
    game.run()

if __name__ == "__main__":
    main()