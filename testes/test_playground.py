"""Testes do backend da interface web (sem rede)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import playground


def test_rodar_devolve_todas_as_fases():
    r = playground.rodar('moeda a = 100.00;\npercentual t = 5%;\nimprimir(a + a * t);')
    assert r["erro"] is None
    assert [t["tipo"] for t in r["tokens"]][:3] == ["TIPO_MOEDA", "ID", "ATR"]
    assert r["arvore"][0].startswith("programa")
    assert r["tabela"] == [{"nome": "a", "tipo": "moeda"}, {"nome": "t", "tipo": "percentual"}]
    assert r["saida"] == ["R$ 105.00"]
    assert {v["nome"]: v["valor"] for v in r["variaveis"]}["t"] == "5.00%"
    assert set(r["tempos"]) == {"lexico", "sintatico", "semantico", "execucao"}


def test_rodar_informa_a_fase_do_erro():
    assert playground.rodar('moeda a = 1.0; percentual t = 5%; moeda x = a + t;')["erro"]["fase"] == "semantico"
    assert playground.rodar('moeda a = ;')["erro"]["fase"] == "sintatico"
    assert playground.rodar('moeda a = 1.0 $')["erro"]["fase"] == "lexico"
    assert playground.rodar('inteiro z = 0; inteiro r = 1 / z;')["erro"]["fase"] == "execucao"
    r = playground.rodar('moeda a = 1.0; percentual t = 5%; moeda x = a + t;')
    assert r["saida"] is None and r["tokens"] and r["arvore"]  # fases anteriores continuam disponiveis


def test_observador_registra_consultas_ao_banco_central(monkeypatch):
    from finflow import bcb
    bcb.limpar_cache()
    monkeypatch.setattr(bcb, "_requisitar", lambda c, i, f: [("01/01/2025", 1.0)])
    r = playground.rodar('percentual p = buscar("ipca", 2025); imprimir(p);')
    eventos = [e for e in r["bcb"] if e["tipo"] == "serie"]
    assert eventos and eventos[0]["serie"] == "ipca" and eventos[0]["cache"] is False
    assert r["saida"] == ["1.00%"]
    assert bcb.observador is None
    bcb.limpar_cache()
