"""
Analisador sintático da FinFlow.

Parser ascendente LALR(1), construído com ply.yacc a partir dos tokens
definidos em finflow.lexer. Produz uma AST representada como tuplas
Python aninhadas. Gramática completa e justificativas de projeto: ver
artigo, Seção III-A e III-D.
"""
import sys
import os
from ply.yacc import yacc

from .lexer import tokens, lexer  # noqa: F401  (tokens precisa estar no namespace deste modulo)

precedence = (
    ('left', 'OP_OU'),
    ('left', 'OP_E'),
    ('right', 'OP_NAO'),
    ('left', 'OP_REL'),
    ('left', 'OP_SOMA'),
    ('left', 'OP_MULT'),
)


def p_programa(p):
    'programa : lista_comandos'
    p[0] = ('programa', p[1])


def p_lista_comandos_multiplos(p):
    'lista_comandos : lista_comandos comando'
    p[0] = p[1] + [p[2]]


def p_lista_comandos_um(p):
    'lista_comandos : comando'
    p[0] = [p[1]]


def p_comando_declaracao(p):
    'comando : tipo ID ATR expressao FIM_CMD'
    p[0] = ('declaracao', p[1], p[2], p[4], p.lineno(2))


def p_comando_atribuicao(p):
    'comando : ID ATR expressao FIM_CMD'
    p[0] = ('atribuicao', p[1], p[3], p.lineno(1))


def p_comando_condicional_se(p):
    'comando : SE expressao ENTAO bloco'
    p[0] = ('se', p[2], p[4], None, p.lineno(1))


def p_comando_condicional_se_senao(p):
    'comando : SE expressao ENTAO bloco SENAO bloco'
    p[0] = ('se', p[2], p[4], p[6], p.lineno(1))


def p_comando_imprimir(p):
    'comando : IMPRIMIR ABRE_P expressao FECHA_P FIM_CMD'
    p[0] = ('imprimir', p[3], p.lineno(1))


def p_comando_repeticao(p):
    'comando : PARA ID ATR expressao ATE expressao FACA bloco'
    p[0] = ('para', p[2], p[4], p[6], p[8], p.lineno(1))


def p_comando_selecao(p):
    'comando : ESCOLHA expressao ABRE_F lista_casos FECHA_F'
    p[0] = ('escolha', p[2], p[4], p.lineno(1))


def p_lista_casos_multiplos(p):
    'lista_casos : lista_casos caso'
    p[0] = p[1] + [p[2]]


def p_lista_casos_um(p):
    'lista_casos : caso'
    p[0] = [p[1]]


def p_caso_valor(p):
    'caso : CASO expressao DOISPONTOS lista_comandos'
    p[0] = ('caso', p[2], p[4])


def p_caso_padrao(p):
    'caso : PADRAO DOISPONTOS lista_comandos'
    p[0] = ('padrao', p[3])


def p_bloco(p):
    'bloco : ABRE_F lista_comandos FECHA_F'
    p[0] = p[2]


def p_tipo(p):
    '''tipo : TIPO_MOEDA
            | TIPO_PERCENTUAL
            | TIPO_INTEIRO
            | TIPO_TEXTO'''
    p[0] = p[1]


def p_expressao_binop(p):
    '''expressao : expressao OP_SOMA expressao
                  | expressao OP_MULT expressao
                  | expressao OP_REL expressao'''
    p[0] = ('binop', p[2], p[1], p[3], p.lineno(2))


def p_expressao_logica(p):
    '''expressao : expressao OP_E expressao
                  | expressao OP_OU expressao'''
    p[0] = ('binop', p[2], p[1], p[3], p.lineno(2))


def p_expressao_nao(p):
    'expressao : OP_NAO expressao'
    p[0] = ('nao', p[2], p.lineno(1))


def p_expressao_buscar(p):
    'expressao : BUSCAR ABRE_P CTE_STRING VIRGULA expressao FECHA_P'
    p[0] = ('buscar', p[3], [p[5]], p.lineno(1))


def p_expressao_buscar_periodo(p):
    'expressao : BUSCAR ABRE_P CTE_STRING VIRGULA expressao VIRGULA expressao FECHA_P'
    p[0] = ('buscar', p[3], [p[5], p[7]], p.lineno(1))


def p_expressao_grupo(p):
    'expressao : ABRE_P expressao FECHA_P'
    p[0] = p[2]


def p_expressao_id(p):
    'expressao : ID'
    p[0] = ('id', p[1], p.lineno(1))


def p_expressao_cte_int(p):
    'expressao : CTE_INT'
    p[0] = ('cte_int', p[1])


def p_expressao_cte_float(p):
    'expressao : CTE_FLOAT'
    p[0] = ('cte_float', p[1])


def p_expressao_cte_percentual(p):
    'expressao : CTE_PERCENTUAL'
    p[0] = ('cte_percentual', p[1])


def p_expressao_cte_string(p):
    'expressao : CTE_STRING'
    p[0] = ('cte_string', p[1])


def p_error(p):
    if p:
        raise SyntaxError(f"Erro sintatico: token inesperado {p.type!r} ('{p.value}') na linha {p.lineno}")
    raise SyntaxError("Erro sintatico: fim de arquivo inesperado")


_outputdir = os.path.dirname(os.path.abspath(__file__))
parser = yacc(module=sys.modules[__name__], debug=False, write_tables=False,
              outputdir=_outputdir)


def parse(codigo: str):
    """Roda o lexer+parser sobre `codigo` e retorna a AST."""
    lexer.lineno = 1
    return parser.parse(codigo, lexer=lexer)
