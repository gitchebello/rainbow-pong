"""Ponto retido: o anfitriao espera a defesa do convidado antes de marcar."""
import io, re, sys, os
from py_mini_racer import MiniRacer

html = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pong.html"), encoding="utf-8").read()
js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)

m = MiniRacer()
m.eval(r"""
function fantasma(n){const f=function(){return fantasma(n+"()")};return new Proxy(f,{
 get(t,p){if(p===Symbol.toPrimitive||p==="valueOf")return()=>0;if(p==="toString")return()=>"";
  if(p===Symbol.iterator)return function*(){};if(p==="length")return 0;
  if(p==="matches"||p==="hidden")return false;return fantasma(n+"."+String(p));},
 set(){return true},has(){return true},
 apply(){return fantasma(n+"()")},construct(){return fantasma(n+"{}")}});}
var document=fantasma("document"); var window=globalThis;
globalThis.innerWidth=900; globalThis.innerHeight=600;
var location={protocol:"http:",host:"x",pathname:"/pong/",href:"http://x/pong/"};
var localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
var matchMedia=()=>({matches:false,addEventListener:()=>{}});
var addEventListener=()=>{}; var removeEventListener=()=>{};
var __raf=null; var requestAnimationFrame=cb=>{__raf=cb;return 0};
var __rel=0; var performance={now:()=>__rel};
var setTimeout=()=>0; var setInterval=()=>0; var clearTimeout=()=>{};
var BroadcastChannel=function(){this.postMessage=()=>{};this.close=()=>{}};
var WebSocket=function(){this.send=()=>{};this.close=()=>{};this.readyState=0};
var navigator={wakeLock:undefined};
var getComputedStyle=()=>({paddingLeft:"0",paddingRight:"0"});
var console={error:(...a)=>{globalThis.__erro=a.map(String).join(" | ")},log:()=>{},warn:()=>{}};
globalThis.__erro=null; globalThis.relatarFalha=e=>{globalThis.__erro=String(e&&e.stack||e)};
""")

gancho = """
  globalThis.__T = {
    salaHost() {
      sala.ws = { readyState: 1, send() {} };
      sala.papel = "anfitriao"; sala.conectado = true;
      sala.id = 1; sala.slot = 0; sala.n = 2;
      sala.membros = { 1: 0, 2: 1 }; sala.atraso = 140;
      S.mode = "2p";
    },
    arena(on) { S.arena = !!on; },
    sairDaSala() { sala.conectado = false; sala.ws = null; sala.canal = null; },
    // bola indo pra raquete 1, que esta longe do ponto de encontro
    montarClassico() {
      S.phase = "play"; S.t = 0; S.score = [0, 0];
      ball.a = LEN / 2; ball.b = 100; ball.va = 420; ball.vb = 0;
      ball.speed = 420; ball.spin = 0; ball.budget = 0; ball.dono = 0;
      pads[1].b = 260; pads[1].destino = 260; pads[1].swing = 0;
    },
    montarArena() {
      S.phase = "play"; S.t = 0; S.score = [0, 0];
      const th = 0;                       // sai pela direita do aro
      ball.a = ARENA_CA(); ball.b = ARENA_CB();
      ball.va = 420; ball.vb = 0; ball.speed = 420; ball.spin = 0; ball.budget = 0;
      ball.dono = 0;
      /* a raquete 1 responde pela direita, mas a copia do anfitriao esta
         atrasada em ~um comprimento de raquete: e o caso do bug. */
      pads[1].b = mArco(-padLen(1) / 2 + 60); pads[1].destino = pads[1].b;
      pads[0].b = mArco(Math.PI * ARENA_R());
    },
    passos(n) { for (let k = 0; k < n; k++) step(DT); },
    espera() { return { on: golEspera.on, quem: golEspera.quem, falhou: golEspera.falhou,
                        t: Math.round(golEspera.t * 1000), janela: Math.round(janelaDefesa() * 1000) }; },
    placar() { return S.score.slice(); },
    fase() { return S.phase; },
    bola() { return { a: Math.round(ball.a), b: Math.round(ball.b),
                      va: Math.round(ball.va), vb: Math.round(ball.vb) }; },
    defesa(j, o) { aceitarDefesa(j, o); },
    thBola() { return Math.atan2(ball.b + BOLA / 2 - ARENA_CB(), ball.a + BOLA / 2 - ARENA_CA()); },
    arcoDe(th) { return mArco(th * ARENA_R()); },
    padLen(j) { return padLen(j); },
    slots() { return [SLOTS[0](), SLOTS[1]()]; },
    diag() { return { falhou: quemFalhou(), deOutro: padDeOutro(quemFalhou()),
                      ativos: jogadoresAtivos(), meu: meuPadSlot(),
                      conect: sala.conectado, papel: sala.papel, cpu: cpuNaArena(),
                      dono: ball.dono, folga: Math.round(folgaRede()),
                      dist: Math.round(Math.hypot(ball.a+BOLA/2-ARENA_CA(), ball.b+BOLA/2-ARENA_CB())),
                      R: Math.round(ARENA_R()) }; }
  };
  function frame(now) {"""
js2 = js.replace("  function frame(now) {", gancho, 1)
m.eval("(function(){\n" + js2 + "\n})()")
m.eval("for(let k=1;k<=60;k++){__rel=k*16.7;if(__raf)__raf(__rel);}")

falhas = []
def eq(nome, got, exp):
    ok = got == exp
    print(("  ok  " if ok else "  XX  ") + nome + f"  ({got!r})")
    if not ok: falhas.append(nome + f" esperava {exp!r}, veio {got!r}")

def diz(nome, cond, extra=""):
    print(("  ok  " if cond else "  XX  ") + nome + ("  " + str(extra) if extra else ""))
    if not cond: falhas.append(nome)

print("\n[1] classico: raquete do convidado atrasada, sem defesa reivindicada")
m.eval("__T.salaHost(); __T.arena(false); __T.montarClassico()")
m.eval("__T.passos(90)")            # 0,75 s: a bola cruza e sai
e = m.eval("JSON.stringify(__T.espera())")
print("      espera:", e)
diz("ponto ficou retido", '"on":true' in e)
eq("placar ainda zerado", m.eval("JSON.stringify(__T.placar())"), "[0,0]")
m.eval("__T.passos(60)")            # meio segundo: a janela fecha
eq("ponto sai quando a janela fecha", m.eval("JSON.stringify(__T.placar())"), "[1,0]")
eq("volta pro saque", m.eval("__T.fase()"), "serve")

print("\n[2] classico: a defesa do convidado chega dentro da janela")
m.eval("__T.montarClassico()")
m.eval("__T.passos(90)")
diz("ponto retido", '"on":true' in m.eval("JSON.stringify(__T.espera())"))
bb = m.eval("__T.bola().b")
m.eval(f"__T.defesa(1, {{ b: {bb} - 20, sw: 0, bb: {bb} }})")
eq("nao pontuou", m.eval("JSON.stringify(__T.placar())"), "[0,0]")
eq("segue no play", m.eval("__T.fase()"), "play")
diz("bola voltou pro outro lado", m.eval("__T.bola().va") < 0, m.eval("JSON.stringify(__T.bola())"))
diz("espera zerada", m.eval("__T.espera()['on']") is False)

print("\n[3] arena: mesma historia no aro")
m.eval("__T.arena(true); __T.montarArena()")
m.eval("__T.passos(60)")
e = m.eval("JSON.stringify(__T.espera())")
print("      espera:", e)
diz("ponto retido na arena", '"on":true' in e)
th = m.eval("__T.thBola()")
arco = m.eval(f"__T.arcoDe({th})")
pl = m.eval("__T.padLen(1)")
m.eval(f"__T.defesa(1, {{ b: {arco - pl/2}, sw: 0, th: {th} }})")
eq("arena: nao pontuou", m.eval("JSON.stringify(__T.placar())"), "[0,0]")
diz("arena: bola voltou pro centro", m.eval("__T.bola().va") < 0,
    m.eval("JSON.stringify(__T.bola())"))

print("\n[4] fora da sala nada muda: o ponto sai na hora")
m.eval("__T.sairDaSala(); __T.arena(false); __T.montarClassico()")
m.eval("__T.passos(90)")
eq("ponto imediato sem sala", m.eval("JSON.stringify(__T.placar())"), "[1,0]")
diz("sem retencao", m.eval("__T.espera()['on']") is False)

print("\n[5] encaixes: arena inverte o eixo b")
m.eval("__T.arena(false)")
c = m.eval("JSON.stringify(__T.slots())")
m.eval("__T.arena(true)")
a = m.eval("JSON.stringify(__T.slots())")
print("      classico:", c, "\n      arena   :", a)
import json
c, a = json.loads(c), json.loads(a)
diz("mesmo eixo a", [c[0][0], c[1][0]] == [a[0][0], a[1][0]])
diz("b trocado", c[0][1] == a[1][1] and c[1][1] == a[0][1])

err = m.eval("globalThis.__erro")
diz("nenhum erro de quadro", not err, err or "")

print("\nRESULTADO:", "FALHOU -> " + "; ".join(falhas) if falhas else "PASSOU")
sys.exit(1 if falhas else 0)
