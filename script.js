const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const TILE = 64;
const SCREEN_W = 12 * TILE;
const SCREEN_H = 8 * TILE;
const FPS = 60;

const COLORS = {
  bg: '#1e1e1e',
  path: '#5b3d1e',
  ground: '#477a47',
  tower: '#b3b32a',
  tower_upgrade: '#d4c137',
  enemy: '#d62828',
  projectile: '#e6e66a',
  text: '#ffffff',
  grid: '#333333'
};

const LEVELS = [
  {
    name: 'Greenway I',
    path: [
      [0, 3], [1, 3], [2, 3], [3, 3], [4, 3], [5, 3],
      [6, 3], [7, 3], [8, 3], [9, 3], [10, 3], [11, 3]
    ],
    waves: [['grunt', 8, 0.9], ['grunt', 10, 0.7], ['tough', 3, 1.5]]
  }
];

const ENEMY_TYPES = {
  grunt: { hp: 30, speed: 40, reward: 8 },
  tough: { hp: 100, speed: 24, reward: 25 }
};

const TOWER_TYPES = {
  arrow: { cost: 75, range: TILE * 3, damage: 10, rate: 0.6, upgrade: 60 },
  cannon: { cost: 125, range: TILE * 2.5, damage: 40, rate: 1.2, upgrade: 100 }
};

class Enemy {
  constructor(type, path) {
    const info = ENEMY_TYPES[type];
    this.type = type;
    this.hp = info.hp;
    this.maxHp = info.hp;
    this.speed = info.speed;
    this.reward = info.reward;
    this.path = path.map(([x, y]) => [x * TILE + TILE / 2, y * TILE + TILE / 2]);
    this.index = 0;
    this.pos = [...this.path[0]];
    this.alive = true;
  }

  update(dt) {
    if (!this.alive || this.index >= this.path.length - 1) return;
    const [tx, ty] = this.path[this.index + 1];
    const [x, y] = this.pos;
    const vx = tx - x, vy = ty - y;
    const dist = Math.hypot(vx, vy);
    const step = this.speed * dt;
    if (dist <= step) {
      this.pos = [tx, ty];
      this.index++;
    } else {
      this.pos = [x + (vx / dist) * step, y + (vy / dist) * step];
    }
  }
}

class Tower {
  constructor(tx, ty, type) {
    this.tx = tx;
    this.ty = ty;
    this.type = type;
    this.level = 1;
    this.cooldown = 0;
  }

  props() {
    const base = TOWER_TYPES[this.type];
    const dmg = base.damage * (1 + 0.5 * (this.level - 1));
    const rng = base.range * (1 + 0.15 * (this.level - 1));
    const rate = Math.max(0.15, base.rate * (1 - 0.1 * (this.level - 1)));
    return { damage: dmg, range: rng, rate: rate };
  }
}

class Projectile {
  constructor(x, y, target, dmg) {
    this.x = x;
    this.y = y;
    this.target = target;
    this.dmg = dmg;
    this.alive = true;
  }

  update(dt) {
    if (!this.target.alive) {
      this.alive = false;
      return;
    }
    const [tx, ty] = this.target.pos;
    const vx = tx - this.x, vy = ty - this.y;
    const dist = Math.hypot(vx, vy);
    const spd = 300;
    if (dist < spd * dt) {
      this.x = tx;
      this.y = ty;
      this.target.hp -= this.dmg;
      if (this.target.hp <= 0) this.target.alive = false;
      this.alive = false;
    } else {
      this.x += (vx / dist) * spd * dt;
      this.y += (vy / dist) * spd * dt;
    }
  }
}

class Game {
  constructor() {
    this.level = LEVELS[0];
    this.path = this.level.path;
    this.gold = 200;
    this.lives = 20;
    this.enemies = [];
    this.towers = [];
    this.projectiles = [];
    this.spawnIndex = 0;
    this.time = 0;

    canvas.addEventListener('click', (e) => this.onClick(e));
  }

  tileFromPos(x, y) {
    if (x > SCREEN_W || y > SCREEN_H) return null;
    return [Math.floor(x / TILE), Math.floor(y / TILE)];
  }

  onClick(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    const tile = this.tileFromPos(x, y);
    if (!tile) return;
    const [tx, ty] = tile;
    for (let t of this.towers) {
      if (t.tx === tx && t.ty === ty) return;
    }
    const cost = TOWER_TYPES.arrow.cost;
    if (this.gold >= cost && !this.path.some(([px, py]) => px === tx && py === ty)) {
      this.gold -= cost;
      this.towers.push(new Tower(tx, ty, 'arrow'));
    }
  }

  spawnEnemies(dt) {
    this.time += dt;
    const waves = this.level.waves;
    const w = waves[0];
    const [etype, count, interval] = w;
    if (this.spawnIndex < count && this.time >= this.spawnIndex * interval) {
      this.enemies.push(new Enemy(etype, this.path));
      this.spawnIndex++;
    }
  }

  update(dt) {
    this.spawnEnemies(dt);
    this.enemies.forEach(e => e.update(dt));
    this.enemies = this.enemies.filter(e => {
      if (e.index >= e.path.length - 1) {
        this.lives--;
        return false;
      }
      return e.alive;
    });

    for (let t of this.towers) {
      t.cooldown -= dt;
      const props = t.props();
      const tx = t.tx * TILE + TILE / 2, ty = t.ty * TILE + TILE / 2;
      if (t.cooldown <= 0) {
        for (let e of this.enemies) {
          const [ex, ey] = e.pos;
          const d = Math.hypot(ex - tx, ey - ty);
          if (d <= props.range) {
            this.projectiles.push(new Projectile(tx, ty, e, props.damage));
            t.cooldown = props.rate;
            break;
          }
        }
      }
    }

    this.projectiles.forEach(p => p.update(dt));
    this.projectiles = this.projectiles.filter(p => p.alive);
  }

  drawRect(x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  }

  drawText(text, x, y) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '14px monospace';
    ctx.fillText(text, x, y);
  }

  draw() {
    this.drawRect(0, 0, SCREEN_W, SCREEN_H, COLORS.bg);
    for (let y = 0; y < 8; y++) {
      for (let x = 0; x < 12; x++) {
        const tileColor = this.path.some(([px, py]) => px === x && py === y) ? COLORS.path : COLORS.ground;
        this.drawRect(x * TILE, y * TILE, TILE, TILE, tileColor);
        ctx.strokeStyle = COLORS.grid;
        ctx.strokeRect(x * TILE, y * TILE, TILE, TILE);
      }
    }
    for (let t of this.towers) {
      const color = t.level > 1 ? COLORS.tower_upgrade : COLORS.tower;
      this.drawRect(t.tx * TILE + 8, t.ty * TILE + 8, TILE - 16, TILE - 16, color);
    }
    for (let e of this.enemies) {
      const [x, y] = e.pos;
      this.drawRect(x - 12, y - 12, 24, 24, COLORS.enemy);
    }
    for (let p of this.projectiles) {
      this.drawRect(p.x - 3, p.y - 3, 6, 6, COLORS.projectile);
    }
    this.drawText(`Gold: ${this.gold}  Lives: ${this.lives}`, 10, SCREEN_H + 20);
  }
}

const game = new Game();
let last = performance.now();

function loop(now) {
  const dt = (now - last) / 1000;
  last = now;
  game.update(dt);
  game.draw();
  if (game.lives > 0) requestAnimationFrame(loop);
  else game.drawText('GAME OVER', SCREEN_W / 2 - 40, SCREEN_H / 2);
}

requestAnimationFrame(loop);
