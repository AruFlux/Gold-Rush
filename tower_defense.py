Python 3.13.5 (tags/v3.13.5:6cb20a2, Jun 11 2025, 16:15:46) [MSC v.1943 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
# tower_defense.py
# Pixel tower defense prototype (mouse-only)
# Requires pygame: pip install pygame
# Tile size: 64x64 (default)
# Features:
# - Multiple levels (defined in LEVELS list)
# - Simple path-following enemies
# - Towers placed with mouse (click on empty ground tile)
# - Upgradable towers (click tower -> upgrade)
# - Waves per level, simple level progression
# - Save / Load (export/import JSON to file)
# - Mouse only controls (ESC to quit, some keyboard shortcuts optional)

import pygame
import sys
import math
import json
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

# ---------- CONFIG ----------
TILE = 64
SCREEN_TILES_W = 12
SCREEN_TILES_H = 8
SCREEN_W = TILE * SCREEN_TILES_W
SCREEN_H = TILE * SCREEN_TILES_H
FPS = 60

FONT_SIZE = 16

STARTING_GOLD = 200
STARTING_LIVES = 20

# Tower definitions (id -> properties)
TOWER_TYPES = {
    "arrow": {
        "name": "Arrow Tower",
        "cost": 75,
        "range": TILE * 3,
        "damage": 10,
        "rate": 0.6,  # shots per second
        "upgrade_cost": 60,
    },
    "cannon": {
        "name": "Cannon",
        "cost": 125,
        "range": TILE * 2.5,
        "damage": 40,
        "rate": 1.2,
        "upgrade_cost": 100,
    }
}

# Enemy types
ENEMY_TYPES = {
    "grunt": {"hp": 30, "speed": 40, "reward": 8},
    "tough": {"hp": 100, "speed": 24, "reward": 25},
}

# Simple pixel colors
COLORS = {
    "bg": (30, 30, 30),
    "grid": (50, 50, 50),
    "path": (90, 60, 30),
    "ground": (70, 120, 70),
    "tower": (150, 150, 40),
    "tower_upgrade": (200, 170, 30),
    "enemy": (200, 40, 40),
    "projectile": (240, 240, 100),
    "ui_panel": (20, 20, 20),
    "text": (230, 230, 230),
    "button": (100, 100, 100),
}

# ---------- SAMPLE LEVELS ----------
# Each level contains:
# - width, height in tiles
# - path: list of tile coords forming path from start to end
# - waves: list of (enemy_type, count, spawn_interval_seconds)
LEVELS = [
    {
        "name": "Greenway I",
        "width": SCREEN_TILES_W,
        "height": SCREEN_TILES_H,
        # path: from left to right across center
        "path": [(0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3),
                 (6, 3), (7, 3), (8, 3), (9, 3), (10, 3), (11, 3)],
        "waves": [
            ("grunt", 8, 0.9),
            ("grunt", 10, 0.7),
            ("tough", 3, 1.5),
        ],
    },
    {
        "name": "River Bend",
        "width": SCREEN_TILES_W,
        "height": SCREEN_TILES_H,
        "path": [(0, 2), (1, 2), (2,2), (3,2), (3,3), (3,4), (4,4), (5,4), (6,4), (7,4), (8,4), (9,4), (10,4), (11,4)],
        "waves": [
            ("grunt", 10, 0.8),
            ("grunt", 12, 0.6),
            ("tough", 4, 1.4),
        ],
    },
    {
        "name": "Fortified Road",
        "width": SCREEN_TILES_W,
        "height": SCREEN_TILES_H,
        "path": [(0,5),(1,5),(2,5),(3,5),(4,5),(4,4),(4,3),(5,3),(6,3),(7,3),(8,3),(9,3),(10,3),(11,3)],
        "waves": [
            ("grunt", 12, 0.7),
            ("tough", 5, 1.3),
            ("grunt", 15, 0.5),
        ],
    }
]

# ---------- GAME OBJECTS ----------
@dataclass
class Path:
    tiles: List[Tuple[int, int]]
    points: List[Tuple[float, float]] = field(init=False)

    def __post_init__(self):
        # Convert tile coords to center pixel coords
        self.points = [((tx + 0.5) * TILE, (ty + 0.5) * TILE) for (tx, ty) in self.tiles]

@dataclass
class Enemy:
    type_id: str
    hp: float
    max_hp: float
    speed: float
    reward: int
    path: Path
    pos: Tuple[float, float]
    path_index: int = 0
    alive: bool = True

    @classmethod
    def spawn(cls, type_id: str, path: Path):
        info = ENEMY_TYPES[type_id]
        start = path.points[0]
        return cls(
            type_id=type_id,
            hp=float(info["hp"]),
            max_hp=float(info["hp"]),
            speed=float(info["speed"]),
            reward=int(info["reward"]),
            path=path,
            pos=start,
            path_index=0,
            alive=True
        )

    def update(self, dt):
        if not self.alive:
            return
        # Move along path points
        if self.path_index >= len(self.path.points) - 1:
            # reached end
            return
        target = self.path.points[self.path_index + 1]
        vx = target[0] - self.pos[0]
        vy = target[1] - self.pos[1]
        dist = math.hypot(vx, vy)
        if dist == 0:
            self.path_index += 1
            return
        maxd = self.speed * dt
        if dist <= maxd:
            self.pos = target
            self.path_index += 1
        else:
            self.pos = (self.pos[0] + vx / dist * maxd, self.pos[1] + vy / dist * maxd)

    def reached_goal(self):
        return self.path_index >= len(self.path.points) - 1 and self.pos == self.path.points[-1]

@dataclass
class Projectile:
    pos: Tuple[float, float]
    target: Enemy
    speed: float
    damage: float
    alive: bool = True

    def update(self, dt):
        if not self.alive or not self.target.alive:
            self.alive = False
            return
        vx = self.target.pos[0] - self.pos[0]
        vy = self.target.pos[1] - self.pos[1]
        dist = math.hypot(vx, vy)
        if dist <= 0:
            self.hit()
            return
        step = self.speed * dt
        if dist <= step:
            self.pos = self.target.pos
            self.hit()
        else:
            self.pos = (self.pos[0] + vx / dist * step, self.pos[1] + vy / dist * step)

    def hit(self):
        if self.target.alive:
            self.target.hp -= self.damage
            if self.target.hp <= 0:
                self.target.alive = False
        self.alive = False

@dataclass
class Tower:
    tx: int
    ty: int
    type_id: str
    level: int = 1
    last_shot: float = 0.0

    def get_props(self):
        base = TOWER_TYPES[self.type_id]
        # Simple scaling per level
        damage = base["damage"] * (1 + 0.5 * (self.level - 1))
        rng = base["range"] * (1 + 0.12 * (self.level - 1))
        rate = base["rate"] * (1 - 0.08 * (self.level - 1))
        return {"damage": damage, "range": rng, "rate": max(0.12, rate), "upgrade_cost": base["upgrade_cost"] * self.level}

# ---------- GAME CLASS ----------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pixel Tower Defense — Prototype")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H + 80))  # add UI panel
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", FONT_SIZE)
        self.running = True

        # Game state
        self.gold = STARTING_GOLD
        self.lives = STARTING_LIVES
        self.level_index = 0
        self.load_level(self.level_index)

        self.towers: List[Tower] = []
        self.enemies: List[Enemy] = []
        self.projectiles: List[Projectile] = []
        self.wave_queue = []
        self.wave_timer = 0.0
        self.current_wave_idx = 0
        self.wave_spawning = False
        self.spawn_count = 0
        self.selected_tile = None
        self.selected_tower = None
        self.paused = False

        # UI buttons area
        self.ui_rect = pygame.Rect(0, SCREEN_H, SCREEN_W, 80)

    def load_level(self, idx):
        lvl = LEVELS[idx]
        self.level_name = lvl["name"]
        self.level_w = lvl["width"]
        self.level_h = lvl["height"]
        self.path = Path(lvl["path"])
        self.waves = lvl["waves"]
        # create a flattened spawn queue: list of tuples (time_offset, enemy_type)
        self.wave_queue = []
        accum = 0.0
        for (etype, count, interval) in self.waves:
            for i in range(count):
                self.wave_queue.append((accum + i * interval, etype))
            # give a gap between waves
            accum = self.wave_queue[-1][0] + 4.0
        self.level_time = 0.0
        self.enemies = []
        self.towers = []
        self.projectiles = []
        self.gold = STARTING_GOLD
        self.lives = STARTING_LIVES
        self.current_wave_idx = 0
        self.spawned_indices = set()

    def tile_from_pos(self, pos):
        x, y = pos
        if x < 0 or x >= SCREEN_W or y < 0 or y >= SCREEN_H:
            return None
        return (int(x // TILE), int(y // TILE))

    def pos_center_of_tile(self, tx, ty):
        return ((tx + 0.5) * TILE, (ty + 0.5) * TILE)

    def is_on_path_tile(self, tx, ty):
        return (tx, ty) in self.path.tiles

    def place_tower(self, tx, ty, type_id):
        # don't place over path or existing tower
        if self.is_on_path_tile(tx, ty):
            return False, "Can't place on path"
        for t in self.towers:
            if t.tx == tx and t.ty == ty:
                return False, "Tile occupied"
        cost = TOWER_TYPES[type_id]["cost"]
        if self.gold < cost:
            return False, "Not enough gold"
        self.gold -= cost
        self.towers.append(Tower(tx=tx, ty=ty, type_id=type_id))
        return True, "Tower placed"

    def upgrade_tower(self, tower: Tower):
        props = tower.get_props()
        cost = props["upgrade_cost"]
        if self.gold < cost:
            return False, "Not enough gold"
        self.gold -= cost
        tower.level += 1
        return True, "Upgraded"

    def sell_tower(self, tower: Tower):
        base_cost = TOWER_TYPES[tower.type_id]["cost"]
        refund = int(0.6 * base_cost * (1 + 0.4 * (tower.level - 1)))
        self.gold += refund
        self.towers.remove(tower)
        return refund

    def spawn_enemy(self, etype):
        e = Enemy.spawn(etype, self.path)
        self.enemies.append(e)

    def handle_spawning(self, dt):
        # spawn according to absolute level_time and wave_queue
        self.level_time += dt
        for i, (t_offset, etype) in enumerate(self.wave_queue):
            if i in self.spawned_indices:
                continue
            if self.level_time >= t_offset:
                self.spawn_enemy(etype)
                self.spawned_indices.add(i)

    def update(self, dt):
        if self.paused:
            return
        self.handle_spawning(dt)
        # update enemies
        for e in list(self.enemies):
            e.update(dt)
            if e.reached_goal():
                # damage player
                e.alive = False
                self.lives -= 1
                if self.lives <= 0:
                    self.running = False
            if not e.alive:
                # reward and remove
                self.gold += e.reward
                if e in self.enemies:
                    self.enemies.remove(e)
        # update towers -> fire projectiles
        now = pygame.time.get_ticks() / 1000.0
        for t in self.towers:
            props = t.get_props()
            # find first enemy in range
            txc = (t.tx + 0.5) * TILE
            tyc = (t.ty + 0.5) * TILE
            target = None
            best_dist = 99999
            for e in self.enemies:
                if not e.alive:
                    continue
                ex, ey = e.pos
                d = math.hypot(ex - txc, ey - tyc)
                if d <= props["range"]:
                    # prefer furthest along path (higher path_index), tie break by dist
                    score = (e.path_index, -d)
                    if target is None or (e.path_index > target[0] or (e.path_index == target[0] and d < best_dist)):
                        target = (e.path_index, e, d)
                        best_dist = d
            if target:
                e = target[1]
                d = target[2]
                if now - t.last_shot >= 1.0 / props["rate"]:
                    # fire
                    proj = Projectile(pos=(txc, tyc), target=e, speed=300.0, damage=props["damage"])
                    self.projectiles.append(proj)
                    t.last_shot = now
        # update projectiles
        for p in list(self.projectiles):
            p.update(dt)
            if not p.alive:
                if p in self.projectiles:
                    self.projectiles.remove(p)

    # ---------- DRAW ----------
    def draw_grid(self, surf):
        for y in range(self.level_h):
            for x in range(self.level_w):
                rect = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                if (x, y) in self.path.tiles:
                    pygame.draw.rect(surf, COLORS["path"], rect)
                else:
                    pygame.draw.rect(surf, COLORS["ground"], rect)
                # grid lines
                pygame.draw.rect(surf, COLORS["grid"], rect, 1)

    def draw_towers(self, surf):
        for t in self.towers:
            rect = pygame.Rect(t.tx * TILE + 6, t.ty * TILE + 6, TILE - 12, TILE - 12)
            color = COLORS["tower_upgrade"] if t.level > 1 else COLORS["tower"]
            pygame.draw.rect(surf, color, rect)
            # level indicator
            txt = self.font.render(f"Lv{t.level}", True, COLORS["text"])
            surf.blit(txt, (t.tx * TILE + 8, t.ty * TILE + TILE - 22))

    def draw_enemies(self, surf):
        for e in self.enemies:
            if not e.alive:
                continue
            x, y = e.pos
            r = TILE // 3
            rect = pygame.Rect(x - r, y - r, r * 2, r * 2)
            pygame.draw.rect(surf, COLORS["enemy"], rect)
            # HP bar
            hp_w = int((e.hp / e.max_hp) * (TILE - 8))
            hp_rect = pygame.Rect(int(x - (TILE - 8) / 2), int(y - TILE / 2 - 8), hp_w, 6)
            back_rect = pygame.Rect(int(x - (TILE - 8) / 2), int(y - TILE / 2 - 8), TILE - 8, 6)
            pygame.draw.rect(surf, (80,80,80), back_rect)
            pygame.draw.rect(surf, (255, 30, 30), hp_rect)

    def draw_projectiles(self, surf):
        for p in self.projectiles:
            x, y = p.pos
            pygame.draw.circle(surf, COLORS["projectile"], (int(x), int(y)), 5)

    def draw_ui(self, surf):
        pygame.draw.rect(surf, COLORS["ui_panel"], self.ui_rect)
        # info text
        info = f"Level: {self.level_name}    Gold: {self.gold}    Lives: {self.lives}    Time: {int(self.level_time)}s"
        txt = self.font.render(info, True, COLORS["text"])
        surf.blit(txt, (8, SCREEN_H + 8))
        # buttons text
        btn_text = "[1] Arrow Tower (75)   [2] Cannon (125)   [S] Save   [L] Load   [N] Next Level"
        txt2 = self.font.render(btn_text, True, COLORS["text"])
        surf.blit(txt2, (8, SCREEN_H + 36))
        # selection
        if self.selected_tile:
            tx, ty = self.selected_tile
            txr = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
            pygame.draw.rect(surf, (255,255,255), txr, 3)

        if self.selected_tower:
            info = f"Selected: {TOWER_TYPES[self.selected_tower.type_id]['name']}  Lv{self.selected_tower.level}  Upgrade: {self.selected_tower.get_props()['upgrade_cost']}"
            txt3 = self.font.render(info, True, COLORS["text"])
            surf.blit(txt3, (8, SCREEN_H + 56))

    # ---------- INPUT ----------
    def handle_mouse_down(self, pos, button):
        # left click: place or select
        tile = self.tile_from_pos(pos)
        if tile is None:
            return
        tx, ty = tile
        self.selected_tile = (tx, ty)
        # check if there's a tower here
        for t in self.towers:
            if t.tx == tx and t.ty == ty:
                self.selected_tower = t
                return
        self.selected_tower = None

    def handle_mouse_up(self, pos, button):
        # right-click to sell if tower selected
        if button == 3:  # right
            if self.selected_tower:
                refund = self.sell_tower(self.selected_tower)
                self.selected_tower = None
        # left-click in UI area ignored already

    def handle_key(self, key):
        if key == pygame.K_1:
            if self.selected_tile:
                tx, ty = self.selected_tile
                ok, msg = self.place_tower(tx, ty, "arrow")
                # small feedback
                print(msg)
        elif key == pygame.K_2:
            if self.selected_tile:
                tx, ty = self.selected_tile
                ok, msg = self.place_tower(tx, ty, "cannon")
                print(msg)
        elif key == pygame.K_s:
            self.save_game("td_save.json")
            print("Saved to td_save.json")
        elif key == pygame.K_l:
            self.load_game("td_save.json")
            print("Loaded td_save.json")
        elif key == pygame.K_n:
            # next level (force)
            self.next_level()
        elif key == pygame.K_u:
            if self.selected_tower:
                ok, msg = self.upgrade_tower(self.selected_tower)
                print(msg)
        elif key == pygame.K_p:
            self.paused = not self.paused

    def next_level(self):
        self.level_index = (self.level_index + 1) % len(LEVELS)
        self.load_level(self.level_index)

    # ---------- SAVE / LOAD ----------
    def save_game(self, filename):
        data = {
            "level_index": self.level_index,
            "gold": self.gold,
            "lives": self.lives,
            "towers": [{"tx": t.tx, "ty": t.ty, "type_id": t.type_id, "level": t.level} for t in self.towers],
            "level_time": self.level_time,
            "spawned_indices": list(self.spawned_indices),
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def load_game(self, filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except Exception as e:
            print("Load failed:", e)
            return
        self.level_index = data.get("level_index", 0)
        self.load_level(self.level_index)
        self.gold = data.get("gold", STARTING_GOLD)
        self.lives = data.get("lives", STARTING_LIVES)
        self.towers = [Tower(tx=t["tx"], ty=t["ty"], type_id=t["type_id"], level=t.get("level", 1)) for t in data.get("towers", [])]
...         self.level_time = data.get("level_time", 0.0)
...         self.spawned_indices = set(data.get("spawned_indices", []))
... 
...     # ---------- MAIN LOOP ----------
...     def run(self):
...         while self.running:
...             dt = self.clock.tick(FPS) / 1000.0
...             for ev in pygame.event.get():
...                 if ev.type == pygame.QUIT:
...                     self.running = False
...                 elif ev.type == pygame.MOUSEBUTTONDOWN:
...                     self.handle_mouse_down(ev.pos, ev.button)
...                 elif ev.type == pygame.MOUSEBUTTONUP:
...                     self.handle_mouse_up(ev.pos, ev.button)
...                 elif ev.type == pygame.KEYDOWN:
...                     if ev.key == pygame.K_ESCAPE:
...                         self.running = False
...                     else:
...                         self.handle_key(ev.key)
... 
...             self.update(dt)
... 
...             # draw
...             self.screen.fill(COLORS["bg"])
...             self.draw_grid(self.screen)
...             self.draw_towers(self.screen)
...             self.draw_enemies(self.screen)
...             self.draw_projectiles(self.screen)
...             self.draw_ui(self.screen)
... 
...             pygame.display.flip()
... 
...         pygame.quit()
...         print("Game over. Thanks for playing!")
... 
... # ---------- ENTRY POINT ----------
... if __name__ == "__main__":
...     g = Game()
...     g.run()
