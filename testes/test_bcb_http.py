"""
Testes da camada HTTP da integração com o Banco Central: códigos de resposta,
tentativas, respostas malformadas, observador e validações de valor_serie.
A função `requests.get` é substituída; nenhum teste acessa a rede.
"""
import os
import sys
from decimal import Decimal

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finflow import bcb, ErroBCB


class Resposta:
    def __init__(self, status, dados=None, json_invalido=False):
        self.status_code = status
        self._dados = dados
        self._invalido = json_invalido
        self.url = "https://api.bcb.gov.br/dados/serie/teste"

    def json(self):
        if self._invalido:
            raise ValueError("json invalido")
        return self._dados


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    bcb.limpar_cache()
    monkeypatch.setattr(bcb.time, "sleep", lambda s: None)
    yield
    bcb.observador = None
    bcb.limpar_cache()


def usar_respostas(monkeypatch, respostas):
    """Faz requests.get devolver (ou lançar) cada item de `respostas`, em ordem."""
    chamadas = []

    def falso(*args, **kwargs):
        chamadas.append((args, kwargs))
        item = respostas[min(len(chamadas), len(respostas)) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(requests, "get", falso)
    return chamadas


DADOS = [{"data": "01/01/2025", "valor": "1.00"}, {"data": "01/02/2025", "valor": ""},
         {"data": "01/03/2025", "valor": "2.00"}]


def test_resposta_valida_ignora_valores_vazios(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, DADOS)])
    valores = bcb.buscar_valores(433, "01/01/2025", "31/03/2025")
    assert valores == [("01/01/2025", 1.0), ("01/03/2025", 2.0)]


def test_404_significa_periodo_sem_dados(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(404)])
    assert bcb.buscar_valores(433, "01/01/2025", "31/03/2025") == []


def test_erro_5xx_e_repetido_ate_funcionar(monkeypatch):
    chamadas = usar_respostas(monkeypatch, [Resposta(500), Resposta(503), Resposta(200, DADOS)])
    assert len(bcb.buscar_valores(433, "01/01/2025", "31/03/2025")) == 2
    assert len(chamadas) == 3


def test_5xx_persistente_vira_erro_bcb(monkeypatch):
    chamadas = usar_respostas(monkeypatch, [Resposta(502)])
    with pytest.raises(ErroBCB, match="indisponivel"):
        bcb.buscar_valores(433, "01/01/2025", "31/03/2025")
    assert len(chamadas) == bcb.TENTATIVAS


def test_codigo_inesperado_e_recusa_imediata(monkeypatch):
    chamadas = usar_respostas(monkeypatch, [Resposta(403)])
    with pytest.raises(ErroBCB, match="recusou"):
        bcb.buscar_valores(433, "01/01/2025", "31/03/2025")
    assert len(chamadas) == 1


def test_json_malformado_vira_erro_bcb(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, json_invalido=True)])
    with pytest.raises(ErroBCB, match="inesperada"):
        bcb.buscar_valores(433, "01/01/2025", "31/03/2025")


def test_resposta_sem_campos_esperados_vira_erro_bcb(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, [{"valor": "1.0"}])])  # sem o campo "data"
    with pytest.raises(ErroBCB, match="inesperada"):
        bcb.buscar_valores(433, "01/01/2025", "31/03/2025")


def test_timeout_e_tratado_como_falha_de_conexao(monkeypatch):
    usar_respostas(monkeypatch, [requests.Timeout("lento")])
    with pytest.raises(ErroBCB, match="sem conexao"):
        bcb.buscar_valores(433, "01/01/2025", "31/03/2025")


def test_observador_recebe_consulta_e_serie(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, DADOS)])
    eventos = []
    bcb.observador = eventos.append
    resultado = bcb.valor_serie("ipca", 2025)
    tipos = [e["tipo"] for e in eventos]
    assert tipos == ["consulta", "serie"]
    assert eventos[0]["linhas"] == 2
    assert eventos[1]["serie"] == "ipca" and isinstance(eventos[1]["resultado"], float)
    assert resultado == Decimal("1.01") * Decimal("1.02") - 1


def test_segunda_consulta_usa_cache(monkeypatch):
    chamadas = usar_respostas(monkeypatch, [Resposta(200, DADOS)])
    bcb.valor_serie("ipca", 2025)
    eventos = []
    bcb.observador = eventos.append
    bcb.valor_serie("ipca", 2025)
    assert len(chamadas) == 1
    assert eventos[-1]["cache"] is True


def test_serie_de_cotacao_devolve_o_ultimo_valor_decimal(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, [{"data": "02/01/2025", "valor": "6.00"},
                                                 {"data": "31/12/2025", "valor": "5.55"}])])
    assert bcb.valor_serie("dolar", 2025) == Decimal("5.55")


def test_valor_serie_valida_argumentos():
    with pytest.raises(ErroBCB, match="desconhecida"):
        bcb.valor_serie("bitcoin", 2025)
    with pytest.raises(ErroBCB, match="periodo invalido"):
        bcb.valor_serie("ipca", 2025, 2020)
    with pytest.raises(ErroBCB, match="futuro"):
        bcb.valor_serie("ipca", 2999)


def test_valor_serie_sem_dados_lanca_erro(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(404)])
    with pytest.raises(ErroBCB, match="nao retornou dados"):
        bcb.valor_serie("ipca", 2025)


def test_buscar_serie_bc_devolve_float(monkeypatch):
    usar_respostas(monkeypatch, [Resposta(200, DADOS)])
    resultado = bcb.buscar_serie_bc(433, "01/01/2025", "31/03/2025")
    assert isinstance(resultado, float) and resultado == pytest.approx(1.01 * 1.02 - 1)
