"""
Testes da FinFlow. Rodar com: pytest testes/ -v
(ou, sem pytest instalado: python testes/test_finflow.py)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finflow import rodar_finflow, ErroSemantico


def test_para_acumulador():
    ambiente = rodar_finflow('''
        inteiro soma = 0;
        para i = 1 ate 5 faca {
            soma = soma + i;
        }
    ''', imprimir_saida=False)
    assert ambiente['soma'] == 15


def test_escolha_switch():
    ambiente = rodar_finflow('''
        inteiro categoria = 2;
        texto resultado = "nao definido";
        escolha categoria {
            caso 1: resultado = "baixo risco";
            caso 2: resultado = "risco moderado";
            padrao: resultado = "risco alto";
        }
    ''', imprimir_saida=False)
    assert ambiente['resultado'] == "risco moderado"


def test_juros_e_precedencia_correta():
    ambiente = rodar_finflow('''
        moeda saldo = 1000.00;
        percentual taxa = 5%;
        moeda saldo_final = saldo + saldo * taxa;
    ''', imprimir_saida=False)
    assert abs(ambiente['saldo_final'] - 1050.0) < 1e-9


def test_precedencia_soma_mult():
    ambiente = rodar_finflow('inteiro r = 2 + 3 * 4;', imprimir_saida=False)
    assert ambiente['r'] == 14  # nao 20 -- prova que * tem precedencia sobre +


def test_erro_moeda_mais_percentual():
    try:
        rodar_finflow('''
            moeda saldo = 100.00;
            percentual taxa = 5%;
            moeda total = saldo + taxa;
        ''', imprimir_saida=False)
        assert False, "deveria ter lancado ErroSemantico"
    except ErroSemantico:
        pass


def test_erro_variavel_nao_declarada():
    try:
        rodar_finflow('imprimir(nao_existe);', imprimir_saida=False)
        assert False, "deveria ter lancado ErroSemantico"
    except ErroSemantico:
        pass


def test_erro_redeclaracao():
    try:
        rodar_finflow('inteiro x = 1; inteiro x = 2;', imprimir_saida=False)
        assert False, "deveria ter lancado ErroSemantico"
    except ErroSemantico:
        pass


def test_dados_externos_pre_populados():
    """Simula uma variavel vinda de fora (ex: API do Banco Central)."""
    ambiente = rodar_finflow(
        'moeda total = valor_externo + valor_externo * taxa_externa;',
        tabela_inicial={
            'valor_externo': ('moeda', None),
            'taxa_externa': ('percentual', None),
        },
        ambiente_inicial={
            'valor_externo': 1000.0,
            'taxa_externa': 0.15,
        },
        imprimir_saida=False,
    )
    assert abs(ambiente['total'] - 1150.0) < 1e-9


if __name__ == "__main__":
    testes = [v for k, v in list(globals().items()) if k.startswith("test_")]
    falhas = 0
    for teste in testes:
        try:
            teste()
            print(f"OK   {teste.__name__}")
        except AssertionError as e:
            falhas += 1
            print(f"FAIL {teste.__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    sys.exit(1 if falhas else 0)
