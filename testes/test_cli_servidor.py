"""
Testes da linha de comando (main.py) e do servidor da interface web
(playground.py). O servidor sobe em uma porta livre e a rede é simulada.
"""
import http.client
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import main
import playground
from finflow import bcb, SERIES


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    bcb.limpar_cache()
    dados = {s.codigo: [("02/01/2025", 1.0), ("31/12/2025", 1.0)] for s in SERIES.values()}
    monkeypatch.setattr(bcb, "_requisitar", lambda codigo, ini, fim: dados.get(codigo, []))
    yield
    bcb.limpar_cache()


def executar(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["main.py", *args])
    with pytest.raises(SystemExit) as saida:
        main.main()
    return saida.value.code


# --- linha de comando -------------------------------------------------------

def test_cli_series_lista_todas(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--series"])
    main.main()
    saida = capsys.readouterr().out
    assert all(nome in saida for nome in SERIES)


def test_cli_executa_um_programa(monkeypatch, capsys):
    assert executar(monkeypatch, os.path.join(RAIZ, "exemplos", "juros.ff")) == 0
    assert capsys.readouterr().out.split("\n")[:2] == ["cresceu", "R$ 1050.00"]


def test_cli_programa_com_erro_sai_com_1(monkeypatch, capsys):
    assert executar(monkeypatch, os.path.join(RAIZ, "exemplos", "erro_tipo.ff")) == 1
    assert "erro de tipo" in capsys.readouterr().out


def test_cli_arquivo_inexistente(monkeypatch, capsys):
    assert executar(monkeypatch, "nao_existe.ff") == 1
    assert "nao encontrado" in capsys.readouterr().out


def test_cli_argumentos_invalidos_mostram_uso(monkeypatch, capsys):
    assert executar(monkeypatch, "--opcao-invalida") == 1
    assert "Uso:" in capsys.readouterr().out


def test_cli_console_roda_todos_os_exemplos(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--console"])
    main.main()
    saida = capsys.readouterr().out
    quantidade = len([f for f in os.listdir(os.path.join(RAIZ, "exemplos")) if f.endswith(".ff")])
    assert f"{quantidade} exemplos executados" in saida


def test_cli_sem_argumentos_abre_a_interface(monkeypatch):
    chamadas = []
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(playground, "servir", lambda: chamadas.append(True))
    main.main()
    assert chamadas == [True]


# --- servidor web -----------------------------------------------------------

@pytest.fixture
def servidor():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), playground.Handler)
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def obter(porta, caminho):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}{caminho}") as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def enviar(porta, caminho, corpo):
    pedido = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}", data=corpo, method="POST")
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8")
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, texto


def test_pagina_inicial(servidor):
    status, corpo = obter(servidor, "/")
    assert status == 200 and "FinFlow" in corpo


def test_dados_listam_exemplos_e_series(servidor):
    status, corpo = obter(servidor, "/dados")
    dados = json.loads(corpo)
    assert status == 200 and "juros.ff" in dados["exemplos"] and set(dados["series"]) == set(SERIES)


def test_rota_inexistente_devolve_404(servidor):
    assert obter(servidor, "/nada")[0] == 404
    assert enviar(servidor, "/outra", b"{}")[0] == 404


def test_executar_programa(servidor):
    status, resposta = enviar(servidor, "/run", json.dumps({"codigo": "moeda a = 1.50; imprimir(a * 2);"}).encode())
    assert status == 200 and resposta["saida"] == ["R$ 3.00"] and resposta["erro"] is None
    assert resposta["tokens"][3]["valor"] == "1.50"


def test_executar_programa_com_erro_informa_a_fase(servidor):
    status, resposta = enviar(servidor, "/run", json.dumps({"codigo": "inteiro n = 10.50;"}).encode())
    assert status == 200 and resposta["erro"]["fase"] == "semantico"


def test_corpo_invalido_devolve_400(servidor):
    assert enviar(servidor, "/run", b"isto nao e json")[0] == 400
    assert enviar(servidor, "/run", b'{"outro": 1}')[0] == 400
    assert enviar(servidor, "/run", b'{"codigo": 5}')[0] == 400


@pytest.mark.parametrize("tamanho, esperado", [("abc", 400), ("-5", 400),
                                                 (str(playground.MAX_CORPO + 1), 413)])
def test_content_length_invalido_ou_grande_demais(servidor, tamanho, esperado):
    conexao = http.client.HTTPConnection("127.0.0.1", servidor)
    conexao.putrequest("POST", "/run")
    conexao.putheader("Content-Length", tamanho)
    conexao.endheaders()
    assert conexao.getresponse().status == esperado
    conexao.close()


def test_exemplos_padrao_quando_a_pasta_esta_vazia(monkeypatch, tmp_path):
    monkeypatch.setattr(playground, "RAIZ", str(tmp_path))
    assert playground.carregar_exemplos() == {"novo.ff": 'imprimir("ola");\n'}
