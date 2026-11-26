"""Corpus sintetico deterministico (distribuicao de Zipf), para testes e para
rodar o benchmark sem o Data Warehouse.

Imita a distribuicao de uma lingua real: poucas palavras muito frequentes
("jogo", "muito", "bom"...) e palavras de conteudo ("travando", "servidor"...)
espalhadas pela faixa de frequencia media do vocabulario.
"""

from __future__ import annotations

import random

FREQUENTES = ["jogo", "muito", "bom", "jogar", "melhor", "horas", "nao", "recomendo", "ruim", "vale"]

CONTEUDO = """travando otimizacao fps baixo historia emocionante personagens servidor lag multiplayer
pena comprar bugs crash fechando sozinho graficos lindos mundo aberto preco caro promocao amigos
joguei cheater hacker banido musica trilha sonora incrivel dificuldade jogabilidade travamento
lagando divertido viciante atualizacao desenvolvedores comunidade mapa missoes combate chefe dificil
facil campanha online offline conteudo dlc gratis pago placa video processador memoria configuracao
steam deck controle teclado mouse legendas portugues dublagem traducao""".split()


def gerar_corpus(n_docs: int = 5000, tam_vocab: int = 20000, media_palavras: int = 40,
                 semente: int = 42) -> list[str]:
    rng = random.Random(semente)
    vocab = [f"pal{i:05d}" for i in range(tam_vocab)]
    for i, palavra in enumerate(FREQUENTES):          # ranks 0, 2, 4, ... 18
        vocab[2 * i] = palavra
    posicoes = rng.sample(range(30, 3000), len(CONTEUDO))  # faixa de frequencia media
    for palavra, pos in zip(CONTEUDO, posicoes):
        vocab[pos] = palavra
    acumulado, total = [], 0.0
    for r in range(len(vocab)):
        total += 1.0 / (r + 1) ** 1.07   # Zipf
        acumulado.append(total)
    textos = []
    for _ in range(n_docs):
        tam = max(3, int(rng.lognormvariate(0, 0.9) * media_palavras * 0.65))
        textos.append(" ".join(rng.choices(vocab, cum_weights=acumulado, k=tam)))
    return textos
