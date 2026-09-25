#!/usr/bin/env python3
"""Bola: cobre os cinco modos de desenho e retrata a mola do impacto.

Sintaxe boa não diz se a bola some, estoura ou vira folha de papel. Aqui o
jogo roda no node com um DOM de mentira, cada modo é forçado por um gancho, e
as fileiras que o desenho emitiu voltam como ASCII — dá para VER o squash.
"""
import json, os, re, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(RAIZ, "pong.html"), encoding="utf-8").read()
js = src.split("<script>")[1].split("</script>")[0]

chk = open(os.path.join(RAIZ, "check.py"), encoding="utf-8").read()
SHIM = chk.split('_SHIM = r"""')[1].split('"""')[0]

GANCHO = r"""
  globalThis.__bola = (o) => {
    S.phase = "play";
    fire.on = !!o.fire;
    roleta.on = !!o.roleta; if (o.roleta) roleta.t = 0.3;
    BOLA = o.gum ? BS * 4 : BS;
    ball.hit = o.hit === undefined ? 0 : o.hit;
    ball.va = o.va === undefined ? 300 : o.va;
    ball.vb = o.vb === undefined ? 140 : o.vb;
    ball.a = LEN / 2; ball.b = SPAN / 2;
  };
  globalThis.__forma = () => { const F = formaDaBola(); return [F.p, F.q, F.ang, F.reta ? 1 : 0]; };
  /* O contexto do DOM de mentira e um fantasma: nao da para grampear o
     fillRect. Entao o retrato sai da geometria de verdade — as mesmas
     fileiras que o discoTorto emitiria — e o draw() roda junto so para
     provar que o modo nao estoura. */
  globalThis.__pintar = (o) => {
    __bola(o); draw();
    const F = formaDaBola();
    const L = F.reta ? [] : spansTortos(F.p, F.q, F.ang);
    return JSON.stringify({ spans: L, p: F.p, q: F.q, reta: F.reta });
  };
  function frame(now) {"""

js = js.replace("function frame(now) {", GANCHO, 1)

MODOS = [
    ("limpa parada",   {"va": 260, "vb": 0}),
    ("limpa veloz",    {"va": 600, "vb": 180}),
    ("no impacto",     {"hit": 0.62}),
    ("apos impacto",   {"hit": 0.50}),
    ("fogo",           {"fire": True}),
    ("roleta",         {"roleta": True}),
    ("chiclete",       {"gum": True}),
    ("chiclete batido",{"gum": True, "hit": 0.62}),
    ("chiclete mola",  {"gum": True, "hit": 0.45}),
]

prog = SHIM + "\n(function(){\n" + js + "\n})()\n" + """
const saida = {};
if (globalThis.__erro) { process.stdout.write(JSON.stringify({fatal: __erro})); process.exit(0); }
for (let k = 1; k <= 40; k++) { __rel = k * 16.7; if (__raf) __raf(__rel); }
const MODOS = %s;
for (const [nome, o] of MODOS) {
  try {
    const pint = JSON.parse(__pintar(o));   // pinta primeiro: __forma le o estado ja aplicado
    saida[nome] = { forma: __forma(), pint, erro: __erro || null };
    globalThis.__erro = null;
  } catch (e) { saida[nome] = { erro: String(e && e.stack || e) }; }
}
// e a mola inteira, quadro a quadro, para ver o arco
const mola = { seca: [], goma: [] };
for (const [nome, gum] of [["seca", false], ["goma", true]]) {
  for (let i = 0; i <= 20; i++) {
    __bola({ gum, hit: 0.62 * (1 - i / 20), va: 300, vb: 0 });
    const F = __forma();
    mola[nome].push([Math.round(F[0] * 100) / 100, Math.round(F[1] * 100) / 100]);
  }
}
saida.__mola = mola;
process.stdout.write(JSON.stringify(saida));
""" % json.dumps(MODOS)

exe = shutil.which("node") or shutil.which("nodejs")
if not exe:
    print("sem node — nao da para testar"); sys.exit(1)
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(prog); caminho = f.name
try:
    r = subprocess.run([exe, caminho], capture_output=True, text=True, timeout=120)
finally:
    os.unlink(caminho)
if r.returncode != 0:
    print("node falhou:\n", r.stderr[:1500]); sys.exit(1)
res = json.loads(r.stdout)
if "fatal" in res:
    print("erro ja na abertura:", res["fatal"][:400]); sys.exit(1)

def desenhar(pint, W=84, H=34):
    """Retrato da silhueta: uma fileira por linha da elipse."""
    spans, p, q = pint["spans"], pint["p"], pint["q"]
    if pint["reta"]:                      # parada, o disco e redondo
        spans = []
        for j in range(-int(q) - 1, int(q) + 2):
            k = 1 - ((j + 0.5) / q) ** 2
            if k > 0:
                meia = p * (k ** 0.5)
                spans.append([j, -meia, meia])
    if not spans: return ["  (vazia)"]
    grade = [[" "] * W for _ in range(H)]
    for (j, xa, xb) in spans:
        i = int(round(j + H / 2))
        if not (0 <= i < H): continue
        for x in range(int(round(xa + W / 2)), int(round(xb + W / 2))):
            if 0 <= x < W: grade[i][x] = "#"
    return ["  " + "".join(l).rstrip() for l in grade if "#" in l]

ruim = False
print("=" * 68)
for nome, _ in MODOS:
    d = res[nome]
    if d.get("erro"):
        ruim = True
        print(f"\n{nome}: ERRO -> {d['erro'][:200]}"); continue
    p, q, ang, reta = d["forma"]
    n = len(d["pint"]["spans"]) or (1 if d["pint"]["reta"] else 0)
    print(f"\n{nome}:  p={p:.1f} q={q:.1f} ang={ang:.2f}rad  "
          f"razao={p/q:.2f}  {'(reto)' if reta else '(torto)'}  {n} fileiras")
    if n == 0:
        ruim = True; print("  BOLA INVISIVEL"); continue
    for l in desenhar(d["pint"])[:30]: print(l)

print("\n" + "=" * 68)
print("A MOLA DO IMPACTO (semieixo no rumo da viagem x perpendicular)\n")
for nome, serie in res["__mola"].items():
    print(f"  {nome}:")
    marca = "".join("-" if s[0] < s[1] else "+" for s in serie)
    print(f"    achata/estica: {marca}   (- achatada, + esticada)")
    print("    razao: " + " ".join(f"{s[0]/s[1]:.2f}" for s in serie[:11]))
    picos = [i for i in range(1, len(serie) - 1)
             if (serie[i][0] - serie[i-1][0]) * (serie[i+1][0] - serie[i][0]) < 0]
    print(f"    inversoes de sentido: {len(picos)}  "
          f"{'(mola com repique)' if len(picos) >= 2 else '(decaimento seco)'}")
print()
print("FALHOU" if ruim else "PASSOU")
sys.exit(1 if ruim else 0)
