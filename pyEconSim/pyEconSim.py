import random

# Define constants
DAYS_IN_YEAR = 365
ALPHA = 0.1  # Sensitivity factor for price adjustments

class Pop:
    def __init__(self, name, money, skills, personality):
        self.name = name
        self.money = money
        self.skills = skills
        self.personality = personality
        self.hunger = 100
        self.health = 100
        self.happiness = 100
        self.inventory = {}  # Stores goods the Pop owns
        self.job = None

    def consume(self):
        """Consume goods to meet needs."""
        # Reduce hunger by consuming food
        if "food" in self.inventory and self.inventory["food"] > 0:
            self.hunger = min(100, self.hunger + 20)  # Food restores hunger
            self.inventory["food"] -= 1
        else:
            self.hunger = max(0, self.hunger - 10)  # Hunger decreases if no food

        # Reduce health if hunger is too low
        if self.hunger <= 10:
            self.health = max(0, self.health - 5)

        # Increase happiness if luxury goods are consumed
        if "luxury" in self.inventory and self.inventory["luxury"] > 0:
            self.happiness = min(100, self.happiness + 10)
            self.inventory["luxury"] -= 1

    def work(self, job):
        """Work at a job to earn money and produce goods."""
        if self.job is None:
            self.job = job
        effort = job["effort"]
        if self.health > 50 and self.hunger > 20:  # Pops can only work if healthy and not starving
            self.money += job["salary"]
            if job["produces"]:
                self.inventory[job["produces"]] = self.inventory.get(job["produces"], 0) + 1
            self.hunger = max(0, self.hunger - effort)
        else:
            print(f"{self.name} is too unhealthy or hungry to work.")

    def buy(self, good, market):
        """Buy goods from the market."""
        if good in market.prices and self.money >= market.prices[good]:
            self.money -= market.prices[good]
            self.inventory[good] = self.inventory.get(good, 0) + 1
            print(f"{self.name} bought {good} for ${market.prices[good]}.")
        else:
            print(f"{self.name} cannot afford {good}.")

    def sell(self, good, market):
        """Sell goods to the market."""
        if good in self.inventory and self.inventory[good] > 0:
            self.money += market.prices[good]
            self.inventory[good] -= 1
            print(f"{self.name} sold {good} for ${market.prices[good]}.")
        else:
            print(f"{self.name} has no {good} to sell.")

    def __str__(self):
        return (f"{self.name}: Money=${self.money}, Hunger={self.hunger}, "
                f"Health={self.health}, Happiness={self.happiness}, Inventory={self.inventory}")

class Good:
    def __init__(self, name, base_cost, quality, decay_rate):
        self.name = name
        self.base_cost = base_cost
        self.quality = quality
        self.decay_rate = decay_rate

class Market:
    def __init__(self):
        self.prices = {}  # Stores current prices for goods
        self.supply = {}  # Stores total supply of goods
        self.demand = {}  # Stores total demand for goods

    def update_prices(self):
        """Update prices based on supply and demand."""
        for good in self.prices:
            if self.supply.get(good, 0) > 0:
                price_change = ALPHA * ((self.demand.get(good, 0) - self.supply.get(good, 0)) / self.supply.get(good, 0))
                self.prices[good] = self.prices[good] * (1 + price_change)
            else:
                self.prices[good] *= 1.2  # Increase price if supply is zero

    def clear_market(self):
        """Reset supply and demand for the next cycle."""
        self.supply = {}
        self.demand = {}

# Define jobs
JOBS = {
    "farmer": {"salary": 10, "effort": 5, "produces": "food"},
    "miner": {"salary": 15, "effort": 10, "produces": "tools"},
    "merchant": {"salary": 20, "effort": 3, "produces": None}
}

# Define goods
GOODS = {
    "food": Good("food", 5, 50, 1),
    "tools": Good("tools", 20, 80, 0.1),
    "luxury": Good("luxury", 50, 100, 0.5)
}

# Initialize Pops
pops = [
    Pop("Alice", 100, {"farming": 5}, "risk-averse"),
    Pop("Bob", 100, {"mining": 5}, "adventurous")
]

# Initialize market
market = Market()
market.prices = {good: GOOODS[good].base_cost for good in GOODS}

# Simulation loop
for day in range(DAYS_IN_YEAR):
    print(f"\n--- Day {day + 1} ---")
    # Production phase
    for pop in pops:
        pop.work(JOBS["farmer"] if pop.skills.get("farming", 0) > 0 else JOBS["miner"])

    # Market phase
    for pop in pops:
        pop.buy("food", market)
        pop.sell("tools", market)

    # Consumption phase
    for pop in pops:
        pop.consume()

    # Update market prices
    market.update_prices()

    # Print Pop status
    for pop in pops:
        print(pop)

    # Clear market for the next day
    market.clear_market()