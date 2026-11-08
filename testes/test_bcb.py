"""
Testes da integracao com o Banco Central e das extensoes da linguagem
(buscar, e/ou/nao). A rede e simulada; o teste ao vivo so roda com
FINFLOW_LIVE=1. Rodar com: pytest testes/ -v
"""
import datetime as dt
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finflow import (rodar_finflow, rodar_finflow_com_dados_bc, buscar_serie_bc,
                     ErroSemantico, ErroExecucao, ErroBCB)
from finflow import bcb


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Substitui a requisicao HTTP por dados fixos e zera o cache."""
    bcb.limpar_cache()
    dados = {
        4390: [("01/01/2025", 1.0), ("01/02/2025", 1.0)],
        433: [("01/01/2025", 0.5), ("01/02/2025", 0.5)],
        196: [("01/01/2025", 0.6), ("01/02/2025", 0.6)],
        1: [("02/01/2025", 6.0), ("31/12/2025", 5.5)],
        432: [("01/01/2025", 12.25), ("31/12/2025", 15.0)],
    }
    monkeypatch.setattr(bcb, "_requisitar", lambda codigo, ini, fim: dados.get(codigo, []))
    yield
    bcb.limpar_cache()


def test_acumulado_e_composto_nao_soma():
    assert buscar_serie_bc(4390, "01/01/2025", "31/12/2025") == pytest.approx(1.01 ** 2 - 1)


def test_periodo_sem_dados_lanca_erro_claro():
    with pytest.raises(ErroBCB, match="nao retornou dados"):
        buscar_serie_bc(999999, "01/01/2025", "31/12/2025")


def test_data_invalida_e_periodo_invertido():
    with pytest.raises(ErroBCB, match="dd/mm/aaaa"):
        buscar_serie_bc(433, "2025-01-01", "31/12/2025")
    with pytest.raises(ErroBCB, match="posterior"):
        buscar_serie_bc(433, "31/12/2025", "01/01/2025")


def test_janelas_de_no_maximo_10_anos():
    janelas = list(bcb._janelas(dt.date(2000, 1, 1), dt.date(2025, 12, 31)))
    assert len(janelas) == 3
    assert janelas[0][0] == dt.date(2000, 1, 1) and janelas[-1][1] == dt.date(2025, 12, 31)
    assert all(b.year - a.year <= 9 for a, b in janelas)


def test_api_fora_do_ar_vira_erro_bcb(monkeypatch):
    import requests

    def falha(*a, **k):
        raise requests.ConnectionError("sem rede")

    monkeypatch.undo()  # volta o _requisitar real
    monkeypatch.setattr(requests, "get", falha)
    monkeypatch.setattr(bcb.time, "sleep", lambda s: None)
    with pytest.raises(ErroBCB, match="sem conexao"):
        buscar_serie_bc(433, "01/01/2025", "31/12/2025")


def test_buscar_na_linguagem_percentual_e_moeda():
    amb = rodar_finflow('''
        percentual ipca = buscar("ipca", 2025);
        moeda dolar = buscar("dolar", 2025);
        percentual meta = buscar("meta_selic", 2025);
    ''', imprimir_saida=False)
    assert amb['ipca'] == Decimal('1.005') ** 2 - 1
    assert amb['dolar'] == Decimal('5.5')   # ultimo valor do periodo
    assert amb['meta'] == Decimal('0.15')


def test_buscar_com_ano_vindo_de_variavel_e_para():
    amb = rodar_finflow('''
        inteiro n = 0;
        para ano = 2025 ate 2025 faca {
            percentual p = buscar("ipca", ano);
            se p > 1% entao { n = n + 1; }
        }
    ''', imprimir_saida=False)
    assert amb['n'] == 1


def test_buscar_serie_desconhecida_e_tipo_errado():
    with pytest.raises(ErroSemantico, match="desconhecida"):
        rodar_finflow('percentual x = buscar("bitcoin", 2025);', imprimir_saida=False)
    with pytest.raises(ErroSemantico):
        rodar_finflow('percentual x = buscar("dolar", 2025);', imprimir_saida=False)  # dolar e moeda
    with pytest.raises(ErroSemantico, match="inteiro"):
        rodar_finflow('percentual x = buscar("ipca", "2025");', imprimir_saida=False)


def test_buscar_ano_futuro_lanca_erro():
    with pytest.raises(ErroBCB, match="futuro"):
        rodar_finflow('percentual x = buscar("ipca", 2999);', imprimir_saida=False)


def test_operadores_logicos():
    amb = rodar_finflow('''
        inteiro a = 0; inteiro b = 0; inteiro c = 0;
        se 1 < 2 e 3 > 2 entao { a = 1; }
        se 1 > 2 ou 3 > 2 entao { b = 1; }
        se nao 1 > 2 entao { c = 1; }
    ''', imprimir_saida=False)
    assert (amb['a'], amb['b'], amb['c']) == (1, 1, 1)


def test_precedencia_e_sobre_ou():
    amb = rodar_finflow('''
        inteiro r = 0;
        se 1 < 2 ou 1 > 2 e 1 > 2 entao { r = 1; }
    ''', imprimir_saida=False)
    assert amb['r'] == 1  # a ou (b e c)


def test_logico_exige_condicoes():
    with pytest.raises(ErroSemantico):
        rodar_finflow('inteiro x = 1; se x e 2 > 1 entao { imprimir(x); }', imprimir_saida=False)
    with pytest.raises(ErroSemantico):
        rodar_finflow('inteiro x = 1; se nao x entao { imprimir(x); }', imprimir_saida=False)


def test_razao_entre_moedas_e_percentual():
    amb = rodar_finflow('''
        moeda a = 1100.00; moeda b = 1000.00;
        percentual ganho = (a - b) / b;
    ''', imprimir_saida=False)
    assert amb['ganho'] == Decimal('0.1')


def test_moeda_vezes_moeda_e_erro_de_tipo():
    with pytest.raises(ErroSemantico):
        rodar_finflow('moeda a = 2.0; moeda b = a * a;', imprimir_saida=False)


def test_divisao_por_zero_e_divisao_inteira():
    with pytest.raises(ErroExecucao, match="divisao por zero"):
        rodar_finflow('inteiro z = 0; inteiro r = 1 / z;', imprimir_saida=False)
    assert rodar_finflow('inteiro r = 7 / 2;', imprimir_saida=False)['r'] == 3


def test_comentarios():
    amb = rodar_finflow('''# cabecalho
inteiro x = 1; # ao lado
# fim''', imprimir_saida=False)
    assert amb['x'] == 1


def test_imprimir_booleano(capsys):
    rodar_finflow('imprimir(1 < 2);')
    assert capsys.readouterr().out.strip() == "verdadeiro"


def test_rodar_finflow_com_dados_bc_exemplo_do_brief(capsys):
    codigo = '''
        moeda valor_aplicado = 10000.00;
        moeda valor_final = valor_aplicado + valor_aplicado * selic_ano;
        percentual rendimento_real = ((1 + selic_ano) / (1 + ipca_ano)) - 1;
        imprimir(valor_final);
        imprimir(rendimento_real);
    '''
    rodar_finflow_com_dados_bc(codigo, {
        'selic_ano': ('percentual', 0.15),
        'ipca_ano': ('percentual', 0.0426),
    })
    saida = capsys.readouterr().out.split("\n")
    assert saida[0] == "R$ 11500.00"
    assert saida[1] == "10.30%"


@pytest.mark.skipif(os.environ.get("FINFLOW_LIVE") != "1", reason="teste ao vivo: defina FINFLOW_LIVE=1")
def test_ao_vivo_selic_e_ipca_2025(monkeypatch):
    monkeypatch.undo()
    bcb.limpar_cache()
    assert buscar_serie_bc(4390, "01/01/2025", "31/12/2025") == pytest.approx(0.1433, abs=1e-3)
    assert buscar_serie_bc(433, "01/01/2025", "31/12/2025") == pytest.approx(0.0426, abs=1e-3)
