import random

class Player:
    def __init__(self, name, surname, position):
        self.name = name
        self.surname = surname
        self.position = position
        self.age = random.randint(18, 35)
        self.height = random.randint(160, 200)
        self.agility = random.randint(1, 100)
        self.strength = random.randint(1, 100)
        self.stamina = random.randint(1, 100)
        self.intellect = random.randint(1, 100)
        self.tackling = random.randint(1, 100)
        self.passing = random.randint(1, 100)
        self.crossing = random.randint(1, 100)
        self.shooting = random.randint(1, 100)
        self.air = random.randint(1, 100)
        self.corner = random.randint(1, 100)

class Team:
    def __init__(self, name):
        self.name = name
        self.players = []
        self.generate_players()

    def generate_players(self):
        positions = ['GK'] + ['DEF'] * 4 + ['MID'] * 4 + ['ATK'] * 2
        for position in positions:
            name = f"Player{len(self.players) + 1}"
            surname = f"Surname{len(self.players) + 1}"
            self.players.append(Player(name, surname, position))

class Zone:
    def __init__(self, name):
        self.name = name
        self.attributes = {
            'agility': 0, 'strength': 0, 'stamina': 0, 'intellect': 0,
            'tackling': 0, 'passing': 0, 'crossing': 0, 'shooting': 0,
            'air': 0, 'corner': 0
        }

    def update_attributes(self, players):
        for attr in self.attributes:
            self.attributes[attr] = sum(getattr(player, attr) for player in players) / len(players)

class Pitch:
    def __init__(self, home_team, away_team):
        self.zones = {
            'HL': Zone('HL'), 'HC': Zone('HC'), 'HR': Zone('HR'),
            'ML': Zone('ML'), 'MC': Zone('MC'), 'MR': Zone('MR'),
            'AL': Zone('AL'), 'AC': Zone('AC'), 'AR': Zone('AR')
        }
        self.update_zones(home_team, away_team)

    def update_zones(self, home_team, away_team):
        zone_players = {
            'HL': [p for p in home_team.players if p.position == 'DEF'][0],
            'HC': [p for p in home_team.players if p.position == 'DEF'][1:3],
            'HR': [p for p in home_team.players if p.position == 'DEF'][3],
            'ML': [p for p in home_team.players if p.position == 'MID'][0],
            'MC': [p for p in home_team.players if p.position == 'MID'][1:3],
            'MR': [p for p in home_team.players if p.position == 'MID'][3],
            'AL': [p for p in away_team.players if p.position == 'ATK'][0],
            'AC': [p for p in away_team.players if p.position == 'ATK'],
            'AR': [p for p in away_team.players if p.position == 'ATK'][1]
        }

        for zone_name, players in zone_players.items():
            self.zones[zone_name].update_attributes(players if isinstance(players, list) else [players])

class Match:
    def __init__(self, home_team, away_team):
        self.home_team = home_team
        self.away_team = away_team
        self.pitch = Pitch(home_team, away_team)
        self.home_score = 0
        self.away_score = 0

    def simulate(self):
        for _ in range(90):  # 90 minutes
            if random.random() < 0.1:  # 10% chance of a goal attempt
                if random.random() < 0.5:  # 50% chance for home team to attack
                    attacking_team = self.home_team
                    attacking_zones = ['AL', 'AC', 'AR']
                    defending_zones = ['HL', 'HC', 'HR']
                else:
                    attacking_team = self.away_team
                    attacking_zones = ['HL', 'HC', 'HR']
                    defending_zones = ['AL', 'AC', 'AR']
                
                attacking_zone = random.choice(attacking_zones)
                defending_zone = random.choice(defending_zones)
                
                attack_strength = sum(self.pitch.zones[attacking_zone].attributes.values())
                defense_strength = sum(self.pitch.zones[defending_zone].attributes.values())
                
                # Adjust scoring probabilities
                if attack_strength > defense_strength:
                    scoring_probability = 0.3
                else:
                    scoring_probability = 0.1
                
                if random.random() < scoring_probability:
                    if attacking_team == self.home_team:
                        self.home_score += 1
                    else:
                        self.away_score += 1

        return self.home_score, self.away_score

class Tournament:
    def __init__(self, team_names):
        self.teams = [Team(name) for name in team_names]
        self.schedule = self.generate_schedule()
        self.results = {}

    def generate_schedule(self):
        schedule = []
        for home in self.teams:
            for away in self.teams:
                if home != away:
                    schedule.append((home, away))
        return schedule * 2  # Each pair plays twice (home and away)

    def play_match(self, home, away):
        match = Match(home, away)
        return match.simulate()

    def run_tournament(self):
        for home, away in self.schedule:
            home_score, away_score = self.play_match(home, away)
            self.results[(home.name, away.name)] = (home_score, away_score)

    def print_results(self):
        for (home, away), (home_score, away_score) in self.results.items():
            print(f"{home:<20} {home_score:>2} - {away_score:<2} {away:<20}")

    def get_standings(self):
        standings = {team.name: {'points': 0, 'goals_for': 0, 'goals_against': 0} for team in self.teams}
        
        for (home, away), (home_score, away_score) in self.results.items():
            standings[home]['goals_for'] += home_score
            standings[home]['goals_against'] += away_score
            standings[away]['goals_for'] += away_score
            standings[away]['goals_against'] += home_score
            
            if home_score > away_score:
                standings[home]['points'] += 3
            elif home_score < away_score:
                standings[away]['points'] += 3
            else:
                standings[home]['points'] += 1
                standings[away]['points'] += 1
        
        return sorted(standings.items(), key=lambda x: (x[1]['points'], x[1]['goals_for'] - x[1]['goals_against']), reverse=True)

    def print_standings(self):
        standings = self.get_standings()
        print("\nFinal Standings:")
        print(f"{'Team':<20} {'Points':>6} {'GF':>4} {'GA':>4} {'GD':>4}")
        print("-" * 42)
        for team, stats in standings:
            gd = stats['goals_for'] - stats['goals_against']
            print(f"{team:<20} {stats['points']:>6} {stats['goals_for']:>4} {stats['goals_against']:>4} {gd:>4}")

# Run the simulation
team_names = [f"Team{i}" for i in range(1, 21)]
tournament = Tournament(team_names)
tournament.run_tournament()
print("Match Results:")
tournament.print_results()
tournament.print_standings()