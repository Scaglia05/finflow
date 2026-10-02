# FinFlow

Linguagem de domínio específico (DSL) para modelagem de operações financeiras — cálculo de juros, comparação de investimentos e condições e laços sobre valores em `moeda`, `percentual`, `inteiro` e `texto`, **com dados reais do Banco Central do Brasil** (Selic, CDI, IPCA, poupança, dólar...) disponíveis direto na linguagem.

Trabalho prático final da disciplina de Teoria da Computação e Compiladores — FHO/Uniararas (Fundação Hermínio Ometto).

**Autores:** Guilherme Augusto Scaglia (RA 111598), João Pedro Denardo (RA 113036), Pedro Henrique Oliveira de Souza (RA 113364).

## Teste rápido (para quem vai avaliar)

Requer Python 3.10+ e internet (os dados vêm da API pública do Banco Central, sem chave).

```bash
git clone https://github.com/Scaglia05/finflow.git
cd finflow
pip install -r requirements.txt
python main.py
```

`python main.py` executa **todos** os exemplos da pasta `exemplos/` (com dados reais do Banco Central) e em seguida abre o playground web em `http://127.0.0.1:8000`: escolha um exemplo, edite à vontade e clique em **Executar** (Ctrl+Enter). Outras formas:

```bash
python main.py --sem-playground           # só roda os exemplos
python main.py exemplos/rendimento.ff     # roda um único programa
python main.py --series                   # séries do Banco Central disponíveis
python playground.py                      # só o editor web
python -m pytest testes -v                # testes automatizados (rodam à parte)
```

(`erro_tipo.ff` falha de propósito: demonstra a análise semântica rejeitando `moeda + percentual`.)

## O que a linguagem faz

```
moeda aplicado = 10000.00;
percentual selic = buscar("selic", 2025);      # dado real do Banco Central
percentual inflacao = buscar("ipca", 2025);

moeda final = aplicado + aplicado * selic;
percentual real = ((1 + selic) / (1 + inflacao)) - 1;

se selic > inflacao e real > 5% entao {        # if / senao, com e / ou / nao
    imprimir("A Selic venceu a inflação.");
} senao {
    imprimir("A inflação comeu o rendimento.");
}

para ano = 2020 ate 2025 faca {                # for
    imprimir(buscar("ipca", ano));
}

escolha ano {                                  # switch
    caso 2025: imprimir("ano atual");
    padrao:    imprimir("outro ano");
}
```

Comentários começam com `#` e vão até o fim da linha.

### Tipos

`moeda` (R$), `percentual` (`5%` vale `0.05`), `inteiro`, `texto`. O sistema de tipos impede erros de unidade:
`moeda + percentual` é rejeitado (use `valor + valor * taxa`); `moeda * moeda` também; `moeda / moeda` resulta em `percentual` (razão).
Condições (`se`) exigem comparação; `e`, `ou`, `nao` operam sobre condições.

### Comandos

| Comando | Exemplo |
|---|---|
| declaração / atribuição | `moeda saldo = 1000.00;` · `saldo = saldo + 10.00;` |
| condicional | `se saldo > 500 entao { ... } senao { ... }` |
| repetição | `para i = 1 ate 5 faca { ... }` |
| seleção | `escolha parcelas { caso 12: ... caso 6: ... padrao: ... }` |
| saída | `imprimir(saldo);` |
| dado do Banco Central | `buscar("selic", 2025)` ou `buscar("ipca", 2020, 2025)` (período de anos) |

### Séries do Banco Central em `buscar("série", ano)`

| Série | Tipo | O que retorna | SGS |
|---|---|---|---|
| `selic` | percentual | Selic acumulada (composta) no período | 4390 |
| `cdi` | percentual | CDI acumulado (composto) | 4391 |
| `ipca` | percentual | IPCA (inflação) acumulado | 433 |
| `igpm` | percentual | IGP-M acumulado | 189 |
| `poupanca` | percentual | Rendimento acumulado da poupança | 196 |
| `meta_selic` | percentual | Meta Selic (% a.a.) no fim do período | 432 |
| `dolar` | moeda | Última cotação do dólar (venda) no período | 1 |
| `euro` | moeda | Última cotação do euro (venda) no período | 21619 |

Séries mensais são **compostas** (produto de `1 + taxa`, não soma). O ano pode ser uma variável (`para ano = ... buscar("ipca", ano)`). Erros claros: série desconhecida e tipo incompatível são detectados na análise semântica; ano futuro, API fora do ar ou sem dados geram `ErroBCB` em execução. Os resultados ficam em cache durante a execução.

Observação técnica: a série SGS 432 é a *meta* Selic anual, não a Selic mensal; por isso `selic` usa a 4390.

## Como funciona (arquitetura)

- **Lexer** (`finflow/lexer.py`) — PLY, palavras reservadas por tabela hash.
- **Parser** (`finflow/parser.py`) — gramática LALR(1), 34 regras de produção (incluindo a regra aumentada), 83 estados, 0 conflitos; gera a AST.
- **Análise semântica** (`finflow/semantica.py`) — tabela de símbolos e verificação de tipos.
- **Interpretador** (`finflow/interpretador.py`) — execução tree-walking sobre a AST.
- **Integração com o Banco Central** (`finflow/bcb.py`) — camada desacoplada do compilador: registro de séries, requisições à API SGS (janelas de até 10 anos, tentativas com espera, cache) e agregação.

## Usando como biblioteca Python

```python
from finflow import rodar_finflow, buscar_serie_bc, rodar_finflow_com_dados_bc

rodar_finflow('imprimir(buscar("ipca", 2025));')

selic = buscar_serie_bc(4390, "01/01/2025", "31/12/2025")   # 0.1433 -> 14,33%
rodar_finflow_com_dados_bc('imprimir(valor + valor * taxa);',
                           {'valor': ('moeda', 1000.0), 'taxa': ('percentual', selic)})
```

## Testes

```bash
pytest testes/ -v                      # usa dados simulados, não precisa de internet
FINFLOW_LIVE=1 pytest testes/ -v       # inclui teste contra a API real (Windows PowerShell: $env:FINFLOW_LIVE=1)
```

## Estrutura do projeto

```
├── finflow/            # o compilador (pacote Python)
│   ├── lexer.py  parser.py  semantica.py  interpretador.py
│   └── bcb.py          # integração com a API do Banco Central
├── exemplos/           # programas .ff (rendimento, inflacao_por_ano, cambio, ...)
├── testes/             # suíte de testes (pytest)
├── Docs/               # artigo e materiais da disciplina
├── main.py             # roda todos os exemplos + playground (ou um arquivo .ff)
├── playground.py       # editor web local
└── requirements.txt
```
