"""
Interpretador (tree-walking) da FinFlow: executa a AST de fato.

Valores `moeda` e `percentual` são `decimal.Decimal`, o que evita os erros de
representação binária do ponto flutuante (0.1 + 0.2 vale exatamente 0.3). Na
saída, arredonda-se a duas casas com ROUND_HALF_UP, a convenção financeira.
"""
from decimal import Decimal, ROUND_HALF_UP


class ErroExecucao(RuntimeError):
    pass


def converter(valor, tipo):
    """Normaliza `valor` para a representação interna do tipo FinFlow."""
    if tipo in ('moeda', 'percentual') and not isinstance(valor, (Decimal, bool)):
        if isinstance(valor, (int, float)):
            return Decimal(str(valor))
    return valor


def _duas_casas(valor):
    decimal = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    return decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def formatar(valor, tipo):
    if tipo == 'booleano':
        return "verdadeiro" if valor else "falso"
    if tipo == 'moeda':
        return f"R$ {_duas_casas(valor)}"
    if tipo == 'percentual':
        return f"{_duas_casas(converter(valor, 'percentual') * 100)}%"
    return str(valor)


def avaliar(expr, ambiente, tabela):
    tag = expr[0]
    if tag in ('cte_int', 'cte_float', 'cte_percentual', 'cte_string'):
        return expr[1]
    if tag == 'id':
        return ambiente[expr[1]]
    if tag == 'nao':
        return not avaliar(expr[1], ambiente, tabela)
    if tag == 'buscar':
        from .bcb import valor_serie
        anos = [avaliar(a, ambiente, tabela) for a in expr[2]]
        return valor_serie(expr[1], *anos)
    if tag == 'binop':
        op = expr[1]
        esq = avaliar(expr[2], ambiente, tabela)
        if op == 'e': return bool(esq) and bool(avaliar(expr[3], ambiente, tabela))
        if op == 'ou': return bool(esq) or bool(avaliar(expr[3], ambiente, tabela))
        dire = avaliar(expr[3], ambiente, tabela)
        if op == '+': return esq + dire
        if op == '-': return esq - dire
        if op == '*': return esq * dire
        if op == '/':
            if dire == 0:
                raise ErroExecucao(f"[linha {expr[4]}] divisao por zero")
            return esq // dire if isinstance(esq, int) and isinstance(dire, int) else esq / dire
        if op == '==': return esq == dire
        if op == '!=': return esq != dire
        if op == '>': return esq > dire
        if op == '<': return esq < dire
        if op == '>=': return esq >= dire
        if op == '<=': return esq <= dire
    raise RuntimeError(f"expressao nao suportada em execucao: {expr}")


def executar_comando(cmd, ambiente, tabela, saida):
    tag = cmd[0]
    if tag == 'declaracao':
        _, tipo_decl, nome, expr, _ = cmd
        ambiente[nome] = converter(avaliar(expr, ambiente, tabela), tipo_decl)
    elif tag == 'atribuicao':
        _, nome, expr, _ = cmd
        ambiente[nome] = converter(avaliar(expr, ambiente, tabela), tabela[nome][0])
    elif tag == 'se':
        _, cond, bloco_then, bloco_else, _ = cmd
        if avaliar(cond, ambiente, tabela):
            for c in bloco_then:
                executar_comando(c, ambiente, tabela, saida)
        elif bloco_else:
            for c in bloco_else:
                executar_comando(c, ambiente, tabela, saida)
    elif tag == 'para':
        _, var, ini, fim, corpo, _ = cmd
        i_ini = avaliar(ini, ambiente, tabela)
        i_fim = avaliar(fim, ambiente, tabela)
        for i in range(i_ini, i_fim + 1):
            ambiente[var] = i
            for c in corpo:
                executar_comando(c, ambiente, tabela, saida)
    elif tag == 'escolha':
        _, alvo, casos, _ = cmd
        valor_alvo = avaliar(alvo, ambiente, tabela)
        executado = False
        bloco_padrao = None
        for c in casos:
            if c[0] == 'caso':
                valor_caso = avaliar(c[1], ambiente, tabela)
                if valor_caso == valor_alvo:
                    for cc in c[2]:
                        executar_comando(cc, ambiente, tabela, saida)
                    executado = True
                    break
            else:
                bloco_padrao = c[1]
        if not executado and bloco_padrao:
            for cc in bloco_padrao:
                executar_comando(cc, ambiente, tabela, saida)
    elif tag == 'imprimir':
        from .semantica import tipo_de
        _, expr, _ = cmd
        valor = avaliar(expr, ambiente, tabela)
        tipo = tipo_de(expr, tabela)
        saida.append(formatar(valor, tipo))
    else:
        raise RuntimeError(f"comando nao reconhecido: {cmd}")


def executar(ast, tabela, ambiente_inicial=None):
    """
    Executa o programa e retorna (ambiente_final, saida).
    `ambiente_inicial`, se fornecido, e um dict {nome: valor} com
    variaveis ja populadas antes da execucao comecar (usado junto com
    `tabela_inicial` de `analisar_semantica`, ver finflow.semantica).
    """
    ambiente = {nome: converter(valor, tabela[nome][0] if nome in tabela else None)
                for nome, valor in (ambiente_inicial or {}).items()}
    saida = []
    _, comandos = ast
    for cmd in comandos:
        executar_comando(cmd, ambiente, tabela, saida)
    return ambiente, saida
