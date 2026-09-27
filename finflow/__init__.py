"""
FinFlow — linguagem de domínio específico para modelagem de operações
financeiras. Compilador: lexer + parser (LALR(1)) + análise semântica +
interpretador (tree-walking).

Uso rápido:
    from finflow import rodar_finflow
    rodar_finflow('''
        moeda saldo = 1000.00;
        percentual taxa = 5%;
        imprimir(saldo + saldo * taxa);
    ''')
"""
from .parser import parse
from .semantica import analisar_semantica, ErroSemantico
from .interpretador import executar

__all__ = ["rodar_finflow", "ErroSemantico", "parse", "analisar_semantica", "executar"]


def rodar_finflow(codigo: str, tabela_inicial: dict | None = None,
                   ambiente_inicial: dict | None = None, imprimir_saida: bool = True):
    """
    Roda o pipeline completo: lex -> parse -> analise semantica -> execucao.

    tabela_inicial / ambiente_inicial: usados para injetar variaveis
    "ja declaradas" vindas de fora do codigo-fonte (ex: dados de uma API
    externa) -- ver finflow.semantica.analisar_semantica.

    Retorna o dict `ambiente` final (nome da variavel -> valor).
    """
    ast = parse(codigo)
    tabela = analisar_semantica(ast, tabela_inicial=tabela_inicial)
    ambiente, saida = executar(ast, tabela, ambiente_inicial=ambiente_inicial)
    if imprimir_saida:
        for linha in saida:
            print(linha)
    return ambiente
