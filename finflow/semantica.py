"""
Análise semântica da FinFlow: tabela de símbolos e verificação de tipos.

Implementa as regras de inferência formalizadas no artigo (Seção III-E,
notação Γ ⊢ e : τ). O ponto central: `moeda + percentual` diretamente é
um erro de tipo (mesmo domínio, grandezas diferentes) — mas um literal
`inteiro` solto é aceito em comparações e operações com `moeda`/`percentual`
por coerção (ex: `saldo > 500`).
"""


class ErroSemantico(Exception):
    pass


TIPOS_COMPATIVEIS_SOMA = {
    ('moeda', 'moeda'): 'moeda',
    ('percentual', 'percentual'): 'percentual',
    ('inteiro', 'inteiro'): 'inteiro',
    ('moeda', 'inteiro'): 'moeda',
    ('inteiro', 'moeda'): 'moeda',
    ('percentual', 'inteiro'): 'percentual',
    ('inteiro', 'percentual'): 'percentual',
}
TIPOS_COMPATIVEIS_MULT = {
    ('moeda', 'percentual'): 'moeda',
    ('percentual', 'moeda'): 'moeda',
    ('moeda', 'inteiro'): 'moeda',
    ('inteiro', 'moeda'): 'moeda',
    ('inteiro', 'inteiro'): 'inteiro',
    ('percentual', 'inteiro'): 'percentual',
    ('inteiro', 'percentual'): 'percentual',
}
TIPOS_COMPATIVEIS_COMPARACAO = {
    ('moeda', 'inteiro'), ('inteiro', 'moeda'),
    ('percentual', 'inteiro'), ('inteiro', 'percentual'),
}


def tipo_de(expr, tabela):
    tag = expr[0]
    if tag == 'cte_int':
        return 'inteiro'
    if tag == 'cte_float':
        return 'moeda'
    if tag == 'cte_percentual':
        return 'percentual'
    if tag == 'cte_string':
        return 'texto'
    if tag == 'id':
        nome, linha = expr[1], expr[2]
        if nome not in tabela:
            raise ErroSemantico(f"[linha {linha}] variavel '{nome}' usada antes de ser declarada")
        return tabela[nome][0]
    if tag == 'nao':
        if tipo_de(expr[1], tabela) != 'booleano':
            raise ErroSemantico(f"[linha {expr[2]}] 'nao' exige uma condicao (comparacao ou expressao logica)")
        return 'booleano'
    if tag == 'buscar':
        return tipo_buscar(expr, tabela)
    if tag == 'binop':
        op, esq, dire, linha = expr[1], expr[2], expr[3], expr[4]
        tp_esq = tipo_de(esq, tabela)
        tp_dire = tipo_de(dire, tabela)
        if op in ('e', 'ou'):
            if tp_esq != 'booleano' or tp_dire != 'booleano':
                raise ErroSemantico(f"[linha {linha}] '{op}' exige duas condicoes, mas recebeu '{tp_esq}' e '{tp_dire}'")
            return 'booleano'
        if op in ('==', '!=', '>', '<', '>=', '<='):
            if tp_esq != tp_dire and (tp_esq, tp_dire) not in TIPOS_COMPATIVEIS_COMPARACAO:
                raise ErroSemantico(f"[linha {linha}] comparacao entre tipos incompativeis: '{tp_esq}' e '{tp_dire}'")
            return 'booleano'
        if op in ('+', '-'):
            par = (tp_esq, tp_dire)
            if par in TIPOS_COMPATIVEIS_SOMA:
                return TIPOS_COMPATIVEIS_SOMA[par]
            raise ErroSemantico(
                f"[linha {linha}] erro de tipo: nao e possivel {'somar' if op == '+' else 'subtrair'} "
                f"'{tp_esq}' com '{tp_dire}' diretamente (ex: 'moeda + percentual' precisa de multiplicacao, nao soma)"
            )
        if op in ('*', '/'):
            par = (tp_esq, tp_dire)
            if op == '/' and par == ('moeda', 'moeda'):
                return 'percentual'  # razao entre dois valores monetarios
            if par in TIPOS_COMPATIVEIS_MULT:
                return TIPOS_COMPATIVEIS_MULT[par]
            if par == ('percentual', 'percentual'):
                return 'percentual'
            raise ErroSemantico(f"[linha {linha}] erro de tipo: nao e possivel multiplicar/dividir '{tp_esq}' com '{tp_dire}'")
    raise ErroSemantico(f"expressao nao reconhecida: {expr}")


def tipo_buscar(expr, tabela):
    from .bcb import SERIES
    _, nome, anos, linha = expr
    if nome not in SERIES:
        raise ErroSemantico(
            f"[linha {linha}] serie '{nome}' desconhecida em buscar(). Disponiveis: {', '.join(SERIES)}")
    for ano in anos:
        if tipo_de(ano, tabela) != 'inteiro':
            raise ErroSemantico(f"[linha {linha}] os anos de buscar() devem ser 'inteiro'")
    return SERIES[nome].tipo


def checar_comando(cmd, tabela):
    tag = cmd[0]
    if tag == 'declaracao':
        _, tipo_decl, nome, expr, linha = cmd
        if nome in tabela:
            raise ErroSemantico(f"[linha {linha}] variavel '{nome}' ja foi declarada")
        tp_expr = tipo_de(expr, tabela)
        if tp_expr != tipo_decl and (tipo_decl, tp_expr) not in TIPOS_COMPATIVEIS_COMPARACAO:
            raise ErroSemantico(f"[linha {linha}] nao e possivel atribuir '{tp_expr}' a variavel do tipo '{tipo_decl}'")
        tabela[nome] = (tipo_decl, None)
    elif tag == 'atribuicao':
        _, nome, expr, linha = cmd
        if nome not in tabela:
            raise ErroSemantico(f"[linha {linha}] variavel '{nome}' usada antes de ser declarada")
        tp_decl = tabela[nome][0]
        tp_expr = tipo_de(expr, tabela)
        if tp_expr != tp_decl and (tp_decl, tp_expr) not in TIPOS_COMPATIVEIS_COMPARACAO:
            raise ErroSemantico(f"[linha {linha}] nao e possivel atribuir '{tp_expr}' a variavel '{nome}' do tipo '{tp_decl}'")
    elif tag == 'se':
        _, cond, bloco_then, bloco_else, linha = cmd
        if tipo_de(cond, tabela) != 'booleano':
            raise ErroSemantico(f"[linha {linha}] condicao do 'se' precisa ser uma comparacao")
        for c in bloco_then:
            checar_comando(c, tabela)
        if bloco_else:
            for c in bloco_else:
                checar_comando(c, tabela)
    elif tag == 'para':
        _, var, ini, fim, corpo, linha = cmd
        if tipo_de(ini, tabela) != 'inteiro' or tipo_de(fim, tabela) != 'inteiro':
            raise ErroSemantico(f"[linha {linha}] limites do 'para' devem ser 'inteiro'")
        tabela[var] = ('inteiro', None)
        for c in corpo:
            checar_comando(c, tabela)
    elif tag == 'escolha':
        _, alvo, casos, linha = cmd
        tp_alvo = tipo_de(alvo, tabela)
        for c in casos:
            if c[0] == 'caso':
                tp_valor = tipo_de(c[1], tabela)
                if tp_valor != tp_alvo:
                    raise ErroSemantico(f"[linha {linha}] 'caso' com tipo '{tp_valor}' incompativel com 'escolha' do tipo '{tp_alvo}'")
                for cc in c[2]:
                    checar_comando(cc, tabela)
            else:
                for cc in c[1]:
                    checar_comando(cc, tabela)
    elif tag == 'imprimir':
        _, expr, linha = cmd
        tipo_de(expr, tabela)
    else:
        raise ErroSemantico(f"comando nao reconhecido: {cmd}")


def analisar_semantica(ast, tabela_inicial=None):
    """
    Roda a analise semantica sobre a AST e retorna a tabela de simbolos
    final. `tabela_inicial`, se fornecida, e um dict {nome: (tipo, valor)}
    com variaveis ja "declaradas" antes do programa comecar (ex: dados
    vindos de uma API externa) -- usado pela integracao com o Banco
    Central, sem exigir que o programador redeclare essas variaveis no
    codigo FinFlow.
    """
    tabela = dict(tabela_inicial) if tabela_inicial else {}
    _, comandos = ast
    for cmd in comandos:
        checar_comando(cmd, tabela)
    return tabela
