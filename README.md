# FinFlow

Linguagem de domínio específico (DSL) para modelagem de operações financeiras — cálculo de juros, categorização de despesas, condições e laços sobre valores em `moeda`, `percentual`, `inteiro` e `texto`.

Trabalho prático final da disciplina de Teoria da Computação e Compiladores — FHO/Uniararas (Fundação Hermínio Ometto).

**Autores:** Guilherme Augusto Scaglia (RA 111598), João Pedro Denardo (RA 113036), Pedro Henrique Oliveira de Souza (RA 113364).

## O que já funciona

- **Lexer** (`finflow/lexer.py`) — análise léxica completa, com tratamento de palavras reservadas via tabela hash.
- **Parser** (`finflow/parser.py`) — gramática LALR(1), 29 regras de produção, 68 estados, 0 conflitos. Suporta `se/senao` (if), `para...ate...faca` (for) e `escolha/caso/padrao` (switch).
- **Análise semântica** (`finflow/semantica.py`) — tabela de símbolos e verificação de tipos. Rejeita, por exemplo, somar `moeda` com `percentual` diretamente, exigindo multiplicação explícita.
- **Interpretador** (`finflow/interpretador.py`) — execução real (tree-walking) sobre a AST.

## Instalação

Requer Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Como rodar um programa FinFlow

```bash
python main.py exemplos/juros.ff
```

Saída esperada:
```
cresceu
R$ 1050.00
```

Outros exemplos em `exemplos/`:
- `para_escolha.ff` — laço `para` e seleção `escolha`.
- `erro_tipo.ff` — demonstra a análise semântica rejeitando `moeda + percentual` direto.

## Como rodar os testes

```bash
pytest testes/ -v
```

ou, sem pytest instalado:
```bash
python testes/test_finflow.py
```

## Sintaxe da linguagem

```
moeda saldo = 1000.00;
percentual taxa = 5%;
inteiro parcelas = 12;
texto mensagem = "ola";

se saldo > 500 entao {
    imprimir("saldo alto");
} senao {
    imprimir("saldo normal");
}

para i = 1 ate 5 faca {
    imprimir(i);
}

escolha parcelas {
    caso 12: imprimir("anual");
    caso 6:  imprimir("semestral");
    padrao:  imprimir("outro");
}
```

Gramática formal completa (EBNF) e a fundamentação teórica de cada decisão de projeto estão no artigo do trabalho (`artigo_finflow.pdf` / `.tex`, entregue separadamente).

## Usando a FinFlow como biblioteca Python

```python
from finflow import rodar_finflow

rodar_finflow('''
    moeda saldo = 1000.00;
    percentual taxa = 5%;
    imprimir(saldo + saldo * taxa);
''')
```

## Estrutura do projeto

```
finflow_project/
├── finflow/            # o compilador (pacote Python)
│   ├── lexer.py
│   ├── parser.py
│   ├── semantica.py
│   └── interpretador.py
├── exemplos/           # programas .ff de exemplo
├── testes/             # suite de testes (pytest)
├── main.py             # CLI: python main.py arquivo.ff
└── requirements.txt
```

## Em desenvolvimento

- Integração com a API pública SGS do Banco Central (Selic, IPCA), permitindo que programas FinFlow operem sobre séries macroeconômicas reais em vez de apenas literais do código-fonte. Os módulos `semantica.py` e `interpretador.py` já aceitam variáveis pré-populadas (`tabela_inicial` / `ambiente_inicial`) para isso — ver `testes/test_finflow.py::test_dados_externos_pre_populados`.
