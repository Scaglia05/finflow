#!/usr/bin/env python3
"""
Reproduz os experimentos do artigo sobre a implementacao atual.

Uso (a partir da raiz do repositorio):
    python tools/experimentos.py regras        # as regras de producao numeradas
    python tools/experimentos.py precedencia   # conflitos e arvores por tabela de precedencia
    python tools/experimentos.py traco         # traco do parser LALR(1) para r = a + b * c;
    python tools/experimentos.py exemplos      # linhas, tokens, nos da AST e tempos dos exemplos
    python tools/experimentos.py benchmark     # tempo por fase em funcao do tamanho do programa
    python tools/experimentos.py tudo          # todos os acima (nao inclui `rede`)
    python tools/experimentos.py rede          # consulta o SGS de verdade (exige internet)
Os tempos dependem da maquina e da rede; os demais numeros sao deterministicos.
"""
import glob
import io
import os
import platform
import re
import statistics
import sys
import time
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from ply.yacc import yacc, PlyLogger  # noqa: E402

import finflow.parser as parser_mod  # noqa: E402
from finflow import parse, analisar_semantica, executar, ErroSemantico  # noqa: E402
from finflow.lexer import lexer, tokens  # noqa: E402


# --- precedencia ------------------------------------------------------------

CONFIGURACOES = [
    ("Nenhuma", ()),
    ("Nivel unico (todos)", (('left', 'OP_OU', 'OP_E', 'OP_NAO', 'OP_REL', 'OP_SOMA', 'OP_MULT'),)),
    ("Aritmetica e relacional, sem logicos",
     (('left', 'OP_REL'), ('left', 'OP_SOMA'), ('left', 'OP_MULT'))),
    ("Seis niveis (final)", parser_mod.precedence),
]
EXPRESSOES = ["x = a + b * c;", "x = a * b + c;", "x = p ou q e r;"]


def _infixa(no):
    if no[0] == 'binop':
        return f"({_infixa(no[2])} {no[1]} {_infixa(no[3])})"
    return no[1]


def _construir(precedencia):
    """Reconstroi o parser com outra tabela de precedencia; devolve (parser, conflitos, estados)."""
    modulo = types.ModuleType("gramatica_experimental")
    modulo.__file__ = parser_mod.__file__
    modulo.tokens = tokens
    modulo.precedence = precedencia
    for nome in dir(parser_mod):
        if nome.startswith("p_"):
            setattr(modulo, nome, getattr(parser_mod, nome))
    avisos = io.StringIO()
    depuracao = io.StringIO()
    p = yacc(module=modulo, debug=True, debuglog=PlyLogger(depuracao), write_tables=False,
             errorlog=PlyLogger(avisos))
    achados = re.findall(r"(\d+) shift/reduce conflict", avisos.getvalue())
    reduce_reduce = re.findall(r"(\d+) reduce/reduce conflict", avisos.getvalue())
    conflitos = (int(achados[0]) if achados else 0) + (int(reduce_reduce[0]) if reduce_reduce else 0)
    estados = len(re.findall(r"^state \d+", depuracao.getvalue(), re.M))
    return p, conflitos, estados


def precedencia():
    print("| Configuracao | Conflitos | Estados | " + " | ".join(EXPRESSOES) + " |")
    for nome, prec in CONFIGURACOES:
        p, conflitos, estados = _construir(prec)
        arvores = []
        for expr in EXPRESSOES:
            lexer.lineno = 1
            ast = p.parse(expr, lexer=lexer)
            arvores.append(_infixa(ast[1][0][2]))
        print(f"| {nome} | {conflitos} | {estados} | " + " | ".join(arvores) + " |")


# --- traco do parser --------------------------------------------------------

def traco(entrada="r = a + b * c;"):
    p = parser_mod.parser
    regras = {i: prod.str for i, prod in enumerate(p.productions)}
    buffer = io.StringIO()
    lexer.lineno = 1
    p.parse(entrada, lexer=lexer, debug=PlyLogger(buffer))
    linhas = buffer.getvalue().splitlines()
    passo = 0
    estado = pilha = None
    print(f"Entrada: {entrada}")
    print(f"{'#':>3}  {'Pilha':<44} {'Lookahead':<10} Acao")
    for linha in linhas:
        if linha.startswith("State  :"):
            estado = linha.split(":")[1].strip()
        elif linha.startswith("Stack  :"):
            pilha = linha.split(":", 1)[1].strip()
        elif linha.startswith("Action :"):
            passo += 1
            acao = linha.split(":", 1)[1].strip()
            if pilha.startswith(". "):
                pilha_simbolos, lookahead = "", pilha[2:]
            else:
                pilha_simbolos, _, lookahead = pilha.partition(" . ")
            achado = re.match(r"LexToken\((\w+)", lookahead)
            lookahead = achado.group(1) if achado else lookahead
            if acao.startswith("Shift"):
                destino = re.search(r"state (\d+)", acao).group(1)
                texto = f"shift {destino}"
            elif acao.startswith("Reduce"):
                corpo = re.search(r"\[(.*?)\] with", acao).group(1)
                numero = next((n for n, s in regras.items() if s.replace(" ", "") == corpo.replace(" ", "")), "?")
                texto = f"reduce {numero}"
            else:
                texto = acao.split(" ")[0].lower()
            print(f"{passo:>3}  {pilha_simbolos:<44} {lookahead:<10} {texto}")


def regras():
    for i, producao in enumerate(parser_mod.parser.productions):
        print(f"{i:>2} {producao.str}")
    print(f"{len(parser_mod.parser.productions)} regras (a de numero 0 e a regra aumentada)")


# --- exemplos e benchmark ---------------------------------------------------

def contar_nos(x):
    if isinstance(x, tuple) and x and isinstance(x[0], str):
        return 1 + sum(contar_nos(v) for v in x[1:])
    if isinstance(x, list):
        return sum(contar_nos(v) for v in x)
    return 0


def mediana_ms(funcao, repeticoes):
    tempos = []
    for _ in range(repeticoes):
        t0 = time.perf_counter()
        funcao()
        tempos.append((time.perf_counter() - t0) * 1000)
    return statistics.median(tempos)


def tokenizar(codigo):
    lexer.lineno = 1
    lexer.input(codigo)
    return sum(1 for _ in iter(lexer.token, None))


def exemplos():
    print("| Programa | Linhas | Tokens | Nos AST | Analise (ms) | Execucao (ms) |")
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "exemplos", "*.ff"))):
        codigo = open(caminho, encoding="utf-8").read()
        nome = os.path.basename(caminho)
        linhas = sum(1 for l in codigo.splitlines() if l.strip())
        tokens_n = tokenizar(codigo)
        ast = parse(codigo)
        nos = contar_nos(ast)
        def analisar():
            try:
                analisar_semantica(parse(codigo))
            except ErroSemantico:
                pass  # o tempo ate a rejeicao tambem e medido

        analise = mediana_ms(analisar, 50)
        try:
            tabela = analisar_semantica(ast)
        except ErroSemantico:
            print(f"| {nome} | {linhas} | {tokens_n} | {nos} | {analise:.2f} | rejeitado na analise |")
            continue
        if "buscar" in codigo:
            print(f"| {nome} | {linhas} | {tokens_n} | {nos} | {analise:.2f} | requer rede |")
        else:
            execucao = mediana_ms(lambda: executar(ast, tabela), 50)
            print(f"| {nome} | {linhas} | {tokens_n} | {nos} | {analise:.2f} | {execucao:.3f} |")


def programa_sintetico(blocos):
    cabecalho = "moeda saldo = 1000.00;\npercentual taxa = 1%;\ninteiro n = 0;\n"
    bloco = "saldo = saldo + saldo * taxa;\nn = n + 1;\nse saldo > 1000 entao {\n    n = n + 2;\n}\n"
    return cabecalho + bloco * blocos


def benchmark(tamanhos=(10, 20, 50, 100, 200, 400), repeticoes=15):
    print(f"Python {platform.python_version()} em {platform.system()} {platform.release()}; "
          f"mediana de {repeticoes} execucoes")
    print("linhas,tokens,lexico_ms,sintatico_ms,semantico_ms,execucao_ms")
    for blocos in tamanhos:
        codigo = programa_sintetico(blocos)
        linhas = sum(1 for l in codigo.splitlines() if l.strip())
        n_tokens = tokenizar(codigo)
        ast = parse(codigo)
        tabela = analisar_semantica(ast)
        lex = mediana_ms(lambda: tokenizar(codigo), repeticoes)
        lex_parse = mediana_ms(lambda: parse(codigo), repeticoes)
        sem = mediana_ms(lambda: analisar_semantica(ast), repeticoes)
        exe = mediana_ms(lambda: executar(ast, tabela), repeticoes)
        print(f"{linhas},{n_tokens},{lex:.2f},{max(lex_parse - lex, 0):.2f},{sem:.2f},{exe:.2f}")


# --- rede (exige internet) --------------------------------------------------

def rede(ano=2025, pausa=0.5):
    """Consulta o SGS de verdade: valores por serie, conferencia independente, janelas e latencia."""
    import requests
    from finflow import bcb

    eventos = []
    bcb.observador = eventos.append
    bcb.limpar_cache()
    print(f"Consultas ao SGS em {time.strftime('%Y-%m-%d')}, ano {ano}")
    print("| Serie | SGS | Modo | Linhas | Consultas | Tempo (ms) | Valor |")
    for nome, serie in bcb.SERIES.items():
        eventos.clear()
        t0 = time.perf_counter()
        valor = bcb.valor_serie(nome, ano)
        ms = round((time.perf_counter() - t0) * 1000)
        resumo = next(e for e in eventos if e["tipo"] == "serie")
        consultas = sum(1 for e in eventos if e["tipo"] == "consulta")
        mostrado = f"{valor * 100:.2f}%" if serie.tipo == "percentual" else f"R$ {valor:.4f}"
        print(f"| {nome} | {serie.codigo} | {serie.modo} | {resumo['valores']} | {consultas} | {ms} | {mostrado} |")
        time.sleep(pausa)

    # Conferencia independente: a serie 13522 do SGS e o IPCA acumulado em 12 meses, calculado pelo IBGE.
    oficial = bcb.buscar_valores(13522, f"01/12/{ano}", f"31/12/{ano}")[0][1]
    calculado = bcb.valor_serie("ipca", ano) * 100
    print(f"\nConferencia do IPCA {ano}: composto pela FinFlow = {calculado:.4f}% ; serie 13522 (IBGE) = {oficial:.2f}%")

    # Janelas: uma serie diaria de 16 anos exige mais de uma consulta (limite de 10 anos).
    eventos.clear()
    t0 = time.perf_counter()
    bcb.valor_serie("dolar", ano - 15, ano)
    ms = round((time.perf_counter() - t0) * 1000)
    consultas = [e["linhas"] for e in eventos if e["tipo"] == "consulta"]
    print(f"Janelas: dolar {ano - 15}-{ano} = {sum(consultas)} linhas em {len(consultas)} consultas {consultas}, {ms} ms")

    # Limite de 10 anos em series diarias, pedido sem dividir a janela.
    time.sleep(pausa)
    resp = requests.get(bcb.URL_SGS.format(codigo=1),
                        params={"formato": "json", "dataInicial": f"01/01/{ano - 10}", "dataFinal": f"31/12/{ano}"},
                        timeout=bcb.TIMEOUT_S)
    print(f"Limite: dolar com 11 anos em uma so consulta -> HTTP {resp.status_code}")

    # Cache e latencia.
    bcb.limpar_cache()
    frios = []
    for _ in range(5):
        bcb.limpar_cache()
        t0 = time.perf_counter()
        bcb.valor_serie("ipca", ano)
        frios.append((time.perf_counter() - t0) * 1000)
        time.sleep(pausa)
    t0 = time.perf_counter()
    bcb.valor_serie("ipca", ano)
    quente = (time.perf_counter() - t0) * 1000
    print(f"Latencia (ipca {ano}, 5 repeticoes sem cache): mediana {statistics.median(frios):.0f} ms, "
          f"min {min(frios):.0f}, max {max(frios):.0f}; com cache: {quente:.3f} ms")
    bcb.observador = None


COMANDOS = {"regras": regras, "precedencia": precedencia, "traco": traco, "exemplos": exemplos,
            "benchmark": benchmark}
COMANDOS_COM_REDE = {"rede": rede}  # fora de `tudo`: exigem internet


def main():
    args = sys.argv[1:]
    if len(args) != 1 or args[0] not in (*COMANDOS, *COMANDOS_COM_REDE, "tudo"):
        print(__doc__)
        sys.exit(1)
    if args[0] in COMANDOS_COM_REDE:
        print(f"\n== {args[0]} ==")
        COMANDOS_COM_REDE[args[0]]()
        return
    for nome in (COMANDOS if args[0] == "tudo" else [args[0]]):
        print(f"\n== {nome} ==")
        COMANDOS[nome]()


if __name__ == "__main__":
    main()
