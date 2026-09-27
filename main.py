#!/usr/bin/env python3
"""
CLI da FinFlow: roda um arquivo .ff a partir da linha de comando.

Uso:
    python main.py exemplos/juros.ff
"""
import sys

from finflow import rodar_finflow, ErroSemantico


def main():
    if len(sys.argv) != 2:
        print("Uso: python main.py <arquivo.ff>")
        sys.exit(1)

    caminho = sys.argv[1]
    try:
        with open(caminho, encoding="utf-8") as f:
            codigo = f.read()
    except FileNotFoundError:
        print(f"Erro: arquivo '{caminho}' nao encontrado.")
        sys.exit(1)

    try:
        rodar_finflow(codigo)
    except (SyntaxError, ErroSemantico) as e:
        print(f"Erro ao processar '{caminho}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
