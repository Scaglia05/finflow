"""
Análise semântica da FinFlow: tabela de símbolos, escopo de blocos e
verificação de tipos.

O ponto central: `moeda + percentual` diretamente é um erro de tipo (mesmo
domínio, grandezas diferentes). Um literal `inteiro` solto é aceito em
comparações e em operações com `moeda`/`percentual` por coerção (ex:
`saldo > 500`); em declarações e atribuições só é aceito o alargamento
`inteiro -> moeda`.

Escopo: variáveis declaradas no nível do programa são globais; as declaradas
dentro de um bloco (`se`, `senao`, `para`, `caso`, `padrao`) existem só até o
fim desse bloco, e a variável de controle do `para` existe só no laço.
`tabela` é o registro de todos os nomes e tipos (usado na execução para
formatar a saída); `escopos` é a pilha de nomes visíveis em cada ponto.
Um mesmo nome só pode ser reutilizado em outro bloco com o mesmo tipo.
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
# (destino, origem): única coerção implícita em declarações e atribuições.
# Um inteiro vira moeda (5 -> R$ 5,00); nunca o contrário (sem truncar
# centavos), e um inteiro não vira percentual (5 não é 5%).
TIPOS_ATRIBUIVEIS = {('moeda', 'inteiro')}


def atribuivel(destino, origem):
    return destino == origem or (destino, origem) in TIPOS_ATRIBUIVEIS


def _visivel(nome, escopos):
    return any(nome in escopo for escopo in escopos)


def tipo_de(expr, tabela, escopos=None):
    """Tipo de uma expressão. Com `escopos`, também exige que as variáveis
    estejam visíveis; sem ele (execução), consulta só a tabela."""
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
        if escopos is not None and not _visivel(nome, escopos):
            raise ErroSemantico(
                f"[linha {linha}] variavel '{nome}' fora do escopo: foi declarada em um bloco que ja terminou")
        return tabela[nome][0]
    if tag == 'nao':
        if tipo_de(expr[1], tabela, escopos) != 'booleano':
            raise ErroSemantico(f"[linha {expr[2]}] 'nao' exige uma condicao (comparacao ou expressao logica)")
        return 'booleano'
    if tag == 'buscar':
        return tipo_buscar(expr, tabela, escopos)
    if tag == 'binop':
        op, esq, dire, linha = expr[1], expr[2], expr[3], expr[4]
        tp_esq = tipo_de(esq, tabela, escopos)
        tp_dire = tipo_de(dire, tabela, escopos)
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


def tipo_buscar(expr, tabela, escopos=None):
    from .bcb import SERIES
    _, nome, anos, linha = expr
    if nome not in SERIES:
        raise ErroSemantico(
            f"[linha {linha}] serie '{nome}' desconhecida em buscar(). Disponiveis: {', '.join(SERIES)}")
    for ano in anos:
        if tipo_de(ano, tabela, escopos) != 'inteiro':
            raise ErroSemantico(f"[linha {linha}] os anos de buscar() devem ser 'inteiro'")
    return SERIES[nome].tipo


def _checar_bloco(comandos, tabela, escopos, locais=()):
    """Verifica um bloco em um escopo próprio, descartado ao final."""
    escopos.append(set(locais))
    try:
        for c in comandos:
            checar_comando(c, tabela, escopos)
    finally:
        escopos.pop()


def _declarar(nome, tipo, linha, tabela, escopos):
    if _visivel(nome, escopos):
        raise ErroSemantico(f"[linha {linha}] variavel '{nome}' ja foi declarada")
    if nome in tabela and tabela[nome][0] != tipo:
        raise ErroSemantico(
            f"[linha {linha}] variavel '{nome}' ja foi declarada com o tipo '{tabela[nome][0]}' em outro bloco")
    tabela[nome] = (tipo, None)
    escopos[-1].add(nome)


def checar_comando(cmd, tabela, escopos=None):
    if escopos is None:
        escopos = [set(tabela)]
    tag = cmd[0]
    if tag == 'declaracao':
        _, tipo_decl, nome, expr, linha = cmd
        tp_expr = tipo_de(expr, tabela, escopos)  # avaliada antes de o nome existir
        if not atribuivel(tipo_decl, tp_expr):
            raise ErroSemantico(f"[linha {linha}] nao e possivel atribuir '{tp_expr}' a variavel do tipo '{tipo_decl}'")
        _declarar(nome, tipo_decl, linha, tabela, escopos)
    elif tag == 'atribuicao':
        _, nome, expr, linha = cmd
        if nome not in tabela:
            raise ErroSemantico(f"[linha {linha}] variavel '{nome}' usada antes de ser declarada")
        if not _visivel(nome, escopos):
            raise ErroSemantico(
                f"[linha {linha}] variavel '{nome}' fora do escopo: foi declarada em um bloco que ja terminou")
        tp_decl = tabela[nome][0]
        tp_expr = tipo_de(expr, tabela, escopos)
        if not atribuivel(tp_decl, tp_expr):
            raise ErroSemantico(f"[linha {linha}] nao e possivel atribuir '{tp_expr}' a variavel '{nome}' do tipo '{tp_decl}'")
    elif tag == 'se':
        _, cond, bloco_then, bloco_else, linha = cmd
        if tipo_de(cond, tabela, escopos) != 'booleano':
            raise ErroSemantico(f"[linha {linha}] condicao do 'se' precisa ser uma comparacao")
        _checar_bloco(bloco_then, tabela, escopos)
        if bloco_else:
            _checar_bloco(bloco_else, tabela, escopos)
    elif tag == 'para':
        _, var, ini, fim, corpo, linha = cmd
        if tipo_de(ini, tabela, escopos) != 'inteiro' or tipo_de(fim, tabela, escopos) != 'inteiro':
            raise ErroSemantico(f"[linha {linha}] limites do 'para' devem ser 'inteiro'")
        if _visivel(var, escopos):
            raise ErroSemantico(f"[linha {linha}] variavel de controle '{var}' ja foi declarada")
        if var in tabela and tabela[var][0] != 'inteiro':
            raise ErroSemantico(
                f"[linha {linha}] variavel '{var}' ja foi declarada com o tipo '{tabela[var][0]}' em outro bloco")
        tabela[var] = ('inteiro', None)
        _checar_bloco(corpo, tabela, escopos, locais=(var,))
    elif tag == 'escolha':
        _, alvo, casos, linha = cmd
        tp_alvo = tipo_de(alvo, tabela, escopos)
        for c in casos:
            if c[0] == 'caso':
                tp_valor = tipo_de(c[1], tabela, escopos)
                if tp_valor != tp_alvo:
                    raise ErroSemantico(f"[linha {linha}] 'caso' com tipo '{tp_valor}' incompativel com 'escolha' do tipo '{tp_alvo}'")
                _checar_bloco(c[2], tabela, escopos)
            else:
                _checar_bloco(c[1], tabela, escopos)
    elif tag == 'imprimir':
        _, expr, linha = cmd
        tipo_de(expr, tabela, escopos)
    else:
        raise ErroSemantico(f"comando nao reconhecido: {cmd}")


def analisar_semantica(ast, tabela_inicial=None):
    """
    Roda a analise semantica sobre a AST e retorna a tabela de simbolos
    final. `tabela_inicial`, se fornecida, e um dict {nome: (tipo, valor)}
    com variaveis ja "declaradas" antes do programa comecar (ex: dados
    vindos de uma API externa) -- usado pela integracao com o Banco
    Central, sem exigir que o programador redeclare essas variaveis no
    codigo FinFlow. Essas variaveis sao globais.
    """
    tabela = dict(tabela_inicial) if tabela_inicial else {}
    escopos = [set(tabela)]
    _, comandos = ast
    for cmd in comandos:
        checar_comando(cmd, tabela, escopos)
    return tabela
