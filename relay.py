#!/usr/bin/env python3
"""Servidor do Rainbow Pong: serve o jogo e retransmite as salas na mesma porta.

Sem dependências — o aperto de mão e o enquadramento do WebSocket são feitos
à mão sobre sockets da biblioteca padrão. Cada sala guarda no máximo dois
jogadores e as mensagens são repassadas cruas de um para o outro.

    python3 relay.py [porta]
"""

import base64
import hashlib
import json
import mimetypes
import os
import socket
import struct
import sys
import threading
import time

print = __import__("functools").partial(print, flush=True)   # log ao vivo, sem buffer

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serve")
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

salas = {}          # codigo -> [conexoes]
trava = threading.Lock()

# Limites para o servidor aguentar exposição pública sem virar alvo fácil
MAX_QUADRO = 64 * 1024      # nenhuma mensagem do jogo passa de ~1 KB
MAX_CONEXOES = 200
MAX_SALAS = 120
MAX_POR_IP = 12
OCIOSO = 45                 # segundos sem receber nada = conexão morta
MUDO = 10                   # ...mas para segurar vaga em sala, 10 já é fantasma

conexoes = 0
por_ip = {}


# ───────────────────────── WebSocket cru ─────────────────────────

def receber_tudo(sock, n):
    dados = b""
    while len(dados) < n:
        pedaco = sock.recv(n - len(dados))
        if not pedaco:
            raise ConnectionError("conexão encerrada")
        dados += pedaco
    return dados


def ler_quadro(sock):
    """Devolve (opcode, payload) de um quadro do cliente."""
    cab = receber_tudo(sock, 2)
    opcode = cab[0] & 0x0F
    mascarado = cab[1] & 0x80
    tam = cab[1] & 0x7F
    if tam == 126:
        tam = struct.unpack(">H", receber_tudo(sock, 2))[0]
    elif tam == 127:
        tam = struct.unpack(">Q", receber_tudo(sock, 8))[0]
    if tam > MAX_QUADRO:
        raise ConnectionError("quadro grande demais")
    chave = receber_tudo(sock, 4) if mascarado else b"\0\0\0\0"
    corpo = receber_tudo(sock, tam)
    if mascarado:
        corpo = bytes(b ^ chave[i % 4] for i, b in enumerate(corpo))
    return opcode, corpo


def montar_quadro(corpo, opcode=1):
    tam = len(corpo)
    if tam < 126:
        cab = struct.pack(">BB", 0x80 | opcode, tam)
    elif tam < (1 << 16):
        cab = struct.pack(">BBH", 0x80 | opcode, 126, tam)
    else:
        cab = struct.pack(">BBQ", 0x80 | opcode, 127, tam)
    return cab + corpo


class Par:
    """Um jogador conectado, com envio protegido por trava."""

    def __init__(self, sock):
        self.sock = sock
        self.codigo = None
        self.trava = threading.Lock()
        self.vivo = True
        self.visto = time.time()

    def enviar(self, texto):
        if not self.vivo:
            return
        try:
            with self.trava:
                self.sock.sendall(montar_quadro(texto.encode("utf-8")))
        except OSError:
            self.vivo = False


def _tirar(par, codigo):
    """Tira `par` de uma sala. Chamar com a trava já tomada."""
    sala = salas.get(codigo)
    if sala and par in sala:
        sala.remove(par)
    if sala is not None and not sala:
        salas.pop(codigo, None)


def entrar_na_sala(par, codigo):
    mortos = []
    with trava:
        # Uma conexão ocupa uma vaga só. Trocar de sala libera a anterior.
        if par.codigo and par.codigo != codigo:
            _tirar(par, par.codigo)
            par.codigo = None

        if codigo not in salas and len(salas) >= MAX_SALAS:
            par.enviar(json.dumps({"t": "lotado"}))
            return False

        sala = salas.setdefault(codigo, [])

        # Fantasmas. Quem fecha direito some na hora, mas quem emudece — celular
        # dormindo, wi-fi trocando, aba no fundo — segurava a vaga até OCIOSO
        # estourar, 45 s trancando o parceiro para fora com "cheia". Pior: o
        # próprio jogador, ao reconectar, batia no próprio fantasma. Os dois
        # lados mandam ping a cada 2 s, então 10 s de silêncio já condena.
        agora = time.time()
        mortos = [p for p in sala if not p.vivo or agora - p.visto > MUDO]
        for m in mortos:
            m.vivo = False
            sala.remove(m)

        if par in sala:
            pass                      # já estava dentro: reconfirma, não duplica
        elif len(sala) >= 2:
            par.enviar(json.dumps({"t": "cheia"}))
            return False
        else:
            sala.append(par)
        par.codigo = codigo
        outros = [p for p in sala if p is not par]

    for m in mortos:                  # fora da trava: derruba o socket parado
        print(f"  sala {codigo}: fantasma removido ({agora - m.visto:.0f}s calado)")
        try:
            m.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    # Avisa os dois com a MESMA mensagem: quem é anfitrião e quem é convidado
    # já está decidido no cliente, não pode depender da ordem de chegada.
    if outros:
        aviso = json.dumps({"t": "par"})
        par.enviar(aviso)
        for o in outros:
            o.enviar(aviso)
    print(f"  sala {codigo}: {len(outros) + 1} jogador(es)")
    return True


def sair_da_sala(par):
    if not par.codigo:
        return
    with trava:
        sala = salas.get(par.codigo, [])
        # Se já foi expulso como fantasma, some calado: avisar "tchau" agora
        # derrubaria o jogador que herdou a vaga.
        estava = par in sala
        if estava:
            sala.remove(par)
        restantes = list(sala) if estava else []
        if not sala:
            salas.pop(par.codigo, None)
    for o in restantes:
        o.enviar(json.dumps({"t": "tchau"}))
    print(f"  sala {par.codigo}: saiu um jogador")


def atender_websocket(sock, chave):
    aceite = base64.b64encode(
        hashlib.sha1((chave + GUID).encode()).digest()
    ).decode()
    sock.sendall(
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: " + aceite.encode() + b"\r\n\r\n"
    )

    par = Par(sock)
    sock.settimeout(OCIOSO)
    try:
        while True:
            opcode, corpo = ler_quadro(sock)
            par.visto = time.time()
            if opcode == 8:
                break
            if opcode == 9:
                with par.trava:
                    sock.sendall(montar_quadro(corpo, opcode=10))
                continue
            if opcode != 1:
                continue

            texto = corpo.decode("utf-8", "replace")
            try:
                msg = json.loads(texto)
            except ValueError:
                continue

            if msg.get("t") == "sala":
                entrar_na_sala(par, str(msg.get("codigo", ""))[:8].upper())
                continue

            # tudo o mais é repassado cru para o outro jogador da sala
            if par.codigo:
                with trava:
                    outros = [p for p in salas.get(par.codigo, []) if p is not par]
                for o in outros:
                    o.enviar(texto)
    except (ConnectionError, OSError):
        pass
    finally:
        par.vivo = False
        sair_da_sala(par)
        try:
            sock.close()
        except OSError:
            pass


# ───────────────────────── HTTP simples ─────────────────────────

def servir_arquivo(sock, caminho, so_cabecalho=False):
    if caminho in ("/", ""):
        caminho = "/index.html"
    alvo = os.path.normpath(os.path.join(RAIZ, caminho.lstrip("/")))
    if not alvo.startswith(RAIZ) or not os.path.isfile(alvo):
        sock.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\n\r\nnao achei")
        return
    tipo = mimetypes.guess_type(alvo)[0] or "application/octet-stream"
    with open(alvo, "rb") as f:
        corpo = f.read()
    cabecalho = (
        f"HTTP/1.1 200 OK\r\nContent-Type: {tipo}; charset=utf-8\r\n"
        f"Content-Length: {len(corpo)}\r\nCache-Control: no-store\r\n\r\n"
    ).encode()
    sock.sendall(cabecalho if so_cabecalho else cabecalho + corpo)


def atender(sock, ip):
    global conexoes
    try:
        sock.settimeout(15)
        bruto = b""
        while b"\r\n\r\n" not in bruto:
            pedaco = sock.recv(4096)
            if not pedaco:
                return
            bruto += pedaco
            if len(bruto) > 65536:
                return

        linhas = bruto.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
        metodo, caminho, *_ = linhas[0].split(" ")
        cabecalhos = {}
        for l in linhas[1:]:
            if ": " in l:
                k, v = l.split(": ", 1)
                cabecalhos[k.lower()] = v

        if "websocket" in cabecalhos.get("upgrade", "").lower():
            print(f"  ws: aperto de mão de {ip}")
            atender_websocket(sock, cabecalhos.get("sec-websocket-key", ""))
            return

        if metodo not in ("GET", "HEAD"):
            sock.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
            return
        servir_arquivo(sock, caminho.split("?")[0], so_cabecalho=(metodo == "HEAD"))
    except (OSError, ValueError, IndexError):
        pass
    finally:
        with trava:
            conexoes -= 1
            por_ip[ip] = por_ip.get(ip, 1) - 1
            if por_ip[ip] <= 0:
                por_ip.pop(ip, None)
        try:
            sock.close()
        except OSError:
            pass


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", porta))
    srv.listen(64)
    print(f"Rainbow Pong servindo em http://0.0.0.0:{porta}  (salas em /ws)")
    global conexoes
    while True:
        cliente, origem = srv.accept()
        ip = origem[0]
        with trava:
            demais = por_ip.get(ip, 0)
            if conexoes >= MAX_CONEXOES or demais >= MAX_POR_IP:
                cheio = True
            else:
                cheio = False
                conexoes += 1
                por_ip[ip] = demais + 1
        if cheio:
            try:
                cliente.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            cliente.close()
            continue
        cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=atender, args=(cliente, ip), daemon=True).start()


if __name__ == "__main__":
    main()
