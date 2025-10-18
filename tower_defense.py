from js import document, window, canvas
import math, random, asyncio, json

# ---------- CONFIG ----------
TILE = 64
SCREEN_W = 12 * TILE
SCREEN_H = 8 * TILE
FPS = 60

ctx = canvas.getContext("2d")

# ---------- COLORS ----------
COLORS = {
    "bg": "#1e1e1e",
    "path": "#5b3d1e",
    "ground": "#477a47",
    "tower": "#b3b32a",
    "tower_upgrade": "#d4c137",
    "enemy": "#d62828",
    "projectile": "#e6e66a",
    "text": "#ffffff",
    "grid": "#333333"
}

# ---------- GAME DATA ----------
LEVELS = [
    {
        "name": "Greenway I",
        "path": [(0,3),(1,3),(2,3),(3,3),(4,3),(5,3),(6,3),(7,3),(8,3),(9,3),(10,3),(11,3)],
        "waves": [("grunt",8,0.9),("grunt",10,0.7),("tough",3,1.5)],
    }
]

ENEMY_TYPES = {
    "grunt": {"hp": 30, "speed": 40, "reward": 8},
    "tough": {"hp": 100, "speed": 24, "reward": 25},
}

TOWER_TYPES = {
    "arrow": {"cost": 75, "range": TILE*3, "damage": 10, "rate": 0.6, "upgrade": 60},
    "cannon": {"cost": 125, "range": TILE*2.5, "damage": 40, "rate": 1.2, "upgrade": 100},
}

# ---------- CLASSES ----------
class Enemy:
    def __init__(self, etype, path):
        info = ENEMY_TYPES[etype]
        self.type = etype
        self.hp = info["hp"]
        self.max_hp = info["hp"]
        self.speed = info["speed"]
        self.reward = info["reward"]
        self.path = [(x*TILE+TILE/2, y*TILE+TILE/2) for x,y in path]
        self.index = 0
        self.pos = self.path[0]
        self.alive = True

    def update(self, dt):
        if not self.alive or self.index >= len(self.path)-1: return
        tx, ty = self.path[self.index+1]
        x, y = self.pos
        vx, vy = tx-x, ty-y
        dist = math.hypot(vx, vy)
        step = self.speed * dt
        if dist <= step:
            self.pos = (tx, ty)
            self.index += 1
        else:
            self.pos = (x + vx/dist*step, y + vy/dist*step)

class Tower:
    def __init__(self, tx, ty, tid):
        self.tx, self.ty = tx, ty
        self.type = tid
        self.level = 1
        self.cooldown = 0

    def props(self):
        base = TOWER_TYPES[self.type]
        dmg = base["damage"] * (1 + 0.5*(self.level-1))
        rng = base["range"] * (1 + 0.15*(self.level-1))
        rate = base["rate"] * (1 - 0.1*(self.level-1))
        return {"damage": dmg, "range": rng, "rate": max(0.15, rate)}

class Projectile:
    def __init__(self, x, y, target, dmg):
        self.x, self.y = x, y
        self.target = target
        self.dmg = dmg
        self.alive = True

    def update(self, dt):
        if not self.target.alive: self.alive = False; return
        tx, ty = self.target.pos
        vx, vy = tx-self.x, ty-self.y
        dist = math.hypot(vx, vy)
        spd = 300
        if dist < spd*dt:
            self.x, self.y = tx, ty
            self.target.hp -= self.dmg
            if self.target.hp <= 0: self.target.alive = False
            self.alive = False
        else:
            self.x += vx/dist*spd*dt
            self.y += vy/dist*spd*dt

# ---------- GAME ----------
class Game:
    def __init__(self):
        self.level = LEVELS[0]
        self.path = self.level["path"]
        self.gold = 200
        self.lives = 20
        self.enemies = []
        self.towers = []
        self.projectiles = []
        self.spawn_index = 0
        self.time = 0
        self.mouse_tile = None
        self.selected_tower = None

        canvas.addEventListener("click", self.on_click)

    def tile_from_pos(self, x, y):
        if x>SCREEN_W or y>SCREEN_H: return None
        return (int(x//TILE), int(y//TILE))

    def on_click(self, evt):
        rect = canvas.getBoundingClientRect()
        x, y = evt.clientX - rect.left, evt.clientY - rect.top
        tile = self.tile_from_pos(x, y)
        if not tile: return
        tx, ty = tile
        for t in self.towers:
            if (t.tx, t.ty)==(tx, ty):
                self.selected_tower = t
                return
        cost = TOWER_TYPES["arrow"]["cost"]
        if self.gold >= cost and (tx,ty) not in self.path:
            self.gold -= cost
            self.towers.append(Tower(tx,ty,"arrow"))

    def spawn_enemies(self, dt):
        self.time += dt
        waves = self.level["waves"]
        w = waves[0]
        etype, count, interval = w
        if self.spawn_index < count and self.time >= self.spawn_index*interval:
            self.enemies.append(Enemy(etype, self.path))
            self.spawn_index += 1

    def update(self, dt):
        self.spawn_enemies(dt)
        for e in list(self.enemies):
            e.update(dt)
            if e.index >= len(e.path)-1:
                self.lives -= 1
                e.alive = False
            if not e.alive:
                if e in self.enemies: self.enemies.remove(e)
                self.gold += e.reward
        for t in self.towers:
            t.cooldown -= dt
            props = t.props()
            tx, ty = t.tx*TILE+TILE/2, t.ty*TILE+TILE/2
            if t.cooldown <= 0:
                for e in self.enemies:
                    ex, ey = e.pos
                    d = math.hypot(ex-tx, ey-ty)
                    if d <= props["range"]:
                        self.projectiles.append(Projectile(tx,ty,e,props["damage"]))
                        t.cooldown = props["rate"]
                        break
        for p in list(self.projectiles):
            p.update(dt)
            if not p.alive: self.projectiles.remove(p)

    def draw_rect(self, x,y,w,h,color):
        ctx.fillStyle = color
        ctx.fillRect(x,y,w,h)

    def draw_text(self, text,x,y):
        ctx.fillStyle = COLORS["text"]
        ctx.font = "14px monospace"
        ctx.fillText(text, x, y)

    def draw(self):
        self.draw_rect(0,0,SCREEN_W,SCREEN_H,COLORS["bg"])
        for y in range(8):
            for x in range(12):
                tile_color = COLORS["path"] if (x,y) in self.path else COLORS["ground"]
                self.draw_rect(x*TILE,y*TILE,TILE,TILE,tile_color)
                ctx.strokeStyle = COLORS["grid"]
                ctx.strokeRect(x*TILE,y*TILE,TILE,TILE)
        for t in self.towers:
            color = COLORS["tower_upgrade"] if t.level>1 else COLORS["tower"]
            self.draw_rect(t.tx*TILE+8,t.ty*TILE+8,TILE-16,TILE-16,color)
        for e in self.enemies:
            x,y = e.pos
            self.draw_rect(x-12,y-12,24,24,COLORS["enemy"])
        for p in self.projectiles:
            self.draw_rect(p.x-3,p.y-3,6,6,COLORS["projectile"])
        self.draw_text(f"Gold: {self.gold}  Lives: {self.lives}",10,SCREEN_H+20)

    async def run(self):
        last = window.performance.now()
        while self.lives>0:
            now = window.performance.now()
            dt = (now-last)/1000.0
            last = now
            self.update(dt)
            self.draw()
            await asyncio.sleep(1/FPS)
        self.draw_text("GAME OVER", SCREEN_W/2-40, SCREEN_H/2)

game = Game()
asyncio.ensure_future(game.run())
