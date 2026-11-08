"""Testes dos erros léxicos e sintáticos e de detalhes do analisador."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finflow import rodar_finflow, parse


def test_caractere_invalido_e_erro_lexico():
    with pytest.raises(SyntaxError, match="Lexema invalido: '@' na linha 2"):
        parse('inteiro a = 1;\ninteiro b = 2 @ 3;')


def test_token_inesperado_e_erro_sintatico():
    with pytest.raises(SyntaxError, match="token inesperado 'FIM_CMD'"):
        parse('moeda x = ;')


def test_fim_de_arquivo_inesperado():
    with pytest.raises(SyntaxError, match="fim de arquivo inesperado"):
        parse('moeda x = 5')


def test_numero_de_linha_acompanha_quebras_de_linha():
    with pytest.raises(SyntaxError, match="na linha 3"):
        parse('inteiro a = 1;\n\ninteiro b = = 2;')


def test_comentarios_sao_ignorados():
    ambiente = rodar_finflow('# comentario\ninteiro a = 1; # outro\n', imprimir_saida=False)
    assert ambiente['a'] == 1


def test_palavra_reservada_nao_e_nome_de_variavel():
    with pytest.raises(SyntaxError):
        parse('inteiro e = 1;')


def test_identificador_com_prefixo_de_palavra_reservada():
    ambiente = rodar_finflow('inteiro moedas = 2; inteiro seguro = 3;', imprimir_saida=False)
    assert ambiente['moedas'] == 2 and ambiente['seguro'] == 3


def test_literais_do_lexer():
    from finflow.lexer import lexer
    lexer.lineno = 1
    lexer.input('5% 1.50 7 "oi"')
    tipos = [(t.type, str(t.value)) for t in iter(lexer.token, None)]
    assert tipos == [('CTE_PERCENTUAL', '0.05'), ('CTE_FLOAT', '1.50'), ('CTE_INT', '7'), ('CTE_STRING', 'oi')]
