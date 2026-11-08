"""
Testes complementares: operadores de comparação, ramo `padrao`, `buscar` com
período, nós desconhecidos (defesa contra AST inválida) e a inicialização
do servidor e da linha de comando. Rodam sem rede.
"""
import os
import runpy
import sys
from decimal import Decimal

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import playground
from finflow import rodar_finflow, bcb, ErroSemantico
from finflow.interpretador import avaliar, executar_comando, converter
from finflow.semantica import tipo_de, checar_comando


@pytest.fixture
def sem_rede(monkeypatch):
    bcb.limpar_cache()
    dados = {433: [("01/06/2024", 1.0), ("01/01/2025", 2.0)]}
    monkeypatch.setattr(bcb, "_requisitar", lambda codigo, ini, fim: dados.get(codigo, []))
    yield
    bcb.limpar_cache()


def test_operadores_de_comparacao():
    ambiente = rodar_finflow('''
        inteiro a = 0; inteiro b = 0; inteiro c = 0;
        se 1 != 2 e 2 >= 2 e 2 <= 3 entao { a = 1; }
        se 1 != 1 ou 1 >= 2 ou 3 <= 2 entao { b = 1; }
        se 2 < 3 e 3 > 2 e 2 == 2 entao { c = 1; }
    ''', imprimir_saida=False)
    assert (ambiente['a'], ambiente['b'], ambiente['c']) == (1, 0, 1)


def test_escolha_cai_no_padrao_quando_nenhum_caso_coincide():
    ambiente = rodar_finflow('''
        inteiro k = 9;
        texto r = "?";
        escolha k {
            caso 1: r = "um";
            caso 2: r = "dois";
            padrao: r = "outro";
        }
    ''', imprimir_saida=False)
    assert ambiente['r'] == "outro"


def test_escolha_sem_padrao_e_sem_correspondencia_nao_faz_nada():
    ambiente = rodar_finflow('inteiro k = 9; inteiro r = 0; escolha k { caso 1: r = 1; }', imprimir_saida=False)
    assert ambiente['r'] == 0


def test_buscar_com_periodo_de_dois_anos(sem_rede):
    ambiente = rodar_finflow('percentual p = buscar("ipca", 2024, 2025);', imprimir_saida=False)
    assert ambiente['p'] == Decimal('1.01') * Decimal('1.02') - 1


def test_conversao_para_decimal():
    assert converter(1.5, 'moeda') == Decimal('1.5') and isinstance(converter(1.5, 'moeda'), Decimal)
    assert converter(2, 'percentual') == Decimal(2)
    assert converter(2, 'inteiro') == 2 and isinstance(converter(2, 'inteiro'), int)
    assert converter(True, 'moeda') is True
    assert converter("x", 'texto') == "x"


def test_nos_desconhecidos_sao_rejeitados():
    with pytest.raises(RuntimeError, match="expressao nao suportada"):
        avaliar(('inexistente',), {}, {})
    with pytest.raises(RuntimeError, match="comando nao reconhecido"):
        executar_comando(('inexistente',), {}, {}, [])
    with pytest.raises(ErroSemantico, match="expressao nao reconhecida"):
        tipo_de(('inexistente',), {})
    with pytest.raises(ErroSemantico, match="comando nao reconhecido"):
        checar_comando(('inexistente',), {})


def test_checar_comando_sem_pilha_de_escopos_usa_a_tabela():
    tabela = {'x': ('inteiro', None)}
    checar_comando(('imprimir', ('id', 'x', 1), 1), tabela)


# --- inicialização ----------------------------------------------------------

class ServidorFalso:
    criados = []

    def __init__(self, endereco, handler):
        self.endereco = endereco
        ServidorFalso.criados.append(endereco)

    def serve_forever(self):
        raise KeyboardInterrupt


def test_servir_encerra_com_ctrl_c(monkeypatch, capsys):
    abertos = []
    ServidorFalso.criados.clear()
    monkeypatch.setattr(playground, "ThreadingHTTPServer", ServidorFalso)
    monkeypatch.setattr(playground.webbrowser, "open", abertos.append)
    playground.servir("127.0.0.1", 8123, abrir_navegador=True)
    playground.servir("127.0.0.1", 8124, abrir_navegador=False)
    assert ServidorFalso.criados == [("127.0.0.1", 8123), ("127.0.0.1", 8124)]
    assert abertos == ["http://127.0.0.1:8123"]
    assert "FinFlow em http://127.0.0.1:8123" in capsys.readouterr().out


def test_main_do_playground_repassa_os_argumentos(monkeypatch):
    chamadas = []
    monkeypatch.setattr(playground, "servir", lambda *a: chamadas.append(a))
    monkeypatch.setattr(sys, "argv", ["playground.py", "--port", "9000", "--sem-navegador"])
    playground.main()
    assert chamadas == [("127.0.0.1", 9000, False)]


def test_main_py_executavel_como_script(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--series"])
    runpy.run_path(os.path.join(RAIZ, "main.py"), run_name="__main__")
    assert "selic" in capsys.readouterr().out


def test_playground_executavel_como_script(monkeypatch):
    chamadas = []
    monkeypatch.setattr(sys, "argv", ["playground.py", "--sem-navegador"])
    monkeypatch.setattr("http.server.ThreadingHTTPServer", ServidorFalso)
    monkeypatch.setattr("webbrowser.open", chamadas.append)
    runpy.run_path(os.path.join(RAIZ, "playground.py"), run_name="__main__")
    assert chamadas == []
