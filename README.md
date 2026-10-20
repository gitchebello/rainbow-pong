# Rainbow Pong

Pong arcade com cara de fliperama antigo ("Vídeo-Raio Mod. P-72"): modo clássico, modo arena online de até 6 jogadores e o Chicletinho, o mascote que aparece depois de vários chicletes seguidos, segura a bola e cospe.

## Rodar

```bash
python3 relay.py           # http://localhost:8000 (jogo + salas na mesma porta)
python3 relay.py 9000      # outra porta
```

`relay.py` não tem dependências: o WebSocket é feito à mão sobre a biblioteca padrão. O jogo é o `pong.html`; `serve/index.html` é a versão publicada.

Na arena, `?name=<nome>` na URL define o nome do jogador e ganha do nome salvo no navegador.

## Verificação

```bash
python3 check.py           # compila o script do jogo com o V8 e pega erros de sintaxe
```

`testbola.py`, `testgol.py` e `simsync.py` testam a física da bola, os gols e a sincronização online.
