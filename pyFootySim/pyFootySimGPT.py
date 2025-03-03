import os
import time
import random
import math

# -------------------------------
# Utility Function
# -------------------------------
def distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points."""
    return math.hypot(x2 - x1, y2 - y1)

# -------------------------------
# Ball Class
# -------------------------------
class Ball:
    """
    Represents the soccer ball.
    
    Attributes:
      x, y: Current position.
      vx, vy: Velocity components.
      possessed_by: Reference to the Player that currently has possession (if any).
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.possessed_by = None

    def update(self, field_width, field_height):
        """
        Update the ball's position based on its velocity.
        Apply friction and bounce off the field boundaries.
        """
        # If the ball is possessed, tie its position to the player.
        if self.possessed_by is not None:
            self.x = self.possessed_by.x
            self.y = self.possessed_by.y
            return

        # Update position based on velocity.
        self.x += self.vx
        self.y += self.vy

        # Apply friction to gradually decelerate the ball.
        friction = 0.95
        self.vx *= friction
        self.vy *= friction

        # If velocity is minimal, stop the ball.
        if abs(self.vx) < 0.1:
            self.vx = 0
        if abs(self.vy) < 0.1:
            self.vy = 0

        # Bounce off the horizontal boundaries.
        if self.x < 1:
            self.x = 1
            self.vx = -self.vx
        if self.x > field_width - 2:
            self.x = field_width - 2
            self.vx = -self.vx

        # Bounce off the vertical boundaries.
        if self.y < 1:
            self.y = 1
            self.vy = -self.vy
        if self.y > field_height - 2:
            self.y = field_height - 2
            self.vy = -self.vy

# -------------------------------
# Player Class
# -------------------------------
class Player:
    """
    Represents an individual soccer player.
    
    Attributes:
      symbol: Unique symbol (e.g., "H" for Home or "A" for Away).
      x, y: Current position.
      base_x, base_y: Base (or home) position in the formation.
      team: Reference to the Team instance the player belongs to.
      has_ball: Boolean flag indicating possession.
    """
    def __init__(self, symbol, base_position, team):
        self.symbol = symbol
        self.base_x, self.base_y = base_position
        self.x, self.y = base_position
        self.team = team
        self.has_ball = False

    def distance_to(self, target_x, target_y):
        """Return the distance from the player to a target point."""
        return distance(self.x, self.y, target_x, target_y)

    def move_towards(self, target_x, target_y, field_width, field_height):
        """
        Move one step towards the target position while keeping within field bounds.
        """
        dx = target_x - self.x
        dy = target_y - self.y
        # Normalize movement to one step in each axis.
        if dx != 0:
            dx = dx / abs(dx)
        if dy != 0:
            dy = dy / abs(dy)
        new_x = self.x + dx
        new_y = self.y + dy
        # Clamp to the field's play area (leaving space for borders).
        self.x = max(1, min(new_x, field_width - 2))
        self.y = max(1, min(new_y, field_height - 2))

    def update(self, ball, field_width, field_height):
        """
        Update the player's behavior:
          - If in possession: decide to pass, shoot, or dribble.
          - If not in possession: move toward the ball if nearby or wander around the base.
        """
        if self.has_ball:
            # When possessing the ball, decide whether to shoot or pass.
            # For Home team, attacking goal is at the right side; for Away, it's on the left.
            # If the player is near the opponent’s goal, shoot.
            if (self.team.name == "Home" and self.x > field_width * 0.75) or \
               (self.team.name == "Away" and self.x < field_width * 0.25):
                # Shoot: set a high velocity toward the goal.
                direction = 1 if self.team.name == "Home" else -1
                ball.vx = direction * 2.0
                # Aim vertically toward the middle of the field.
                if self.y < field_height // 2:
                    ball.vy = 1.0
                elif self.y > field_height // 2:
                    ball.vy = -1.0
                else:
                    ball.vy = 0
                # Release the ball.
                self.has_ball = False
                ball.possessed_by = None
            else:
                # Look for a teammate further forward (closer to the opponent’s goal).
                potential = None
                for teammate in self.team.players:
                    if teammate == self:
                        continue
                    if self.team.name == "Home" and teammate.x > self.x:
                        potential = teammate
                        break
                    elif self.team.name == "Away" and teammate.x < self.x:
                        potential = teammate
                        break
                if potential:
                    # Pass: set ball velocity toward the teammate.
                    dx = potential.x - self.x
                    dy = potential.y - self.y
                    dist = math.hypot(dx, dy)
                    if dist == 0:
                        dist = 1
                    ball.vx = (dx / dist) * 2.0
                    ball.vy = (dy / dist) * 2.0
                    self.has_ball = False
                    ball.possessed_by = None
                else:
                    # If no forward pass is available, dribble toward the goal.
                    self.move_towards(self.team.goal_x, self.y, field_width, field_height)
                    ball.x = self.x
                    ball.y = self.y
            return

        # If not in possession and ball is close, move toward it.
        if self.distance_to(ball.x, ball.y) < 2:
            self.move_towards(ball.x, ball.y, field_width, field_height)
        else:
            # Wander around near the base position.
            if math.hypot(self.x - self.base_x, self.y - self.base_y) > 3:
                self.move_towards(self.base_x, self.base_y, field_width, field_height)
            else:
                # Random small movement around the base.
                move_options = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
                dx, dy = random.choice(move_options)
                new_x = self.x + dx
                new_y = self.y + dy
                if abs(new_x - self.base_x) <= 3 and abs(new_y - self.base_y) <= 3:
                    self.x = max(1, min(new_x, field_width - 2))
                    self.y = max(1, min(new_y, field_height - 2))

# -------------------------------
# Team Class
# -------------------------------
class Team:
    """
    Represents a soccer team.
    
    Attributes:
      name: "Home" or "Away".
      symbol: Single-character symbol for players.
      goal_x: The x-coordinate of the attacking goal.
      score: Current team score.
      players: List of 11 Player instances arranged in a formation.
    """
    def __init__(self, name, symbol, goal_x, field_width, field_height):
        self.name = name
        self.symbol = symbol
        self.goal_x = goal_x  # Attacking goal location (x-coordinate)
        self.score = 0
        self.players = []
        self.field_width = field_width
        self.field_height = field_height
        self.create_players()

    def create_players(self):
        """
        Initialize 11 players and assign them base positions.
        For the Home team, base positions are in the left half.
        For the Away team, positions are in the right half.
        """
        for i in range(11):
            if self.name == "Home":
                base_x = random.randint(3, self.field_width // 2 - 2)
            else:
                base_x = random.randint(self.field_width // 2 + 1, self.field_width - 4)
            # Distribute players evenly along the vertical axis.
            base_y = 1 + i * (self.field_height - 2) // 10
            player = Player(self.symbol, (base_x, base_y), self)
            self.players.append(player)

    def reset_positions(self):
        """Reset all players to their base positions and clear possession."""
        for player in self.players:
            player.x, player.y = player.base_x, player.base_y
            player.has_ball = False

# -------------------------------
# Game Class
# -------------------------------
class Game:
    """
    Manages the overall simulation and game loop.
    
    Attributes:
      field_width, field_height: Dimensions of the field.
      home_team, away_team: Instances of Team.
      ball: The Ball instance.
      game_duration: Total game time in seconds.
      current_time: Elapsed time.
    """
    def __init__(self):
        self.field_width = 80
        self.field_height = 20
        self.game_duration = 300  # 5 minutes match (300 seconds)
        self.current_time = 0
        # Home team attacks right (goal near field_width - 2) while Away attacks left (goal at 1).
        self.home_team = Team("Home", "H", self.field_width - 2, self.field_width, self.field_height)
        self.away_team = Team("Away", "A", 1, self.field_width, self.field_height)
        self.ball = Ball(self.field_width // 2, self.field_height // 2)
        self.assign_initial_possession()

    def assign_initial_possession(self):
        """Randomly assign initial ball possession to a player from one of the teams."""
        team = random.choice([self.home_team, self.away_team])
        player = random.choice(team.players)
        player.has_ball = True
        self.ball.possessed_by = player
        self.ball.x = player.x
        self.ball.y = player.y

    def reset_positions(self):
        """
        Reset player and ball positions after a goal.
        Reassign ball possession randomly.
        """
        self.home_team.reset_positions()
        self.away_team.reset_positions()
        self.ball.x = self.field_width // 2
        self.ball.y = self.field_height // 2
        self.ball.vx = 0
        self.ball.vy = 0
        self.ball.possessed_by = None
        self.assign_initial_possession()

    def check_goal(self):
        """
        Check if a goal has been scored.
        If the ball crosses the left or right boundaries, update the score and reset positions.
        """
        if self.ball.x <= 0:
            # Away team scores (their attacking goal is on the left)
            self.away_team.score += 1
            print("Goal for Away Team!")
            time.sleep(1)
            self.reset_positions()
        elif self.ball.x >= self.field_width - 1:
            # Home team scores (attacking right)
            self.home_team.score += 1
            print("Goal for Home Team!")
            time.sleep(1)
            self.reset_positions()

    def update(self):
        """
        Update the state of the game:
          - Update each player's behavior.
          - Check and assign ball possession if a player is near the ball.
          - Update the ball physics.
          - Check for a goal.
        """
        # Update all players.
        for player in self.home_team.players + self.away_team.players:
            player.update(self.ball, self.field_width, self.field_height)
            # If ball is free and a player is near, gain possession.
            if self.ball.possessed_by is None and player.distance_to(self.ball.x, self.ball.y) < 2:
                player.has_ball = True
                self.ball.possessed_by = player

        # Update the ball's movement if not possessed.
        self.ball.update(self.field_width, self.field_height)

        # Check for goal scoring.
        self.check_goal()

    def render(self):
        """
        Render the field using ASCII graphics.
        Draw field borders, a center line, players, and the ball.
        Also display the current time, score, and ball possession status.
        """
        # Initialize an empty field.
        field = [[' ' for _ in range(self.field_width)] for _ in range(self.field_height)]

        # Draw top and bottom borders.
        for x in range(self.field_width):
            field[0][x] = '-'
            field[self.field_height - 1][x] = '-'
        # Draw left and right borders.
        for y in range(self.field_height):
            field[y][0] = '|'
            field[y][self.field_width - 1] = '|'
        # Draw a center line.
        mid = self.field_width // 2
        for y in range(self.field_height):
            field[y][mid] = '|'

        # Place the ball.
        bx = int(round(self.ball.x))
        by = int(round(self.ball.y))
        if 0 <= bx < self.field_width and 0 <= by < self.field_height:
            field[by][bx] = 'o'

        # Place all players.
        for player in self.home_team.players + self.away_team.players:
            px = int(round(player.x))
            py = int(round(player.y))
            if 0 <= px < self.field_width and 0 <= py < self.field_height:
                field[py][px] = player.symbol

        # Clear the terminal.
        os.system('cls' if os.name == 'nt' else 'clear')

        # Print the field.
        for row in field:
            print(''.join(row))
        # Print status updates.
        print(f"Time: {int(self.current_time)} sec   Home: {self.home_team.score}  Away: {self.away_team.score}")
        if self.ball.possessed_by:
            print(f"Ball in possession of {self.ball.possessed_by.team.name} Team")
        else:
            print("Ball is free")

    def run(self):
        """
        Main game loop.
        The game runs for the specified duration, updating the state and rendering the field.
        """
        start_time = time.time()
        while self.current_time < self.game_duration:
            self.update()
            self.render()
            time.sleep(0.1)  # Pacing for animation effect.
            self.current_time = time.time() - start_time
        print("Full Time!")
        print(f"Final Score - Home: {self.home_team.score}  Away: {self.away_team.score}")

# -------------------------------
# Main Execution
# -------------------------------
if __name__ == "__main__":
    game = Game()
    game.run()
