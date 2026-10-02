#!/usr/bin/env python3
"""
CLI da FinFlow.

Uso:
    python main.py exemplos/rendimento.ff     roda um programa FinFlow
    python main.py --series                   lista as series do Banco Central disponiveis em buscar()
"""
import sys

from finflow import rodar_finflow, ErroSemantico, ErroExecucao, ErroBCB, SERIES


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--series":
        for nome, s in SERIES.items():
            print(f"{nome:<11} {s.tipo:<11} {s.descricao}")
        return

    if len(sys.argv) != 2:
        print(__doc__)
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
    except (SyntaxError, ErroSemantico, ErroExecucao, ErroBCB) as e:
        print(f"Erro ao processar '{caminho}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
