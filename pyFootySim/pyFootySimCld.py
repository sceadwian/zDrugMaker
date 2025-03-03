import os
import random
import time
import math

class Player:
    """
    Represents an individual soccer player with position and movement capabilities.
    """
    def __init__(self, symbol, base_x, base_y, team):
        self.symbol = symbol
        self.x = base_x
        self.y = base_y
        self.base_x = base_x
        self.base_y = base_y
        self.team = team
        self.has_ball = False

    def move(self, ball, players):
        """
        Move the player based on game situation:
        1. If player has the ball, move toward opponent's goal
        2. If ball is nearby, move toward it
        3. Otherwise, wander around base position
        """
        if self.has_ball:
            # If player has the ball, move toward opponent's goal
            goal_x = self.team.opponent_goal
            
            # Calculate direction to opponent's goal
            dx = 1 if goal_x > self.x else -1
            
            # Move toward goal
            new_x = self.x + dx
            new_y = self.y
            
            # Decision making: pass or shoot
            self.decide_action(ball, players)
        elif self.is_ball_nearby(ball):
            # Move toward ball if nearby
            dx = 1 if ball.x > self.x else (-1 if ball.x < self.x else 0)
            dy = 1 if ball.y > self.y else (-1 if ball.y < self.y else 0)
            
            new_x = self.x + dx
            new_y = self.y + dy
        else:
            # Wander around base position
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            
            # Try to stay near base position
            if abs(self.x + dx - self.base_x) <= 5 and abs(self.y + dy - self.base_y) <= 2:
                new_x = self.x + dx
                new_y = self.y + dy
            else:
                # Move back toward base position
                new_x = self.x + (1 if self.base_x > self.x else -1)
                new_y = self.y + (1 if self.base_y > self.y else -1)
        
        # Ensure player stays within field boundaries
        new_x = max(1, min(new_x, 78))
        new_y = max(1, min(new_y, 18))
        
        # Check for collision with other players
        if not self.check_collision(new_x, new_y, players):
            self.x, self.y = new_x, new_y

    def check_collision(self, x, y, players):
        """Check if moving to position would cause collision with another player"""
        for player in players:
            if player != self and player.x == x and player.y == y:
                return True
        return False

    def is_ball_nearby(self, ball):
        """Check if ball is within 3 units of player"""
        distance = math.sqrt((self.x - ball.x) ** 2 + (self.y - ball.y) ** 2)
        return distance <= 3

    def decide_action(self, ball, players):
        """Decide whether to pass or shoot"""
        goal_x = self.team.opponent_goal
        
        # If close to goal, try to shoot
        if abs(self.x - goal_x) < 10:
            if random.random() < 0.3:  # 30% chance to shoot when near goal
                self.shoot(ball)
                return
        
        # Otherwise, look for a teammate to pass to
        teammates = [p for p in players if p.team == self.team and p != self]
        forward_teammates = []
        
        for teammate in teammates:
            # Check if teammate is closer to opponent's goal than current player
            if ((goal_x > self.x and teammate.x > self.x) or 
                (goal_x < self.x and teammate.x < self.x)):
                forward_teammates.append(teammate)
        
        if forward_teammates and random.random() < 0.4:  # 40% chance to pass
            target = random.choice(forward_teammates)
            self.pass_ball(ball, target)

    def shoot(self, ball):
        """Shoot the ball toward opponent's goal"""
        goal_x = self.team.opponent_goal
        goal_y = 10  # Middle of the field height
        
        # Calculate direction to goal
        dx = goal_x - self.x
        dy = goal_y - self.y
        
        # Normalize and add some randomness
        distance = math.sqrt(dx ** 2 + dy ** 2)
        if distance > 0:
            dx = dx / distance * 2 + random.uniform(-0.2, 0.2)
            dy = dy / distance * 2 + random.uniform(-0.5, 0.5)
        
        # Set ball velocity
        ball.vx = dx
        ball.vy = dy
        
        # Release the ball
        ball.x = self.x
        ball.y = self.y
        self.has_ball = False

    def pass_ball(self, ball, target_player):
        """Pass the ball to a teammate"""
        # Direction to teammate
        dx = target_player.x - self.x
        dy = target_player.y - self.y
        
        # Normalize
        distance = math.sqrt(dx ** 2 + dy ** 2)
        if distance > 0:
            dx = dx / distance * 1.5
            dy = dy / distance * 1.5
        
        # Set ball velocity
        ball.vx = dx
        ball.vy = dy
        
        # Release the ball
        ball.x = self.x
        ball.y = self.y
        self.has_ball = False


class Ball:
    """
    Represents the soccer ball with position and physics.
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
    
    def update(self, field_width, field_height):
        """Update ball position based on velocity and handle bounces"""
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Bounce off walls
        if self.x <= 1 or self.x >= field_width - 2:
            self.vx = -self.vx * 0.7  # Bounce with 30% energy loss
        if self.y <= 1 or self.y >= field_height - 2:
            self.vy = -self.vy * 0.7  # Bounce with 30% energy loss
        
        # Ensure ball stays within field
        self.x = max(1, min(self.x, field_width - 2))
        self.y = max(1, min(self.y, field_height - 2))
        
        # Apply friction
        self.vx *= 0.95
        self.vy *= 0.95
        
        # Stop if velocity is very small
        if abs(self.vx) < 0.1 and abs(self.vy) < 0.1:
            self.vx = 0
            self.vy = 0


class Team:
    """
    Represents a soccer team with players and team statistics.
    """
    def __init__(self, name, symbol, goal_x):
        self.name = name
        self.symbol = symbol
        self.score = 0
        self.goal_x = goal_x  # The goal this team defends
        self.opponent_goal = 1 if goal_x == 78 else 78  # The goal this team attacks
        self.players = []
    
    def setup_formation(self, field_width, field_height):
        """Set up initial player formation"""
        # Clear existing players
        self.players = []
        
        # Determine if home (left) or away (right) for formation setup
        is_left_side = (self.goal_x == 1)
        
        # Base x-position depends on which side of the field
        base_x = 20 if is_left_side else 60
        
        # Goalkeeper
        goalkeeper_x = 5 if is_left_side else 75
        self.add_player(goalkeeper_x, 10)
        
        # Defenders (3)
        def_x = 15 if is_left_side else 65
        for y_pos in [5, 10, 15]:
            self.add_player(def_x, y_pos)
        
        # Midfielders (4)
        mid_x = 30 if is_left_side else 50
        for y_pos in [4, 8, 12, 16]:
            self.add_player(mid_x, y_pos)
        
        # Forwards (3)
        fwd_x = 45 if is_left_side else 35
        for y_pos in [5, 10, 15]:
            self.add_player(fwd_x, y_pos)
    
    def add_player(self, base_x, base_y):
        """Add a player to the team"""
        player = Player(self.symbol, base_x, base_y, self)
        self.players.append(player)
        return player


class Game:
    """
    Manages the overall soccer game simulation.
    """
    def __init__(self, width=80, height=20, duration=300):
        self.width = width
        self.height = height
        self.duration = duration
        self.time = 0
        
        # Create teams
        self.home_team = Team("Home", "H", 1)
        self.away_team = Team("Away", "A", 78)
        
        # Set opponent references
        self.home_team.opponent = self.away_team
        self.away_team.opponent = self.home_team
        
        # Set up player formations
        self.home_team.setup_formation(width, height)
        self.away_team.setup_formation(width, height)
        
        # Create the ball at center field
        self.ball = Ball(width // 2, height // 2)
        
        # Give initial possession to a random team
        self.give_random_possession()
    
    def give_random_possession(self):
        """Give the ball to a random player on a random team"""
        team = random.choice([self.home_team, self.away_team])
        player = random.choice(team.players)
        
        # Position the ball with the player
        self.ball.x = player.x
        self.ball.y = player.y
        
        # Give possession
        player.has_ball = True
        
        # Reset ball velocity
        self.ball.vx = 0
        self.ball.vy = 0
    
    def check_goal(self):
        """Check if a goal has been scored"""
        # Check if ball is at either end of the field
        if self.ball.x <= 1:
            # Goal for away team
            if 7 <= self.ball.y <= 13:  # Goal height
                self.away_team.score += 1
                self.display_goal_message(self.away_team.name)
                self.reset_after_goal()
                return True
                
        elif self.ball.x >= self.width - 2:
            # Goal for home team
            if 7 <= self.ball.y <= 13:  # Goal height
                self.home_team.score += 1
                self.display_goal_message(self.home_team.name)
                self.reset_after_goal()
                return True
        
        return False
    
    def display_goal_message(self, team_name):
        """Display a goal message"""
        print(f"\n{'*' * 20}")
        print(f"GOAL for {team_name} team!")
        print(f"{'*' * 20}")
        time.sleep(2)  # Pause to show the goal message
    
    def reset_after_goal(self):
        """Reset player and ball positions after a goal"""
        # Reset ball to center
        self.ball.x = self.width // 2
        self.ball.y = self.height // 2
        self.ball.vx = 0
        self.ball.vy = 0
        
        # Reset player positions
        self.home_team.setup_formation(self.width, self.height)
        self.away_team.setup_formation(self.width, self.height)
        
        # Give possession to the team that conceded
        if self.home_team.score > self.away_team.score:
            player = random.choice(self.away_team.players)
        else:
            player = random.choice(self.home_team.players)
        
        player.has_ball = True
    
    def update_ball_possession(self):
        """Update which player has possession of the ball"""
        # Remove existing possession
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                player.has_ball = False
        
        # Check for new possession
        all_players = self.home_team.players + self.away_team.players
        
        for player in all_players:
            # Only change possession if ball is moving slowly
            if abs(self.ball.vx) < 0.2 and abs(self.ball.vy) < 0.2:
                distance = math.sqrt((player.x - self.ball.x) ** 2 + (player.y - self.ball.y) ** 2)
                if distance < 1.5:  # Close enough to gain possession
                    player.has_ball = True
                    self.ball.x = player.x
                    self.ball.y = player.y
                    self.ball.vx = 0
                    self.ball.vy = 0
                    break
    
    def update(self):
        """Update game state for one time step"""
        # Update players
        all_players = self.home_team.players + self.away_team.players
        for player in all_players:
            player.move(self.ball, all_players)
        
        # Update ball if not in possession
        has_possession = False
        for player in all_players:
            if player.has_ball:
                has_possession = True
                break
        
        if not has_possession:
            self.ball.update(self.width, self.height)
        
        # Check for goals
        if not self.check_goal():
            # Update possession (only if no goal was scored)
            self.update_ball_possession()
    
    def render(self):
        """Render the soccer field and game state"""
        # Clear the terminal
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Create field buffer
        field = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        
        # Draw borders
        for x in range(self.width):
            field[0][x] = '-'
            field[self.height - 1][x] = '-'
        
        for y in range(self.height):
            field[y][0] = '|'
            field[y][self.width - 1] = '|'
        
        # Draw center line
        for y in range(self.height):
            field[y][self.width // 2] = '|'
        
        # Draw goals
        for y in range(7, 14):
            field[y][0] = 'G'
            field[y][self.width - 1] = 'G'
        
        # Draw players
        for player in self.home_team.players + self.away_team.players:
            x, y = int(player.x), int(player.y)
            if 0 <= x < self.width and 0 <= y < self.height:
                field[y][x] = player.symbol
        
        # Draw ball
        ball_x, ball_y = int(self.ball.x), int(self.ball.y)
        if 0 <= ball_x < self.width and 0 <= ball_y < self.height:
            field[ball_y][ball_x] = 'o'
        
        # Print field
        print('\n')
        for row in field:
            print(''.join(row))
        
        # Print game info
        minutes = int(self.time // 60)
        seconds = int(self.time % 60)
        print(f"\nTime: {minutes:02d}:{seconds:02d}")
        print(f"Score: Home {self.home_team.score} - {self.away_team.score} Away")
        
        # Show which team has possession
        possession = "None"
        for team in [self.home_team, self.away_team]:
            for player in team.players:
                if player.has_ball:
                    possession = team.name
                    break
        print(f"Possession: {possession}")
    
    def run(self):
        """Run the main game loop"""
        try:
            while self.time < self.duration:
                self.update()
                self.render()
                
                # Increment time
                self.time += 0.1
                
                # Add delay for animation
                time.sleep(0.1)
            
            # Game over message
            self.render()
            print("\nFULL TIME!")
            print(f"Final Score: Home {self.home_team.score} - {self.away_team.score} Away")
            if self.home_team.score > self.away_team.score:
                print("Home team wins!")
            elif self.away_team.score > self.home_team.score:
                print("Away team wins!")
            else:
                print("It's a draw!")
                
        except KeyboardInterrupt:
            print("\nGame interrupted!")


if __name__ == "__main__":
    game = Game()
    game.run()