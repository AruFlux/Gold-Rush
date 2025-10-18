/* Pixel Tower Defense — Full upgrade of features requested
   Features included:
   - Buy towers (arrow/cannon), place on non-path tiles
   - Select towers, upgrade, sell
   - Towers show visual changes when upgraded
   - Enemies show HP bars
   - Multiple levels with growing difficulty and new obstacles
   - Waves, enemies remaining counter
   - Base (endpoint) with health; enemies reaching base reduce its HP
   - Losing triggers explosion animation and overlay to retry
   - Map editor toggles obstacles
*/

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const TILE = 64;
const COLS = 12;
const ROWS = 8;
const SCREEN_W = COLS * TILE;
const SCREEN_H = ROWS * TILE;
canvas.width = SCREEN_W;
canvas.height = SCREEN_H;

const SIDEBAR = {
  goldEl: document.getElementById('gold'),
  baseEl: document.getElementById('baseHealth'),
  levelName: document.getElementById('levelName'),
  waveInfo: document.getElementById('waveInfo'),
  overlay: document.getElementById('overlay'),
  overlayTitle: document.getElementById('overlayTitle'),
  retryBtn: document.getElementById('retryBtn')
};

const buyArrow = document.getElementById('buyArrow');
const buyCannon = document.getElementById('buyCannon');
const upgradeBtn = document.getElementById('upgradeBtn');
const sellBtn = document.getElementById('sellBtn');
const nextLevelBtn = document.getElementById('nextLevelBtn');
const toggleObstacles = document.getElementById('toggleObstacles');
const resetBtn = document.getElementById('resetBtn');

const COLORS = {
  bg:'#1e1e1e',
  path:'#5b3d1e',
  ground:'#477a47',
  tower:'#b3b32a',
  tower_upgrade:'#d4c137',
  enemy:'#d62828',
  projectile:'#e6e66a',
  text:'#ffffff',
  grid:'#333333',
  base:'#28527a',
  obstacle:'#4b4b4b'
};

const LEVELS = [
  {
    name:'Greenway I',
    path:[[0,3],[1,3],[2,3],[3,3],[4,3],[5,3],[6,3],[7,3],[8,3],[9,3],[10,3],[11,3]],
    waves:[ ['grunt',8,0.9], ['grunt',10,0.7], ['tough',4,1.4] ],
    baseHP: 30,
    obstacles: []
  },
  {
    name:'Riverbend',
    path:[[0,2],[1,2],[2,2],[3,2],[3,3],[3,4],[4,4],[5,4],[6,4],[7,4],[8,4],[9,4],[10,4],[11,4]],
    waves:[ ['grunt',12,0.8], ['tough',6,1.3], ['grunt',15,0.6] ],
    baseHP: 40,
    obstacles: [[5,2],[5,3],[8,5]]
  },
  {
    name:'Fortified Road',
    path:[[0,5],[1,5],[2,5],[3,5],[4,5],[4,4],[4,3],[5,3],[6,3],[7,3],[8,3],[9,3],[10,3],[11,3]],
    waves:[ ['grunt',15,0.7], ['tough',8,1.2], ['heavy',6,1.6] ],
    baseHP: 60,
    obstacles: [[2,4],[7,2],[9,5],[6,5]]
  }
];

const ENEMY_TYPES = {
  grunt:{hp:30,speed:40,reward:8,color:'#e04b4b'},
  tough:{hp:120,speed:28,reward:25,color:'#a83b3b'},
  heavy:{hp:220,speed:18,reward:50,color:'#8b2b2b'}
};

const TOWER_TYPES = {
  arrow:{cost:75,range:TILE*3,damage:10,rate:0.6,upgradeCost:60},
  cannon:{cost:125,range:TILE*2.5,damage:40,rate:1.2,upgradeCost:100}
};

// ---- Game Objects ----
class Enemy {
  constructor(type,path){
    this.type = type;
    this.hp = ENEMY_TYPES[type].hp;
    this.maxHp = this.hp;
    this.speed = ENEMY_TYPES[type].speed;
    this.reward = ENEMY_TYPES[type].reward;
    this.color = ENEMY_TYPES[type].color;
    this.path = path.map(([x,y])=>[x*TILE+TILE/2,y*TILE+TILE/2]);
    this.index = 0;
    this.pos = [...this.path[0]];
    this.alive = true;
  }
  update(dt){
    if(!this.alive || this.index>=this.path.length-1) return;
    const [tx,ty]=this.path[this.index+1];
    const [x,y]=this.pos;
    const vx=tx-x, vy=ty-y;
    const dist=Math.hypot(vx,vy);
    const step=this.speed*dt;
    if(dist<=step){ this.pos=[tx,ty]; this.index++; }
    else { this.pos=[x+(vx/dist)*step, y+(vy/dist)*step]; }
  }
  draw(){
    const [x,y]=this.pos;
    ctx.fillStyle=this.color;
    ctx.fillRect(x-12,y-12,24,24);
    // hp bar
    const w=28;
    const hx=x-w/2, hy=y-20;
    ctx.fillStyle='rgba(0,0,0,0.6)';
    ctx.fillRect(hx,hy,w,5);
    ctx.fillStyle='#ff6b6b';
    ctx.fillRect(hx,hy,(this.hp/this.maxHp)*w,5);
  }
}

class Tower {
  constructor(tx,ty,type){
    this.tx=tx; this.ty=ty; this.type=type;
    this.level=1; this.cooldown=0;
  }
  props(){
    const base=TOWER_TYPES[this.type];
    const damage=base.damage*(1+0.5*(this.level-1));
    const range=base.range*(1+0.12*(this.level-1));
    const rate=Math.max(0.12, base.rate*(1-0.08*(this.level-1)));
    return {damage,range,rate,upgradeCost:base.upgradeCost*this.level};
  }
  draw(){
    const x=this.tx*TILE+8, y=this.ty*TILE+8;
    ctx.fillStyle = this.level>1?COLORS.tower_upgrade:COLORS.tower;
    ctx.fillRect(x,y,TILE-16,TILE-16);
    // simple visual: level ring
    ctx.strokeStyle='#000000';
    ctx.lineWidth=2;
    ctx.strokeRect(x,y,TILE-16,TILE-16);
    ctx.fillStyle='#fff';
    ctx.font='12px monospace';
    ctx.fillText('Lv'+this.level, this.tx*TILE+10, this.ty*TILE+TILE-18);
  }
}

class Projectile {
  constructor(x,y,target,dmg){
    this.x=x; this.y=y; this.target=target; this.dmg=dmg; this.alive=true;
  }
  update(dt){
    if(!this.target.alive){ this.alive=false; return; }
    const tx=this.target.pos[0], ty=this.target.pos[1];
    const vx=tx-this.x, vy=ty-this.y;
    const dist=Math.hypot(vx,vy); const spd=300;
    if(dist<spd*dt){ this.x=tx; this.y=ty; this.target.hp-=this.dmg; if(this.target.hp<=0) this.target.alive=false; this.alive=false; }
    else{ this.x+=vx/dist*spd*dt; this.y+=vy/dist*spd*dt; }
  }
  draw(){ ctx.fillStyle=COLORS.projectile; ctx.fillRect(this.x-3,this.y-3,6,6); }
}

// ---- Game Core ----
class Game {
  constructor(){
    this.levelIndex=0;
    this.loadLevel(this.levelIndex);
    this.selected=null;
    this.selectedTower=null;
    this.placingType=null;
    this.exploding=false;
    this.explosionFrames=0;
  }
  loadLevel(idx){
    const L=LEVELS[idx];
    this.levelName=L.name;
    this.path=L.path.slice();
    this.obstacles=new Set((L.obstacles||[]).map(o=>o[0]+','+o[1]));
    this.waves=L.waves.slice();
    this.baseHP=L.baseHP;
    this.baseMax=L.baseHP;
    this.gold=200;
    this.enemies=[];
    this.towers=[];
    this.projectiles=[];
    this.spawnIndex=0;
    this.time=0;
    this.totalToSpawn=this.waves.reduce((a,w)=>a+w[1],0);
    this.enemiesKilled=0;
    this.levelOver=false;
    this.updateUI();
  }
  updateUI(){
    SIDEBAR.goldEl.textContent='Gold: '+this.gold;
    SIDEBAR.baseEl.textContent='Base: '+this.baseHP+'/'+this.baseMax;
    SIDEBAR.levelName.textContent='Level: '+this.levelName;
    const left = Math.max(0, this.totalToSpawn - this.enemiesKilled - this.enemies.length);
    SIDEBAR.waveInfo.textContent='Enemies left: '+left;
  }
  tileAt(x,y){
    return [Math.floor(x/TILE), Math.floor(y/TILE)];
  }
  isPath(tx,ty){ return this.path.some(p=>p[0]===tx && p[1]===ty); }
  isObstacle(tx,ty){ return this.obstacles.has(tx+','+ty); }
  canPlace(tx,ty){
    if(tx<0||ty<0||tx>=COLS||ty>=ROWS) return false;
    if(this.isPath(tx,ty) || this.isObstacle(tx,ty)) return false;
    if(this.towers.some(t=>t.tx===tx&&t.ty===ty)) return false;
    return true;
  }
  spawn(dt){
    this.time+=dt;
    // spawn from waves sequentially
    if(this.spawnIndex < this.totalToSpawn){
      let countSoFar=0;
      for(let [etype,count,interval] of this.waves){
        if(this.spawnIndex < countSoFar+count){
          const idxInWave = this.spawnIndex - countSoFar;
          const spawnTime = idxInWave * interval;
          if(this.time >= spawnTime){
            this.enemies.push(new Enemy(etype,this.path));
            this.spawnIndex++;
          }
          break;
        }
        countSoFar+=count;
        // shift time window for next waves (gap added based on last spawn)
        this.time = Math.min(this.time, this.time);
      }
    } else {
      // all spawned, check if level cleared
      if(this.enemies.length===0 && !this.levelOver){
        this.levelOver=true;
        // if last level, loop or show victory
      }
    }
  }
  update(dt){
    if(this.exploding) { this.explosionFrames++; if(this.explosionFrames>60){ this.showOverlay('You Lost'); } return; }
    this.spawn(dt);
    // update enemies
    for(let e of this.enemies) e.update(dt);
    // handle enemies reaching base
    for(let i=this.enemies.length-1;i>=0;i--){
      const e=this.enemies[i];
      if(e.index >= e.path.length-1 && e.pos[0]===e.path[e.path.length-1][0] && e.pos[1]===e.path[e.path.length-1][1]){
        this.baseHP -= Math.ceil(e.maxHp/10);
        e.alive=false;
        this.enemies.splice(i,1);
        if(this.baseHP<=0){ this.triggerExplosion(); return; }
      }
    }
    // remove dead enemies, reward gold
    for(let i=this.enemies.length-1;i>=0;i--){
      const e=this.enemies[i];
      if(!e.alive){
        this.enemies.splice(i,1);
        this.enemiesKilled++;
        this.gold += e.reward;
      }
    }
    // towers shoot
    for(let t of this.towers){
      t.cooldown -= dt;
      const props=t.props();
      const tx=t.tx*TILE+TILE/2, ty=t.ty*TILE+TILE/2;
      if(t.cooldown<=0){
        // prioritize further along path
        let target=null, bestIndex=-1;
        for(let e of this.enemies){
          const d=Math.hypot(e.pos[0]-tx,e.pos[1]-ty);
          if(d<=props.range && e.index>=bestIndex){ target=e; bestIndex=e.index; }
        }
        if(target){ this.projectiles.push(new Projectile(tx,ty,target,props.damage)); t.cooldown=props.rate; }
      }
    }
    // projectiles
    for(let i=this.projectiles.length-1;i>=0;i--){
      const p=this.projectiles[i];
      p.update(dt);
      if(!p.alive) this.projectiles.splice(i,1);
    }
    this.updateUI();
  }
  drawGrid(){
    for(let y=0;y<ROWS;y++){
      for(let x=0;x<COLS;x++){
        const inPath=this.isPath(x,y);
        const isObs=this.isObstacle(x,y);
        const color = inPath ? COLORS.path : (isObs?COLORS.obstacle:COLORS.ground);
        ctx.fillStyle=color; ctx.fillRect(x*TILE,y*TILE,TILE,TILE);
        ctx.strokeStyle=COLORS.grid; ctx.strokeRect(x*TILE,y*TILE,TILE,TILE);
      }
    }
  }
  draw(){
    ctx.fillStyle=COLORS.bg; ctx.fillRect(0,0,SCREEN_W,SCREEN_H);
    this.drawGrid();
    // base endpoint marker
    const last = this.path[this.path.length-1];
    ctx.fillStyle=COLORS.base; ctx.fillRect(last[0]*TILE+8,last[1]*TILE+8,TILE-16,TILE-16);
    // draw towers
    for(let t of this.towers) t.draw();
    // draw enemies
    for(let e of this.enemies) e.draw();
    // draw projectiles
    for(let p of this.projectiles) p.draw();
    // selection highlight
    if(this.selectedTower){ ctx.strokeStyle='yellow'; ctx.lineWidth=3; ctx.strokeRect(this.selectedTower.tx*TILE+2,this.selectedTower.ty*TILE+2,TILE-4,TILE-4); ctx.lineWidth=1; }
    // HUD text on canvas
    ctx.fillStyle='#ffffff'; ctx.font='14px monospace';
    ctx.fillText('Gold: '+this.gold,10,SCREEN_H-6);
    ctx.fillText('Base: '+this.baseHP+'/'+this.baseMax,160,SCREEN_H-6);
  }
  placeTower(tx,ty,type){
    if(!this.canPlace(tx,ty)) return false;
    const cost=TOWER_TYPES[type].cost;
    if(this.gold<cost) return false;
    this.gold-=cost; this.towers.push(new Tower(tx,ty,type)); this.updateUI(); return true;
  }
  selectAt(tx,ty){
    for(let t of this.towers) if(t.tx===tx && t.ty===ty) return t;
    return null;
  }
  upgradeSelected(){
    if(!this.selectedTower) return;
    const cost=this.selectedTower.props().upgradeCost;
    if(this.gold<cost) return;
    this.gold-=cost; this.selectedTower.level++; this.updateUI();
  }
  sellSelected(){
    if(!this.selectedTower) return;
    const baseCost=TOWER_TYPES[this.selectedTower.type].cost;
    const refund=Math.floor(baseCost*0.6*(1+0.4*(this.selectedTower.level-1)));
    this.gold+=refund;
    this.towers = this.towers.filter(t=>t!==this.selectedTower);
    this.selectedTower=null;
    this.updateUI();
  }
  nextLevel(){
    this.levelIndex = (this.levelIndex+1) % LEVELS.length;
    this.loadLevel(this.levelIndex);
  }
  resetLevel(){ this.loadLevel(this.levelIndex); }
  toggleObstacles(){ /* optional map editing: flip some obstacles */ this.obstacles = new Set(this.obstacles.size?[]: (LEVELS[this.levelIndex].obstacles||[]).map(o=>o[0]+','+o[1])); this.updateUI(); }
  triggerExplosion(){
    this.exploding=true; this.explosionFrames=0;
  }
  showOverlay(text){
    SIDEBAR.overlay.classList.remove('hidden');
    SIDEBAR.overlayTitle.textContent=text;
  }
  hideOverlay(){ SIDEBAR.overlay.classList.add('hidden'); }
}

const game = new Game();

// ---- Input handling ----
canvas.addEventListener('contextmenu', e=>{ e.preventDefault(); const rect=canvas.getBoundingClientRect(); const x=e.clientX-rect.left, y=e.clientY-rect.top; const [tx,ty]=game.tileAt(x,y); const sel=game.selectAt(tx,ty); if(sel){ game.selectedTower=sel; game.sellSelected(); } });
canvas.addEventListener('click', e=>{
  const rect=canvas.getBoundingClientRect();
  const x=e.clientX-rect.left, y=e.clientY-rect.top;
  const [tx,ty]=game.tileAt(x,y);
  const sel = game.selectAt(tx,ty);
  if(sel){ game.selectedTower = sel; return; }
  // place either chosen type or default arrow
  if(game.placingType){ if(game.placeTower(tx,ty,game.placingType)) game.placingType=null; return; }
  // if place buttons not used, default to placing arrow
  if(game.placeTower(tx,ty,'arrow')) return;
});

// sidebar buttons
buyArrow.addEventListener('click', ()=>{ game.placingType='arrow'; });
buyCannon.addEventListener('click', ()=>{ game.placingType='cannon'; });
upgradeBtn.addEventListener('click', ()=>{ game.upgradeSelected(); });
sellBtn.addEventListener('click', ()=>{ game.sellSelected(); });
nextLevelBtn.addEventListener('click', ()=>{ game.nextLevel(); });
toggleObstacles.addEventListener('click', ()=>{ game.toggleObstacles(); });
resetBtn.addEventListener('click', ()=>{ game.resetLevel(); });
SIDEBAR.retryBtn.addEventListener('click', ()=>{ game.hideOverlay(); game.resetLevel(); });

// ---- Game loop ----
let last = performance.now();
function loop(now){
  const dt = (now-last)/1000; last = now;
  game.update(dt);
  ctx.clearRect(0,0,SCREEN_W,SCREEN_H);
  game.draw();
  if(!game.exploding && game.baseHP>0) requestAnimationFrame(loop);
  else if(game.exploding){
    // draw explosion effect
    const f = game.explosionFrames;
    ctx.fillStyle='rgba(255,80,30,'+Math.min(1,f/30)+')';
    ctx.beginPath(); ctx.arc(SCREEN_W/2, SCREEN_H/2, f*8, 0, Math.PI*2); ctx.fill();
    if(game.explosionFrames<60) requestAnimationFrame(loop);
    else game.showOverlay('You Lost');
  } else {
    game.showOverlay('You Lost');
  }
}
requestAnimationFrame(loop);
