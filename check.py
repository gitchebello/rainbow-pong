#!/usr/bin/env python3
"""Verificação do Rainbow Pong.

O coração é a compilação real do script com o V8 — o mesmo motor do navegador.
Isso pega TODO erro de sintaxe, inclusive os que uma leitura por expressão
regular não vê: nome declarado duas vezes, palavra reservada, vírgula faltando.
Três travamentos nesta base foram desta família.
"""
import json
import re
import sys

CAMINHO = sys.argv[1] if len(sys.argv) > 1 else "pong.html"

src = open(CAMINHO, encoding="utf-8").read()
js = src.split("<script>")[1].split("</script>")[0]
css = src.split("<style>")[1].split("</style>")[0]
ruim = False

# ── 1. compila com o V8, exatamente como o navegador faz ──
try:
    from py_mini_racer import MiniRacer
    try:
        MiniRacer().eval("new Function(" + json.dumps(js) + ")")
        print("V8: o script compila sem erro de sintaxe")
    except Exception as e:
        ruim = True
        msg = str(e).split("\n")[0]
        print("V8: ERRO DE SINTAXE ->", msg)
        m = re.search(r":(\d+):(\d+)", msg)
        if m:
            ln = int(m.group(1))
            for k, linha in enumerate(js.split("\n")[max(0, ln - 4):ln + 3], start=max(1, ln - 3)):
                print(("  >>>" if k == ln else "     "), f"{k:5d} {linha}")
except ImportError:
    print("V8: indisponível (pip install py-mini-racer num venv) — pulando")

# ── 2. HTML: aninhamento das tags ──
VOID = {"br", "img", "input", "hr", "meta", "link", "path", "polygon",
        "rect", "circle", "source", "use"}
corpo = src[src.index('<div class="room">'):src.index("<script>")]
pilha, erros = [], []
for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>", corpo):
    fecha, tag, _, sozinha = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
    if tag in VOID or sozinha == "/":
        continue
    linha = corpo.count("\n", 0, m.start()) + 1
    if not fecha:
        pilha.append((tag, linha))
    elif not pilha:
        erros.append(f"linha {linha}: </{tag}> sem abertura")
    else:
        topo, tl = pilha.pop()
        if topo != tag:
            erros.append(f"linha {linha}: </{tag}> fecha <{topo}> da linha {tl}")
erros += [f"linha {l}: <{t}> nunca fechada" for t, l in pilha]
if erros:
    ruim = True
    print("HTML:", "; ".join(erros[:4]))
else:
    print("HTML: aninhamento OK")

# ── 3. CSS: chaves e tokens declarados ──
if css.count("{") != css.count("}"):
    ruim = True
    print(f"CSS: chaves desbalanceadas ({css.count('{')}/{css.count('}')})")
else:
    print("CSS: chaves OK")
usados = set(re.findall(r"var\(--([a-z0-9-]+)", css))
declarados = set(re.findall(r"^\s*--([a-z0-9-]+)\s*:", css, re.M))
orfaos = sorted(usados - declarados - {"p1", "p2", "net", "ball"})   # estes vêm do script
if orfaos:
    ruim = True
    print("CSS: tokens sem declaração:", orfaos)
else:
    print("CSS: tokens OK")

# ── 4. ids que o script procura existem no HTML? ──
ids_html = set(re.findall(r'\bid="([^"]+)"', src))
faltando = sorted({i for i in re.findall(r'getElementById\("([^"]+)"\)', js)} - ids_html)
if faltando:
    ruim = True
    print("DOM: getElementById sem elemento:", faltando)
else:
    print("DOM: ids OK")


# ── 5. identificadores curtos usados sem declaração ──
# O V8 compila `b.speed` numa função que não tem `b`: só quebra quando aquela
# linha roda. Foi assim que a desaceleração do chiclete foi parar dentro de
# premioRoleta, onde a bola se chama `ball`. Nomes de uma letra são sempre
# locais, então dá para cobrá-los por escopo sem precisar de um parser inteiro.

def limpar(t):
    """Troca strings, comentarios e regexes por espacos, preservando posicoes."""
    saida = []
    i, n = 0, len(t)
    anterior = ""
    while i < n:
        c = t[i]
        if c == "/" and i + 1 < n and t[i + 1] == "/":
            j = t.find("\n", i);  j = n if j < 0 else j
            saida.append(" " * (j - i)); i = j; continue
        if c == "/" and i + 1 < n and t[i + 1] == "*":
            j = t.find("*/", i + 2); j = n if j < 0 else j + 2
            saida.append(" " * (j - i)); i = j; continue
        if c in "\"'`":
            j = i + 1
            while j < n and t[j] != c:
                j += 2 if t[j] == "\\" else 1
            saida.append(" " * (min(j, n - 1) - i + 1)); i = min(j, n - 1) + 1
            anterior = "s"; continue
        if c == "/" and anterior not in ("i", ")", "]"):
            j, classe = i + 1, False
            while j < n:
                if t[j] == "\\": j += 2; continue
                if t[j] == "[": classe = True
                elif t[j] == "]": classe = False
                elif t[j] == "/" and not classe: break
                elif t[j] == "\n": break
                j += 1
            if j < n and t[j] == "/":
                saida.append(" " * (j - i + 1)); i = j + 1; anterior = "i"; continue
        saida.append(c)
        if not c.isspace():
            anterior = "i" if (c.isalnum() or c in "_$") else c
        i += 1
    return "".join(saida)


limpo = limpar(js)
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
USO = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)(?![\w$])(?!\s*:)")
CURTO = re.compile(r"(?<![\w$.])([A-Za-z_$])(?![\w$])(?!\s*:)")


def corpo_de(t, i):
    """Do '{' em t[i:] ate a chave que o fecha."""
    prof, j = 0, t.index("{", i)
    ini = j
    while j < len(t):
        if t[j] == "{":
            prof += 1
        elif t[j] == "}":
            prof -= 1
            if prof == 0:
                return ini, j + 1
        j += 1
    return ini, len(t)


def _fim_decl(t, i):
    """Da lista de declaradores ate o ';' (ou ')') que fecha o statement."""
    prof = 0
    while i < len(t):
        c = t[i]
        if c in "([{":
            prof += 1
        elif c in ")]}":
            if prof == 0:
                return i
            prof -= 1
        elif c == ";" and prof == 0:
            return i
        i += 1
    return len(t)


def _partes(txt):
    """Quebra `a = 1, b = 2` nas virgulas de profundidade zero."""
    saida, prof, ini = [], 0, 0
    for k, c in enumerate(txt):
        if c in "([{":
            prof += 1
        elif c in ")]}":
            prof -= 1
        elif c == "," and prof == 0:
            saida.append(txt[ini:k]); ini = k + 1
    saida.append(txt[ini:])
    return saida


def _alvo(parte):
    """O lado esquerdo, ate o primeiro '=' de profundidade zero."""
    prof = 0
    for k, c in enumerate(parte):
        if c in "([{":
            prof += 1
        elif c in ")]}":
            prof -= 1
        elif c == "=" and prof == 0 and parte[k:k + 2] != "==":
            return parte[:k]
    return parte


def nomes_da_decl(t, i):
    """Todo nome de um `const a = 1, b = 2;` — nao so o primeiro.

    Capturar so o primeiro nome depois da palavra-chave foi o que deixou
    passar o `GUM` duplicado, o terceiro travamento desta base.
    """
    achados = set()
    for parte in _partes(t[i:_fim_decl(t, i)]):
        achados |= set(IDENT.findall(_alvo(parte)))     # cobre desestruturacao
    return achados


def _declaracoes(t):
    """Nomes que um trecho declara, sem entrar em escopo nenhum."""
    s = set()
    for m in re.finditer(r"\b(const|let|var|function|class)\s+", t):
        if m.group(1) in ("function", "class"):
            g = IDENT.match(t, m.end())
            if g:
                s.add(g.group(0))
        else:
            s |= nomes_da_decl(t, m.end())
    return s


def ligados(corpo):
    """Tudo que o corpo amarra: declaracoes, parametros, capturas."""
    s = _declaracoes(corpo)
    s |= set(re.findall(r"\bcatch\s*\(\s*([\w$]+)", corpo))
    for g in re.findall(r"\bfunction[\w$ ]*\(([^()]*)\)", corpo):
        s |= set(IDENT.findall(g))
    for g in re.findall(r"\(([^()]*)\)\s*=>", corpo):          # (a, b) => ...
        s |= set(IDENT.findall(g))
    s |= set(re.findall(r"(?:^|[^\w$.])([\w$]+)\s*=>", corpo))  # x => ...
    return s


# Escopo do modulo, por profundidade de chaves. Recortar texto nao serve —
# sobra corpo de arrow function, e um `const b = o || ball` de dentro de
# bounce() daria passe livre ao `b` em qualquer outra funcao.
def profundidade_em(t, pos):
    return t.count("{", 0, pos) - t.count("}", 0, pos)


primeira = re.search(r"^  (?:async )?function [\w$]+\s*\(", limpo, re.M)
NIVEL = profundidade_em(limpo, primeira.start()) if primeira else 1

globais_topo = set()
for m in re.finditer(r"\b(const|let|var|function|class)\s+", limpo):
    if profundidade_em(limpo, m.start()) != NIVEL:
        continue
    if m.group(1) in ("function", "class"):
        g = IDENT.match(limpo, m.end())
        if g:
            globais_topo.add(g.group(0))
    else:
        globais_topo |= nomes_da_decl(limpo, m.end())
globais_topo = {x for x in globais_topo if len(x) == 1}

soltos = []
for m in re.finditer(r"^  (?:async )?function ([\w$]+)\s*\(([^)]*)\)\s*\{", limpo, re.M):
    nome, params = m.group(1), m.group(2)
    ini, fim = corpo_de(limpo, m.start())
    corpo = limpo[ini:fim]
    liga = ligados(corpo) | set(IDENT.findall(params)) | globais_topo | {"_"}
    for u in sorted(set(CURTO.findall(corpo))):
        if u in liga:
            continue
        ln = js.count("\n", 0, ini) + 1
        soltos.append(f"{nome}() usa `{u}` sem declarar (linha ~{ln} do script)")

if soltos:
    ruim = True
    print("JS: identificador solto ->", "; ".join(sorted(set(soltos))[:5]))
else:
    print("JS: identificadores curtos OK")


# ── 6. zona morta temporal (TDZ) no escopo do modulo ──
# `const A = B / 3` com B declarado mais abaixo compila liso no V8 e explode no
# carregamento: ReferenceError, script inteiro morto. Ja derrubou esta base uma
# vez (CRYSTAL antes de SPRITES) e quase de novo (MIRA_PASSO antes de DT).
# Corpo de funcao nao conta: ali a avaliacao e adiada.

ordem = {}
for m in re.finditer(r"\b(const|let|var|function|class)\s+", limpo):
    if profundidade_em(limpo, m.start()) != NIVEL:
        continue
    if m.group(1) in ("function", "class"):
        g = IDENT.match(limpo, m.end())
        if g:
            ordem.setdefault(g.group(0), m.start() if m.group(1) != "function" else -1)
    else:
        for nome in nomes_da_decl(limpo, m.end()):
            ordem.setdefault(nome, m.start())

cedo = []
for m in re.finditer(r"\b(const|let)\s+", limpo):
    if profundidade_em(limpo, m.start()) != NIVEL:
        continue
    trecho = limpo[m.end():_fim_decl(limpo, m.end())]
    # tudo a partir da primeira seta ou `function` e adiado
    corte = len(trecho)
    for marca in re.finditer(r"=>|\bfunction\b", trecho):
        corte = marca.start(); break
    imediato = trecho[:corte]
    alvos = {x for parte in _partes(trecho) for x in IDENT.findall(_alvo(parte))}
    # USO ignora chave de objeto (`ball:`) e acesso de propriedade (`.ball`):
    # nenhum dos dois e uma referencia ao nome do modulo.
    for uso in set(USO.findall(imediato)) - alvos:
        pos = ordem.get(uso)
        if pos is not None and pos > m.start():
            ln = js.count("\n", 0, m.start()) + 1
            adiante = js.count("\n", 0, pos) + 1
            cedo.append(f"linha {ln} usa `{uso}`, que so nasce na linha {adiante}")

if cedo:
    ruim = True
    print("JS: uso antes da declaracao ->", "; ".join(sorted(set(cedo))[:4]))
else:
    print("JS: ordem das declaracoes OK")



# ── 7. fumaça de execução: 300 quadros num DOM fantasma ──
# Sintaxe boa não garante quadro bom: um `i` fora do seu `for` compila liso e
# mata o jogo no primeiro quadro. Aqui o script roda de verdade no V8, com um
# DOM de mentira, e qualquer erro que o laço de quadros engolir aparece.
try:
    from py_mini_racer import MiniRacer as _MR
    _m = _MR()
    _m.eval(r"""
function fantasma(n){const f=function(){return fantasma(n+"()")};return new Proxy(f,{
 get(t,p){if(p===Symbol.toPrimitive||p==="valueOf")return()=>0;if(p==="toString")return()=>"";
  if(p===Symbol.iterator)return function*(){};if(p==="length")return 0;
  if(p==="matches"||p==="hidden")return false;return fantasma(n+"."+String(p));},
 set(){return true},has(){return true},
 apply(){return fantasma(n+"()")},construct(){return fantasma(n+"{}")}});}
var document=fantasma("document"); var window=globalThis;
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
    # gancho de teste: depois da abertura, forca a tela final — ela ja ficou
    # descoberta uma vez (a coroa sumiu num recorte e so quebrava no fim de jogo)
    _js2 = js.replace("function frame(now) {",
        "globalThis.__forcarOver = (v) => { S.phase = \"over\"; S.winner = 0; S.t = 0; vertical = !!v; };\n  function frame(now) {", 1)
    _m.eval("(function(){\n" + _js2 + "\n})()")
    _res = _m.eval("(function(){for(let k=1;k<=300&&!__erro;k++){__rel=k*16.7;if(__raf)__raf(__rel);}"
                   "if(!__erro&&globalThis.__forcarOver){__forcarOver(false);"
                   "for(let k=301;k<=430&&!__erro;k++){__rel=k*16.7;if(__raf)__raf(__rel);}"
                   "if(!__erro){__forcarOver(true);"
                   "for(let k=431;k<=560&&!__erro;k++){__rel=k*16.7;if(__raf)__raf(__rel);}}}return __erro||'';})()")
    if _res:
        ruim = True
        print("EXECUÇÃO: erro em quadro ->", _res.split("\n")[0][:200])
    else:
        print("EXECUÇÃO: 560 quadros (abertura + tela final nas duas orientações) sem erro")
except ImportError:
    print("EXECUÇÃO: V8 indisponível — pulando")
except Exception as _e:
    ruim = True
    print("EXECUÇÃO: erro na carga ->", str(_e).split("\n")[0][:200])


print("\nRESULTADO:", "FALHOU" if ruim else "PASSOU")
sys.exit(1 if ruim else 0)
