#!/usr/bin/env python3
"""
CLI da FinFlow.

Uso:
    python main.py                            roda TODOS os exemplos e abre o playground web
    python main.py --sem-playground           roda todos os exemplos e termina
    python main.py exemplos/rendimento.ff     roda um unico programa FinFlow
    python main.py --series                   lista as series do Banco Central disponiveis em buscar()

Os testes automatizados rodam a parte: python -m pytest testes -v
"""
import glob
import os
import sys

from finflow import rodar_finflow, ErroSemantico, ErroExecucao, ErroBCB, SERIES

ERROS = (SyntaxError, ErroSemantico, ErroExecucao, ErroBCB)
RAIZ = os.path.dirname(os.path.abspath(__file__))


def rodar_arquivo(caminho):
    """Roda um .ff; devolve True se terminou sem erro."""
    try:
        with open(caminho, encoding="utf-8") as f:
            codigo = f.read()
    except FileNotFoundError:
        print(f"Erro: arquivo '{caminho}' nao encontrado.")
        return False
    try:
        rodar_finflow(codigo)
        return True
    except ERROS as e:
        print(f"Erro ao processar '{caminho}': {e}")
        return False


def rodar_todos():
    arquivos = sorted(glob.glob(os.path.join(RAIZ, "exemplos", "*.ff")))
    for caminho in arquivos:
        print(f"\n===== {os.path.basename(caminho)} =====")
        rodar_arquivo(caminho)
    print(f"\n{len(arquivos)} exemplos executados (erro_tipo.ff falha de proposito: demonstra a analise semantica).")


def main():
    args = sys.argv[1:]

    if args == ["--series"]:
        for nome, s in SERIES.items():
            print(f"{nome:<11} {s.tipo:<11} {s.descricao}")
    elif not args or args == ["--sem-playground"]:
        rodar_todos()
        if not args:
            from playground import servir
            print()
            servir()
    elif len(args) == 1 and not args[0].startswith("--"):
        sys.exit(0 if rodar_arquivo(args[0]) else 1)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
