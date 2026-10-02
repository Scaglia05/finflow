#!/usr/bin/env python3
"""
Interface web da FinFlow: escreva um programa, execute e veja cada fase do
compilador (tokens, arvore, tipos), as consultas ao Banco Central e o resultado.

Uso:
    python playground.py              # abre http://127.0.0.1:8000
    python playground.py --port 8080
"""
import argparse
import glob
import json
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from finflow import (parse, analisar_semantica, executar, ErroSemantico, ErroExecucao,
                     ErroBCB, SERIES, bcb)
from finflow.interpretador import formatar
from finflow.lexer import lexer

RAIZ = os.path.dirname(os.path.abspath(__file__))
ERROS = (SyntaxError, ErroSemantico, ErroExecucao, ErroBCB)
_trava = threading.Lock()  # lexer e parser do PLY sao globais


def carregar_exemplos():
    exemplos = {}
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "exemplos", "*.ff"))):
        with open(caminho, encoding="utf-8") as f:
            exemplos[os.path.basename(caminho)] = f.read()
    return exemplos or {"novo.ff": 'imprimir("ola");\n'}


def listar_tokens(codigo):
    lexer.lineno = 1
    lexer.input(codigo)
    return [{"tipo": t.type, "valor": t.value, "linha": t.lineno} for t in iter(lexer.token, None)]


def _no(x, nivel, saida):
    pad = "  " * nivel
    if isinstance(x, tuple) and x and isinstance(x[0], str):
        folhas = [repr(v) if isinstance(v, str) else str(v) for v in x[1:] if not isinstance(v, (tuple, list))]
        saida.append(f"{pad}{x[0]} {' '.join(folhas)}".rstrip())
        for v in x[1:]:
            if isinstance(v, (tuple, list)):
                _no(v, nivel + 1, saida)
    elif isinstance(x, list):
        saida.append(f"{pad}[bloco]")
        for v in x:
            _no(v, nivel + 1, saida)


def arvore(ast):
    linhas = []
    _no(ast, 0, linhas)
    return linhas


def rodar(codigo):
    """Executa o programa e devolve o que cada fase produziu (ou onde falhou)."""
    r = {"tokens": None, "arvore": None, "tabela": None, "bcb": [], "saida": None,
         "variaveis": None, "tempos": {}, "erro": None}
    fase = "lexico"
    with _trava:
        bcb.observador = r["bcb"].append
        try:
            t = time.perf_counter()
            r["tokens"] = listar_tokens(codigo)
            r["tempos"]["lexico"] = _ms(t)

            fase, t = "sintatico", time.perf_counter()
            ast = parse(codigo)
            r["arvore"] = arvore(ast)
            r["tempos"]["sintatico"] = _ms(t)

            fase, t = "semantico", time.perf_counter()
            tabela = analisar_semantica(ast)
            r["tabela"] = [{"nome": n, "tipo": tp} for n, (tp, _) in tabela.items()]
            r["tempos"]["semantico"] = _ms(t)

            fase, t = "execucao", time.perf_counter()
            ambiente, saida = executar(ast, tabela)
            r["saida"] = saida
            r["variaveis"] = [{"nome": n, "tipo": tp, "valor": formatar(ambiente[n], tp)}
                              for n, (tp, _) in tabela.items() if n in ambiente]
            r["tempos"]["execucao"] = _ms(t)
        except ERROS as e:
            r["erro"] = {"fase": fase, "tipo": type(e).__name__, "mensagem": str(e)}
        finally:
            bcb.observador = None
    return r


def _ms(t0):
    return round((time.perf_counter() - t0) * 1000)


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, status, tipo, corpo):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(RAIZ, "web", "index.html"), encoding="utf-8") as f:
                return self._enviar(200, "text/html; charset=utf-8", f.read())
        if self.path == "/dados":
            corpo = json.dumps({"exemplos": carregar_exemplos(),
                                "series": {n: s.descricao for n, s in SERIES.items()}})
            return self._enviar(200, "application/json", corpo)
        self._enviar(404, "text/plain", "nao encontrado")

    def do_POST(self):
        if self.path != "/run":
            return self._enviar(404, "text/plain", "nao encontrado")
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            codigo = json.loads(self.rfile.read(tamanho))["codigo"]
        except (ValueError, KeyError):
            return self._enviar(400, "application/json", json.dumps({"erro": {"mensagem": "requisicao invalida"}}))
        self._enviar(200, "application/json", json.dumps(rodar(codigo)))

    def log_message(self, *args):
        pass


def servir(host="127.0.0.1", port=8000, abrir_navegador=True):
    servidor = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"FinFlow em {url}  (Ctrl+C para sair)")
    if abrir_navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sem-navegador", action="store_true")
    args = ap.parse_args()
    servir(args.host, args.port, not args.sem_navegador)


if __name__ == "__main__":
    main()
