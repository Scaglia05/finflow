"""
Integracao da FinFlow com a API publica SGS (Sistema Gerenciador de Series
Temporais) do Banco Central do Brasil. Sem autenticacao.

Esta camada e independente do compilador: o lexer/parser/semantica apenas
consultam o registro `SERIES` (nome logico -> codigo SGS, tipo FinFlow); a
rede so e acessada em tempo de execucao, pelo comando `buscar(...)`.
"""
import datetime as dt
import time
from dataclasses import dataclass
from functools import lru_cache

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
TIMEOUT_S = 30
TENTATIVAS = 3
JANELA_MAX_ANOS = 10  # a API limita consultas por periodo a 10 anos


class ErroBCB(RuntimeError):
    pass


@dataclass(frozen=True)
class Serie:
    codigo: int
    modo: str   # 'acumulado': composto dos valores mensais | 'ultimo': ultimo valor do periodo
    tipo: str   # tipo FinFlow do resultado: 'percentual' ou 'moeda'
    descricao: str


# A serie 432 do SGS e a META Selic (% a.a.), nao a Selic mensal: por isso
# 'selic' usa a 4390 (acumulada no mes) e 'meta_selic' usa a 432.
SERIES = {
    'selic': Serie(4390, 'acumulado', 'percentual', 'Selic acumulada no periodo (composta, base mensal)'),
    'cdi': Serie(4391, 'acumulado', 'percentual', 'CDI acumulado no periodo (composto, base mensal)'),
    'ipca': Serie(433, 'acumulado', 'percentual', 'IPCA acumulado no periodo (inflacao oficial)'),
    'igpm': Serie(189, 'acumulado', 'percentual', 'IGP-M acumulado no periodo'),
    'poupanca': Serie(196, 'acumulado', 'percentual', 'Rendimento acumulado da poupanca'),
    'meta_selic': Serie(432, 'ultimo', 'percentual', 'Meta Selic (% a.a.) vigente no fim do periodo'),
    'dolar': Serie(1, 'ultimo', 'moeda', 'Dolar comercial (venda), ultima cotacao do periodo, em R$'),
    'euro': Serie(21619, 'ultimo', 'moeda', 'Euro (venda), ultima cotacao do periodo, em R$'),
}


def _fmt(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


def _parse(s: str) -> dt.date:
    try:
        return dt.datetime.strptime(s, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        raise ErroBCB(f"data invalida '{s}': use o formato dd/mm/aaaa") from None


def _janelas(ini: dt.date, fim: dt.date):
    while ini <= fim:
        fim_janela = min(fim, dt.date(ini.year + JANELA_MAX_ANOS - 1, 12, 31))
        yield ini, fim_janela
        ini = fim_janela + dt.timedelta(days=1)


def _requisitar(codigo: int, ini: dt.date, fim: dt.date) -> list:
    import requests

    params = {"formato": "json", "dataInicial": _fmt(ini), "dataFinal": _fmt(fim)}
    ultimo_erro = None
    for tentativa in range(TENTATIVAS):
        try:
            resp = requests.get(URL_SGS.format(codigo=codigo), params=params, timeout=TIMEOUT_S)
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_erro = f"sem conexao com a API do Banco Central ({type(e).__name__})"
        else:
            if resp.status_code == 404:
                return []  # o SGS responde 404 quando nao ha dados no periodo
            if resp.status_code >= 500:
                ultimo_erro = f"API do Banco Central indisponivel (HTTP {resp.status_code})"
            elif resp.status_code != 200:
                raise ErroBCB(f"API do Banco Central recusou a consulta da serie {codigo} (HTTP {resp.status_code})")
            else:
                try:
                    linhas = resp.json()
                    return [(l["data"], float(l["valor"])) for l in linhas if l.get("valor") not in (None, "")]
                except (ValueError, KeyError, TypeError):
                    raise ErroBCB(f"resposta inesperada da API do Banco Central para a serie {codigo}") from None
        if tentativa < TENTATIVAS - 1:
            time.sleep(1 + tentativa)
    raise ErroBCB(f"falha ao consultar a serie {codigo}: {ultimo_erro}")


@lru_cache(maxsize=256)
def _valores(codigo: int, data_inicial: str, data_final: str) -> tuple:
    ini, fim = _parse(data_inicial), _parse(data_final)
    if ini > fim:
        raise ErroBCB(f"periodo invalido: {data_inicial} e posterior a {data_final}")
    valores = []
    for a, b in _janelas(ini, fim):
        valores.extend(_requisitar(codigo, a, b))
    return tuple(valores)


def buscar_valores(codigo: int, data_inicial: str, data_final: str) -> list:
    """Retorna [(data 'dd/mm/aaaa', valor float)] da serie no periodo."""
    return list(_valores(codigo, data_inicial, data_final))


def limpar_cache():
    _valores.cache_clear()


def _acumular(valores) -> float:
    acumulado = 1.0
    for _, v in valores:
        acumulado *= 1 + v / 100
    return acumulado - 1


def buscar_serie_bc(codigo_serie: int, data_inicial: str, data_final: str) -> float:
    """
    Variacao acumulada (produto composto, nao soma) de uma serie mensal do
    SGS no periodo, como fracao decimal (4.26% -> 0.0426), pronta para ser
    um valor `percentual` da FinFlow. Datas no formato 'dd/mm/aaaa'.
    Lanca ErroBCB (RuntimeError) se a API falhar ou nao retornar dados.
    """
    valores = buscar_valores(codigo_serie, data_inicial, data_final)
    if not valores:
        raise ErroBCB(f"a API nao retornou dados da serie {codigo_serie} entre {data_inicial} e {data_final}")
    return _acumular(valores)


def valor_serie(nome: str, ano_inicial: int, ano_final: int | None = None) -> float:
    """Valor da serie logica `nome` entre 1/jan/ano_inicial e 31/dez/ano_final (padrao: o mesmo ano)."""
    serie = SERIES.get(nome)
    if serie is None:
        raise ErroBCB(f"serie desconhecida '{nome}'. Disponiveis: {', '.join(SERIES)}")
    ano_final = ano_inicial if ano_final is None else ano_final
    hoje = dt.date.today()
    if ano_final < ano_inicial:
        raise ErroBCB(f"periodo invalido: ano final {ano_final} anterior ao inicial {ano_inicial}")
    if ano_inicial > hoje.year:
        raise ErroBCB(f"nao ha dados de '{nome}' para {ano_inicial} (ano no futuro)")
    ini = dt.date(ano_inicial, 1, 1)
    fim = min(dt.date(ano_final, 12, 31), hoje)
    valores = buscar_valores(serie.codigo, _fmt(ini), _fmt(fim))
    if not valores:
        raise ErroBCB(f"a API nao retornou dados de '{nome}' entre {_fmt(ini)} e {_fmt(fim)}")
    if serie.modo == 'acumulado':
        return _acumular(valores)
    ultimo = valores[-1][1]
    return ultimo / 100 if serie.tipo == 'percentual' else ultimo
