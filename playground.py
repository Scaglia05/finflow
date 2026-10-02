#!/usr/bin/env python3
"""
Playground web da FinFlow: escreva um programa, clique em Executar.

Uso:
    python playground.py              # abre http://127.0.0.1:8000
    python playground.py --port 8080
"""
import argparse
import glob
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from finflow import parse, analisar_semantica, executar, ErroSemantico, ErroExecucao, ErroBCB

RAIZ = os.path.dirname(os.path.abspath(__file__))

PAGINA = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"><title>FinFlow Playground</title>
<style>
body{font-family:system-ui,sans-serif;max-width:900px;margin:1.5rem auto;padding:0 1rem;color:#1a1a1a;background:#fff}
textarea{background:#fff;color:#1a1a1a}
textarea{width:100%;height:320px;font:14px/1.4 Consolas,monospace;padding:.6rem;box-sizing:border-box}
pre{background:#111;color:#e6e6e6;padding:.8rem;min-height:4rem;white-space:pre-wrap;border-radius:6px}
pre.erro{color:#ff8a80} button,select{font-size:1rem;padding:.4rem .8rem;margin-right:.5rem}
small{color:#555}
</style></head><body>
<h1>FinFlow Playground</h1>
<p><small>Dados reais do Banco Central via <code>buscar("selic", 2025)</code>. Séries: __SERIES__.</small></p>
<p><select id="ex"></select><button id="run">Executar (Ctrl+Enter)</button></p>
<textarea id="code" spellcheck="false"></textarea>
<h3>Saída</h3><pre id="out"></pre>
<script>
const $=id=>document.getElementById(id), exemplos=__EXEMPLOS__;
for(const n in exemplos){const o=document.createElement("option");o.textContent=n;$("ex").append(o)}
$("ex").onchange=()=>{$("code").value=exemplos[$("ex").value]};
async function run(){
  $("out").className="";$("out").textContent="Executando...";
  const r=await fetch("/run",{method:"POST",body:JSON.stringify({codigo:$("code").value})});
  const j=await r.json();
  $("out").className=j.erro?"erro":"";$("out").textContent=j.erro||j.saida.join("\\n");
}
$("run").onclick=run;
$("code").addEventListener("keydown",e=>{if(e.ctrlKey&&e.key==="Enter")run()});
$("ex").onchange();
</script></body></html>"""


def carregar_exemplos():
    exemplos = {}
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "exemplos", "*.ff"))):
        with open(caminho, encoding="utf-8") as f:
            exemplos[os.path.basename(caminho)] = f.read()
    return exemplos or {"novo.ff": 'imprimir("ola");\n'}


def rodar(codigo):
    try:
        ast = parse(codigo)
        tabela = analisar_semantica(ast)
        _, saida = executar(ast, tabela)
        return {"saida": saida}
    except (SyntaxError, ErroSemantico, ErroExecucao, ErroBCB) as e:
        return {"erro": f"{type(e).__name__}: {e}"}


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, status, tipo, corpo):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path != "/":
            return self._enviar(404, "text/plain", "nao encontrado")
        from finflow import SERIES
        pagina = (PAGINA.replace("__EXEMPLOS__", json.dumps(carregar_exemplos()).replace("</", "<\\/"))
                  .replace("__SERIES__", ", ".join(SERIES)))
        self._enviar(200, "text/html; charset=utf-8", pagina)

    def do_POST(self):
        if self.path != "/run":
            return self._enviar(404, "text/plain", "nao encontrado")
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            codigo = json.loads(self.rfile.read(tamanho))["codigo"]
        except (ValueError, KeyError):
            return self._enviar(400, "application/json", json.dumps({"erro": "requisicao invalida"}))
        self._enviar(200, "application/json", json.dumps(rodar(codigo)))

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sem-navegador", action="store_true")
    args = ap.parse_args()
    servidor = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"FinFlow Playground em {url}  (Ctrl+C para sair)")
    if not args.sem_navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
