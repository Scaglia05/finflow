"""
Testes do escopo de blocos, da coerção em declarações e atribuições, dos
demais erros semânticos e da aritmética decimal. Rodam sem rede.
"""
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finflow import rodar_finflow, rodar_finflow_com_dados_bc, ErroSemantico


def erro(codigo, trecho):
    with pytest.raises(ErroSemantico, match=trecho):
        rodar_finflow(codigo, imprimir_saida=False)


# --- escopo de blocos -------------------------------------------------------

def test_variavel_de_bloco_nao_existe_depois_do_bloco():
    erro('inteiro a = 1; se a == 1 entao { inteiro b = 2; } imprimir(b);', "fora do escopo")


def test_atribuicao_a_variavel_de_bloco_fora_do_bloco():
    erro('se 1 == 1 entao { inteiro b = 2; } b = 3;', "fora do escopo")


def test_variavel_de_controle_do_para_nao_vaza():
    erro('para i = 1 ate 3 faca { inteiro x = i; } imprimir(i);', "fora do escopo")


def test_variavel_global_visivel_em_blocos_aninhados():
    ambiente = rodar_finflow('''
        inteiro total = 0;
        para i = 1 ate 3 faca {
            se i > 1 entao { total = total + i; }
        }
    ''', imprimir_saida=False)
    assert ambiente['total'] == 5


def test_mesmo_nome_em_blocos_irmaos_com_mesmo_tipo():
    ambiente = rodar_finflow('''
        inteiro n = 0;
        se 1 == 1 entao { inteiro t = 1; n = n + t; }
        se 1 == 1 entao { inteiro t = 2; n = n + t; }
    ''', imprimir_saida=False)
    assert ambiente['n'] == 3


def test_mesmo_nome_em_blocos_irmaos_com_tipo_diferente_e_erro():
    erro('se 1 == 1 entao { inteiro t = 1; } se 1 == 1 entao { texto t = "x"; }', "outro bloco")


def test_sombreamento_e_erro():
    erro('inteiro x = 1; se x == 1 entao { inteiro x = 2; }', "ja foi declarada")


def test_dois_lacos_com_a_mesma_variavel_de_controle():
    ambiente = rodar_finflow('''
        inteiro s = 0;
        para i = 1 ate 2 faca { s = s + i; }
        para i = 1 ate 3 faca { s = s + i; }
    ''', imprimir_saida=False)
    assert ambiente['s'] == 9


def test_variavel_de_controle_nao_pode_repetir_nome_visivel():
    erro('inteiro i = 0; para i = 1 ate 2 faca { i = 5; }', "variavel de controle 'i' ja foi declarada")


def test_variavel_de_controle_com_tipo_conflitante_de_outro_bloco():
    erro('se 1 == 1 entao { texto i = "a"; } para i = 1 ate 2 faca { imprimir(i); }', "outro bloco")


def test_nome_nao_pode_ser_usado_na_propria_declaracao():
    erro('inteiro x = x + 1;', "usada antes de ser declarada")


def test_blocos_de_caso_tem_escopo_proprio():
    ambiente = rodar_finflow('''
        inteiro k = 2;
        inteiro r = 0;
        escolha k {
            caso 1: inteiro a = 5; r = a;
            caso 2: inteiro a = 6; r = a;
        }
    ''', imprimir_saida=False)
    assert ambiente['r'] == 6
    erro('inteiro k = 1; escolha k { caso 1: inteiro a = 5; } imprimir(a);', "fora do escopo")


def test_variaveis_injetadas_sao_globais(capsys):
    rodar_finflow_com_dados_bc('se taxa > 1% entao { imprimir(taxa); }', {'taxa': ('percentual', 0.05)})
    assert capsys.readouterr().out.strip() == "5.00%"


def test_variavel_injetada_nao_pode_ser_redeclarada():
    with pytest.raises(ErroSemantico, match="ja foi declarada"):
        rodar_finflow_com_dados_bc('percentual taxa = 1%;', {'taxa': ('percentual', 0.05)}, imprimir_saida=False)


# --- coerção em declarações e atribuições ----------------------------------

def test_moeda_nao_vira_inteiro():
    erro('inteiro n = 10.50;', "nao e possivel atribuir 'moeda'")
    erro('inteiro n = 1; n = 2.50;', "nao e possivel atribuir 'moeda'")


def test_inteiro_nao_vira_percentual():
    erro('percentual p = 5;', "nao e possivel atribuir 'inteiro'")


def test_inteiro_vira_moeda_na_declaracao_e_na_atribuicao(capsys):
    ambiente = rodar_finflow('moeda m = 5; imprimir(m); m = 7; imprimir(m);')
    assert capsys.readouterr().out.split("\n")[:2] == ["R$ 5.00", "R$ 7.00"]
    assert ambiente['m'] == Decimal(7) and isinstance(ambiente['m'], Decimal)


def test_texto_nao_recebe_numero():
    erro('texto t = 5;', "nao e possivel atribuir 'inteiro'")


# --- demais regras semânticas ----------------------------------------------

def test_tipo_do_caso_deve_ser_igual_ao_do_escolha():
    erro('texto s = "a"; escolha s { caso 1: s = "b"; }', "incompativel")


def test_limites_do_para_devem_ser_inteiros():
    erro('para i = 1.0 ate 3 faca { imprimir(i); }', "limites")


def test_condicao_do_se_deve_ser_comparacao():
    erro('inteiro a = 1; se a entao { a = 2; }', "comparacao")


def test_nao_exige_condicao():
    erro('inteiro a = 1; se nao a entao { a = 2; }', "'nao' exige")


def test_comparacao_entre_tipos_incompativeis():
    erro('texto s = "a"; inteiro n = 1; se s == n entao { n = 2; }', "incompativeis")


def test_atribuicao_a_variavel_inexistente():
    erro('x = 1;', "usada antes de ser declarada")


def test_multiplicar_ou_dividir_texto_e_rejeitado():
    erro('texto a = "x"; texto b = a * a;', "multiplicar/dividir")
    erro('texto a = "x"; texto b = a / a;', "multiplicar/dividir")


# --- aritmética decimal -----------------------------------------------------

def test_soma_decimal_e_exata(capsys):
    rodar_finflow('moeda a = 0.10; moeda b = 0.20; moeda c = a + b; imprimir(c == 0.30);')
    assert capsys.readouterr().out.strip() == "verdadeiro"
    assert 0.1 + 0.2 != 0.3  # em ponto flutuante binario a mesma conta falha


def test_arredondamento_financeiro_meio_para_cima(capsys):
    rodar_finflow('moeda m = 2.675; imprimir(m); percentual p = 12.345%; imprimir(p);')
    assert capsys.readouterr().out.split("\n")[:2] == ["R$ 2.68", "12.35%"]


def test_divisao_inteira_e_real():
    ambiente = rodar_finflow('inteiro a = 7 / 2; moeda b = 7.00 / 2; moeda c = 5; moeda d = c / 2;',
                             imprimir_saida=False)
    assert ambiente['a'] == 3
    assert ambiente['b'] == Decimal('3.5')
    assert ambiente['d'] == Decimal('2.5')


def test_valores_injetados_viram_decimal():
    ambiente = rodar_finflow_com_dados_bc(
        'moeda total = valor + valor * taxa;',
        {'valor': ('moeda', 1000.0), 'taxa': ('percentual', 0.15)},
        imprimir_saida=False)
    assert ambiente['valor'] == Decimal('1000') and ambiente['total'] == Decimal('1150')
    assert isinstance(ambiente['taxa'], Decimal)


def test_percentual_tem_valor_decimal_exato():
    ambiente = rodar_finflow('percentual p = 5%; percentual q = 0.5%;', imprimir_saida=False)
    assert ambiente['p'] == Decimal('0.05') and ambiente['q'] == Decimal('0.005')
