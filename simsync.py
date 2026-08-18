"""Anfitrião x convidado: mede o desvio da bola sob latência.

Hipótese em teste: o convidado NÃO prevê a rebatida nas raquetes, então entre
o impacto real e a chegada do aviso a bola dele atravessa a raquete e depois
salta de volta. Comparo com a versão em que ele também prevê a rebatida.
"""
import math, random, statistics

LEN, SPAN, WALL, BS, DT = 512, 320, 8, 8, 1/120
FACE0, FACE1 = 26, LEN - 26

class B:
    def __init__(s, a=26.0, b=160.0, va=300.0, vb=90.0): s.a,s.b,s.va,s.vb = a,b,va,vb
    def copia(s): return B(s.a, s.b, s.va, s.vb)

def anda(x, dt):
    x.a += x.va*dt; x.b += x.vb*dt
    if x.b <= WALL: x.b = WALL; x.vb = abs(x.vb)
    if x.b + BS >= SPAN-WALL: x.b = SPAN-WALL-BS; x.vb = -abs(x.vb)

def rebate(x, rnd):
    """Devolve True se bateu numa raquete. Mesma regra nos dois lados."""
    if x.va < 0 and x.a <= FACE0:
        x.a = FACE0; vel = min(math.hypot(x.va,x.vb)*1.07, 640)
        ang = rnd.uniform(-0.8, 0.8)
        x.va, x.vb = math.cos(ang)*vel, math.sin(ang)*vel
        return True
    if x.va > 0 and x.a + BS >= FACE1:
        x.a = FACE1-BS; vel = min(math.hypot(x.va,x.vb)*1.07, 640)
        ang = rnd.uniform(-0.8, 0.8)
        x.va, x.vb = -math.cos(ang)*vel, math.sin(ang)*vel
        return True
    return False

def roda(dur, lat, jit, hz, limiar, lerp, preve, seed=7):
    rnd_h = random.Random(seed)      # o anfitrião decide o ângulo
    rnd_g = random.Random(seed)      # o convidado prevê com a MESMA semente
    host, guest = B(), B()
    fila, t, prox, desvios = [], 0.0, 0.0, []
    while t < dur:
        anda(host, DT)
        if rebate(host, rnd_h):
            fila.append((t + max(.001,(lat+rnd_h.uniform(-jit,jit))/1000), "ev", host.copia()))
        if hz and t >= prox:
            prox = t + 1/hz
            fila.append((t + max(.001,(lat+rnd_h.uniform(-jit,jit))/1000), "bola", host.copia()))

        anda(guest, DT)
        if preve: rebate(guest, rnd_g)
        for it in [f for f in fila if f[0] <= t]:
            fila.remove(it)
            _, tipo, est = it
            alvo = est.copia()
            passos = int((lat/2/1000)/DT)
            for _ in range(passos): anda(alvo, DT)
            d = math.hypot(alvo.a-guest.a, alvo.b-guest.b)
            if tipo=="ev" and not preve or d > limiar:
                guest.a,guest.b,guest.va,guest.vb = alvo.a,alvo.b,alvo.va,alvo.vb
            else:
                guest.a += (alvo.a-guest.a)*lerp; guest.b += (alvo.b-guest.b)*lerp
                guest.va,guest.vb = alvo.va,alvo.vb
        desvios.append(math.hypot(host.a-guest.a, host.b-guest.b))
        t += DT
    return desvios

def relata(nome, d):
    d2 = sorted(d)
    print(f"    {nome:38s} mediana {d2[len(d2)//2]:5.1f}  p95 {d2[int(len(d2)*.95)]:6.1f}  "
          f"pior {d2[-1]:6.1f}  ruim(>8px) {sum(1 for v in d if v>8)/len(d)*100:5.1f}%")

print("Desvio entre a bola do anfitriao e a do convidado, em unidades (a bola tem 8)\n")
for lat, jit, nome in [(6,3,"LAN"), (45,20,"celular na mesma rede"), (110,45,"internet ruim")]:
    print(f"{nome}  ({lat}+-{jit} ms)")
    relata("hoje (sem prever rebatida) + mundo 4Hz", roda(30,lat,jit,4,45,0.0,False))
    relata("preve rebatida + bola 10Hz, lerp 30%",   roda(30,lat,jit,10,60,0.30,True))
    relata("preve rebatida + bola 20Hz, lerp 35%",   roda(30,lat,jit,20,60,0.35,True))
    print()
