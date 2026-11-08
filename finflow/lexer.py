"""
Analisador léxico da FinFlow.

Converte o código-fonte em uma sequência de tokens, usando a biblioteca
PLY (Python Lex-Yacc). Palavras reservadas são resolvidas por consulta a
uma tabela hash dentro de t_ID, em vez de uma regra de regex por palavra
(ver justificativa no artigo, Seção III-C).
"""
import sys
import os
from decimal import Decimal
from ply.lex import lex

reserved = {
    'se': 'SE', 'entao': 'ENTAO', 'senao': 'SENAO', 'imprimir': 'IMPRIMIR',
    'moeda': 'TIPO_MOEDA', 'percentual': 'TIPO_PERCENTUAL',
    'inteiro': 'TIPO_INTEIRO', 'texto': 'TIPO_TEXTO',
    'e': 'OP_E', 'ou': 'OP_OU', 'nao': 'OP_NAO',
    'para': 'PARA', 'ate': 'ATE', 'faca': 'FACA',
    'escolha': 'ESCOLHA', 'caso': 'CASO', 'padrao': 'PADRAO',
    'buscar': 'BUSCAR',
}

tokens = [
    'ID', 'CTE_FLOAT', 'CTE_INT', 'CTE_PERCENTUAL', 'CTE_STRING',
    'ABRE_P', 'FECHA_P', 'ABRE_F', 'FECHA_F', 'FIM_CMD', 'VIRGULA', 'DOISPONTOS',
    'ATR', 'OP_SOMA', 'OP_MULT', 'OP_REL',
] + list(reserved.values())


def t_CTE_PERCENTUAL(t):
    r'\d+(\.\d+)?%'
    t.value = Decimal(t.value[:-1]) / 100
    return t


def t_CTE_FLOAT(t):
    r'\d+\.\d+'
    t.value = Decimal(t.value)
    return t


def t_CTE_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_CTE_STRING(t):
    r'"[^"]*"'
    t.value = t.value[1:-1]
    return t


def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'ID')
    return t


t_ABRE_P = r'\('
t_FECHA_P = r'\)'
t_ABRE_F = r'\{'
t_FECHA_F = r'\}'
t_FIM_CMD = r';'
t_VIRGULA = r','
t_DOISPONTOS = r':'
t_OP_REL = r'==|!=|>=|<=|>|<'
t_OP_SOMA = r'\+|-'
t_OP_MULT = r'\*|/'
t_ATR = r'='
t_ignore = " \t\r"
t_ignore_COMENTARIO = r'\#[^\n]*'


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise SyntaxError(f"Lexema invalido: {t.value[0]!r} na linha {t.lineno}")


# Tabelas de lex/yacc sao geradas na pasta do usuario que roda o script;
# aqui fixamos para a pasta deste modulo, evitando poluir o diretorio de
# trabalho de quem importar o pacote.
_outputdir = os.path.dirname(os.path.abspath(__file__))
lexer = lex(module=sys.modules[__name__], optimize=False,
            lextab='finflow_lextab', outputdir=_outputdir)
