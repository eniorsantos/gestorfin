"""CLI: finllm db|cvm|rag|bench ..."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .agentes import executar_agentes
from .avaliacao import carregar_referencia, comparar_com_referencia, gerar_relatorio_regressao, salvar_referencia
from .auditoria import listar_consultas, registrar_consulta
from .backtest import run_backtest
from .config import settings
from .cvm.load import normalizar_setores
from .db import connect
from .fundamentalista import calcular_indicadores
from .ocr import extrair_texto_pdf, tem_texto
from .ollama_client import OllamaClient
from .rag.cache import cache_embeddings, cache_respostas
from .rag.rerank_crossencoder import rerank_cross_encoder
from .rag.sql_direct import tentar_resposta_direta
from .rag.tools import TOOLS_REAIS
from .tecnico import Cotacao, calcular_indicadores as calcular_tecnicos

app = typer.Typer(no_args_is_help=True, help="Análise financeira com LLM local: RAG sobre dados da CVM + benchmark")
db_app, cvm_app, rag_app, bench_app = (typer.Typer(no_args_is_help=True) for _ in range(4))
auditoria_app = typer.Typer(no_args_is_help=True)
dashboard_app = typer.Typer(no_args_is_help=True)
indicadores_app = typer.Typer(no_args_is_help=True)
tecnico_app = typer.Typer(no_args_is_help=True)
agentes_app = typer.Typer(no_args_is_help=True)
backtest_app = typer.Typer(no_args_is_help=True)
avaliacao_app = typer.Typer(no_args_is_help=True)
app.add_typer(db_app, name="db", help="Banco de dados")
app.add_typer(cvm_app, name="cvm", help="Dados abertos da CVM")
app.add_typer(rag_app, name="rag", help="Indexação e consulta (RAG)")
app.add_typer(bench_app, name="bench", help="Benchmark de modelos")
app.add_typer(auditoria_app, name="auditoria", help="Auditoria de consultas")
app.add_typer(indicadores_app, name="indicadores", help="Indicadores fundamentalistas")
app.add_typer(tecnico_app, name="tecnico", help="Indicadores técnicos (Fase 4)")
app.add_typer(agentes_app, name="agentes", help="Agentes de análise (Fase 5)")
app.add_typer(backtest_app, name="backtest", help="Backtest point-in-time (Fase 6)")
app.add_typer(avaliacao_app, name="avaliacao", help="Avaliação contínua/regressão (Fase 8)")
app.add_typer(dashboard_app, name="dashboard", help="Dashboard Streamlit (Fase 7)")
console = Console()


def parse_years(s: str) -> list[int]:
    out: list[int] = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        elif part.strip():
            out.append(int(part))
    return sorted(set(out))


def _csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _resolve(conn, empresas: list[str] | None) -> list[int] | None:
    if not empresas:
        return None
    from .rag.entities import resolve_empresa

    cds = []
    for name in empresas:
        try:
            cd, denom = resolve_empresa(conn, name)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
        console.print(f"  {name!r} -> {denom} (CD_CVM {cd})")
        cds.append(cd)
    return cds


EMP = typer.Option(None, "--empresa", "-e", help="Nome/alias da empresa (repita para várias)")
YEARS = typer.Option("2023-2024", help="Ex.: 2024 | 2022-2024 | 2021,2023")


# ---------------- db ----------------
@db_app.command("init")
def db_init() -> None:
    """Cria extensões, tabelas e índices."""
    from .schema import init_db

    with connect() as conn:
        init_db(conn, settings.embed_dim)
    console.print("[green]schema ok[/green]")


@db_app.command("stats")
def db_stats() -> None:
    """Contagens por tabela."""
    with connect() as conn, conn.cursor() as cur:
        t = Table("tabela", "linhas")
        for name in ("empresas", "demonstracoes", "documentos_ipe", "chunks"):
            cur.execute(f"SELECT count(*) FROM {name}")
            t.add_row(name, f"{cur.fetchone()[0]:,}")
        cur.execute("SELECT source, count(*) FROM chunks GROUP BY 1")
        for s, n in cur.fetchall():
            t.add_row(f"  chunks[{s}]", f"{n:,}")
        console.print(t)


# ---------------- cvm ----------------
@cvm_app.command("download")
def cvm_download(years: str = YEARS, kinds: str = "cad,dfp,itr", force: bool = False) -> None:
    """Baixa cadastro (cad), DFP e ITR (e ipe, se pedido) para data/raw."""
    from .cvm.download import NotPublished, fetch

    for kind in _csv(kinds):
        for y in ([None] if kind == "cad" else parse_years(years)):
            try:
                p = fetch(kind, y, force=force)
                console.print(f"[green]ok[/green] {kind} {y or ''} -> {p}")
            except NotPublished as e:
                console.print(f"[yellow]não publicado[/yellow] {e}")


@cvm_app.command("load")
def cvm_load(
    years: str = YEARS, kinds: str = "dfp,itr", statements: str = "DRE,BPA,BPP", empresa: list[str] = EMP,
) -> None:
    """Carrega cadastro + DFP/ITR no Postgres (idempotente)."""
    from .cvm.download import local_path
    from .cvm.load import load_cadastro, load_zip

    with connect() as conn:
        cad = local_path("cad")
        if cad.exists():
            console.print(f"cadastro: {load_cadastro(conn, cad):,} companhias")
        cds = _resolve(conn, empresa)
        for kind in _csv(kinds):
            for y in parse_years(years):
                p = local_path(kind, y)
                if not p.exists():
                    console.print(f"[yellow]ausente[/yellow] {p} (rode `cvm download`)")
                    continue
                console.print(f"{kind.upper()} {y}")
                n = load_zip(conn, p, tipo_doc=kind, statements=_csv(statements), cd_cvms=cds, log=console.print)
                console.print(f"  total: {n:,}")


@cvm_app.command("ipe-categories")
def ipe_categories(year: int = 2024) -> None:
    """Lista as categorias IPE existentes (para configurar IPE_CATEGORIES)."""
    from .cvm.ipe import list_categories

    t = Table("categoria", "documentos")
    for c, n in list_categories(year):
        t.add_row(c, f"{n:,}")
    console.print(t)


@cvm_app.command("ipe-sync")
def ipe_sync(years: str = "2024", empresa: list[str] = EMP, categories: str = "") -> None:
    """Registra documentos IPE (fatos relevantes etc.) como pendentes de indexação."""
    from .cvm.ipe import sync_index

    with connect() as conn:
        cds = _resolve(conn, empresa)
        cats = _csv(categories) or settings.categories
        n = sync_index(conn, parse_years(years), cds, cats)
    console.print(f"{n:,} documentos registrados ({', '.join(cats)})")


# ---------------- rag ----------------
@rag_app.command("index-statements")
def rag_index_statements(
    years: str = YEARS, empresa: list[str] = EMP, kinds: str = "DFP,ITR", statements: str = "DRE,BPA,BPP",
    cons: str = "con,ind",
) -> None:
    """Gera cartões textuais das demonstrações e indexa (embeddings) no pgvector."""
    from .rag.cards import iter_card_chunks
    from .rag.index import index_chunks

    client = OllamaClient()
    with connect() as conn:
        cds = _resolve(conn, empresa)
        gen = iter_card_chunks(conn, cd_cvms=cds, years=parse_years(years), kinds=_csv(kinds),
                               statements=_csv(statements), cons=_csv(cons))
        new, skipped = index_chunks(conn, client, gen, progress=lambda n, s: console.print(f"  novos={n:,} já_existiam={s:,}", end="\r"))
    console.print(f"\n[green]concluído[/green]: {new:,} novos, {skipped:,} já existiam")


@rag_app.command("index-ipe")
def rag_index_ipe(limit: int = 50, empresa: list[str] = EMP) -> None:
    """Baixa, extrai texto, divide e indexa documentos IPE pendentes."""
    from .cvm.ipe import process_pending

    client = OllamaClient()
    with connect() as conn:
        stats = process_pending(conn, client, limit=limit, cd_cvms=_resolve(conn, empresa), log=console.print)
    console.print(stats)


@rag_app.command("search")
def rag_search(query: str, k: int = 6, empresa: str = typer.Option(None, "--empresa", "-e")) -> None:
    """Só a recuperação (sem LLM) — útil para depurar o RAG."""
    from .rag.retrieve import retrieve

    client = OllamaClient()
    with connect() as conn:
        cd = _resolve(conn, [empresa])[0] if empresa else None
        hits, filters = retrieve(conn, client, query, k=k, cd_cvm=cd)
    console.print(f"filtros: {filters}")
    for i, h in enumerate(hits, 1):
        console.print(f"\n[bold][{i}] {h.via} score={h.score:.4f}[/bold] {h.title}")
        console.print(h.content[:600])


@rag_app.command("ask")
def rag_ask(
    question: str, model: str = typer.Option(None, help="Padrão: LLM_MODEL"), empresa: str = typer.Option(None, "--empresa", "-e"),
    k: int = 6, verbose: bool = False, use_tools: bool = typer.Option(True, help="Permitir uso de tools (function calling)"),
    data_entrega: str = typer.Option(None, "--data-entrega", help="Point-in-time: só documentos entregues até esta data (YYYY-MM-DD)"),
) -> None:
    """Pergunta com resposta fundamentada, citações e validação numérica."""
    from .rag.answer import answer, format_hit
    from datetime import date

    dt_entrega = date.fromisoformat(data_entrega) if data_entrega else None
    client = OllamaClient()
    with connect() as conn:
        cd = _resolve(conn, [empresa])[0] if empresa else None
        r = answer(conn, client, question, model=model or settings.llm_model, cd_cvm=cd, k=k,
                   use_tools=use_tools, data_entrega_max=dt_entrega)
    a = r["answer"]
    if a is None:
        console.print("[red]O modelo não devolveu JSON válido.[/red]")
        raise typer.Exit(1)
    console.print(f"\n[bold]{a.resposta}[/bold]")
    if a.valor is not None:
        console.print(f"valor: {a.valor:,.2f} {a.unidade or ''}")
    v = r["validation"]
    if v and not v.ok:
        console.print(f"[yellow]⚠ números não encontrados no contexto: {v.unsupported}[/yellow]")
    if a.nao_encontrado:
        console.print("[yellow]modelo indicado: informação não encontrada no contexto[/yellow]")
    if r.get("tool_called"):
        console.print(f"[cyan]tool usada:[/cyan] {r['tool_called']} -> {r.get('tool_result')}")
    console.print("\nFontes:")
    for i, h in enumerate(r["hits"], 1):
        mark = "*" if i in a.citacoes else " "
        console.print(f" {mark}{format_hit(i, h)}")
    if verbose:
        console.print(f"\nfiltros={r['filters']} tentativas={len(r['attempts'])} tempo={r['elapsed_s']:.1f}s")
        console.print(r["attempts"])
    console.print("\n[dim]Apoio à análise; não é recomendação de investimento.[/dim]")


# ---------------- bench ----------------
@bench_app.command("hardware")
def bench_hardware() -> None:
    """Mostra o hardware detectado."""
    from .bench.hardware import detect

    console.print_json(json.dumps(detect(OllamaClient()), ensure_ascii=False))


@bench_app.command("build")
def bench_build(
    n_fact: int = 40, n_abstain: int = 15, n_calc: int = 10, seed: int = 42,
    only_indexed: bool = typer.Option(False, help="Usa só empresas já indexadas (necessário p/ --context retrieved)"),
    out: Path = Path("benchmark/datasets/cvm_qa_v1.jsonl"),
) -> None:
    """Gera o dataset de avaliação a partir do banco (verdade = dados da CVM)."""
    from .bench.dataset import build_dataset, save

    with connect() as conn:
        items, meta = build_dataset(conn, n_fact=n_fact, n_abstain=n_abstain, n_calc=n_calc, seed=seed,
                                    only_indexed=only_indexed)
    save(items, meta, out)
    console.print(f"[green]{len(items)} itens[/green] -> {out}  {meta['counts']}")


@bench_app.command("run")
def bench_run(
    models_file: Path = Path("benchmark/models.yaml"),
    dataset: Path = Path("benchmark/datasets/cvm_qa_v1.jsonl"),
    context: str = typer.Option("gold", help="gold = contexto correto + distratores | retrieved = RAG real"),
    repeats: int = 1, max_mem_gb: float = typer.Option(None, help="Ignora modelos com min_mem_gb maior"),
    only: str = typer.Option("", help="Lista de modelos (csv) para rodar"),
    pull: bool = typer.Option(False, help="Baixa modelos ausentes via API do Ollama"),
    out: Path = typer.Option(None),
) -> None:
    """Roda o benchmark nos modelos do YAML e gera o relatório."""
    from .bench import dataset as ds
    from .bench.hardware import detect
    from .bench.report import write_report
    from .bench.runner import load_models, run_benchmark
    from .bench.tasks import builtin_items

    client = OllamaClient()
    models = load_models(models_file, only=_csv(only) or None, max_mem_gb=max_mem_gb)
    if not models:
        console.print("[red]Nenhum modelo selecionado (veja --max-mem-gb / --only).[/red]")
        raise typer.Exit(1)
    have = set(client.tags())
    for m in models:
        if m.name not in have:
            if pull:
                console.print(f"baixando {m.name} ...")
                client.pull(m.name)
            else:
                console.print(f"[yellow]ausente:[/yellow] {m.name} — `docker compose exec ollama ollama pull {m.name}` ou use --pull")
    models = [m for m in models if m.name in set(client.tags())]
    if not models:
        raise typer.Exit(1)

    items = (ds.load(dataset) if dataset.exists() else []) + builtin_items()
    if not dataset.exists():
        console.print("[yellow]dataset RAG ausente: rodando só classif/tools (use `bench build`).[/yellow]")
    out = out or Path("benchmark/results") / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hardware.json").write_text(json.dumps(detect(client), indent=2, ensure_ascii=False))
    (out / "run_config.json").write_text(json.dumps({
        "context": context, "repeats": repeats, "models": [m.name for m in models], "items": len(items),
        "num_ctx": settings.llm_num_ctx, "temperature": settings.llm_temperature, "seed": settings.llm_seed,
    }, indent=2))
    conn = connect() if context == "retrieved" else None
    try:
        run_benchmark(client, models, items, out, context_mode=context, repeats=repeats, conn=conn, log=console.print)
    finally:
        if conn:
            conn.close()
    console.print(f"\n[green]relatório:[/green] {write_report(out)}")


@bench_app.command("report")
def bench_report(run: Path = typer.Option(None, help="Diretório da execução (padrão: a mais recente)")) -> None:
    """(Re)gera report.md/summary.csv de uma execução."""
    from .bench.report import write_report

    if run is None:
        runs = sorted(p for p in Path("benchmark/results").iterdir() if p.is_dir())
        if not runs:
            console.print("[red]nenhuma execução encontrada[/red]")
            raise typer.Exit(1)
        run = runs[-1]
    console.print(f"[green]{write_report(run)}[/green]")
    console.print((run / "summary.csv").read_text())


# ---------------- auditoria ----------------
@auditoria_app.command("list")
def auditoria_list(limit: int = typer.Option(20, help="Quantidade de registros")):
    """Lista as últimas consultas auditadas."""
    rows = listar_consultas(limit=limit)
    t = Table("id", "criado_em", "modelo", "pergunta")
    for r in rows:
        t.add_row(str(r["id"]), str(r["criado_em"]), r["modelo"], r["pergunta"][:80])
    console.print(t)


# ---------------- indicadores ----------------
@indicadores_app.command("calc")
def indicadores_calc(ticker: str, data: str = typer.Option(None, help="Data-base YYYY-MM-DD")):
    """Calcula indicadores fundamentalistas de um ticker."""
    from datetime import datetime

    dt_refer = datetime.strptime(data, "%Y-%m-%d").date() if data else None
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cd_cvm, denom FROM empresas WHERE denom ILIKE %s ORDER BY cd_cvm LIMIT 1",
                (f"%{ticker}%",),
            )
            row = cur.fetchone()
            if not row:
                console.print(f"[red]Empresa não encontrada para {ticker!r}[/red]")
                raise typer.Exit(1)
            cd_cvm, denom = row
            if dt_refer is None:
                cur.execute(
                    """
                    SELECT MAX(dt_refer) FROM demonstracoes
                    WHERE cd_cvm=%s AND tipo_doc='DFP' AND consolidacao='con'
                      AND demonstracao IN ('DRE','BPA','BPP')
                    """,
                    (cd_cvm,),
                )
                dt_row = cur.fetchone()
                dt_refer = dt_row[0] if dt_row and dt_row[0] else None
    if dt_refer is None:
        console.print(f"[red]Sem DFP consolidada para {denom}[/red]")
        raise typer.Exit(1)
    ind = calcular_indicadores(cd_cvm, dt_refer)
    t = Table("indicador", "valor")
    t.add_row("Empresa", ind.ticker)
    t.add_row("CD_CVM", str(ind.cd_cvm))
    t.add_row("Data referência", ind.dt_refer)
    t.add_row("P/L", f"{ind.pl:.2f}" if ind.pl is not None else "n/d")
    t.add_row("ROE", f"{ind.roe:.2%}" if ind.roe is not None else "n/d")
    t.add_row("ROIC", f"{ind.roic:.2%}" if ind.roic is not None else "n/d")
    t.add_row("Dív. Líq./EBITDA", f"{ind.divida_liquida_ebitda:.2f}" if ind.divida_liquida_ebitda is not None else "n/d")
    t.add_row("F-Score", str(ind.f_score) if ind.f_score is not None else "n/d")
    console.print(t)


# ---------------- cvm dfc/dva ----------------
@cvm_app.command("load-dfc-dva")
def cvm_load_dfc_dva(
    years: str = "2022-2024", empresa: list[str] = typer.Option(None, "--empresa", "-e"),
    statements: str = "DFC_MD,DFC_MI,DVA,DRA",
) -> None:
    """Carrega DFC (fluxo de caixa) e DVA (valor adicionado) a partir dos zips DFP."""
    from .cvm.download import local_path
    from .cvm.load import load_zip

    with connect() as conn:
        cds = _resolve(conn, empresa)
        for y in parse_years(years):
            p = local_path("dfp", y)
            if not p.exists():
                console.print(f"[yellow]ausente[/yellow] {p} (rode `cvm download --kinds dfp`)")
                continue
            console.print(f"DFP {y} (DFC/DVA)")
            n = load_zip(conn, p, tipo_doc="dfp", statements=_csv(statements), cd_cvms=cds, log=console.print)
            console.print(f"  total: {n:,}")
    console.print("[green]DFC/DVA carregado[/green]")


# ---------------- tecnico ----------------
@tecnico_app.command("sinal")
def tecnico_sinal(ticker: str, periodo: str = typer.Option("6m", help="1m, 6m, 1a, 5a")):
    """Sinal técnico agregado de um ticker."""
    from .rag.tools import get_sinal_tecnico

    resultado = get_sinal_tecnico(ticker, periodo)
    t = Table("campo", "valor")
    for k, v in resultado.items():
        t.add_row(k, str(v))
    console.print(t)


@tecnico_app.command("indicadores")
def tecnico_indicadores(ticker: str, periodo: str = typer.Option("6m", help="1m, 6m, 1a, 5a")):
    """Indicadores técnicos completos de um ticker."""
    from .rag.tools import get_indicadores_tecnicos

    resultado = get_indicadores_tecnicos(ticker, periodo)
    if "mensagem" in resultado:
        console.print(f"[yellow]{resultado['mensagem']}[/yellow]")
        raise typer.Exit(1)
    t = Table("indicador", "valor")
    for k, v in resultado.items():
        t.add_row(k, str(v))
    console.print(t)


# ---------------- agentes ----------------
@agentes_app.command("analisar")
def agentes_analisar(
    ticker: str,
    use_tecnico: bool = typer.Option(True, help="Incluir análise técnica"),
    use_fundamentalista: bool = typer.Option(True, help="Incluir análise fundamentalista"),
):
    """Executa os agentes (fundamentalista, técnico, risco, sintetizador)."""
    indicadores = {}
    tecnicos = {}
    contexto = {}

    if use_fundamentalista:
        from datetime import datetime
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cd_cvm, denom FROM empresas WHERE denom ILIKE %s ORDER BY cd_cvm LIMIT 1",
                    (f"%{ticker}%",),
                )
                row = cur.fetchone()
                if not row:
                    console.print(f"[red]Empresa não encontrada para {ticker!r}[/red]")
                    raise typer.Exit(1)
                cd_cvm, denom = row
                cur.execute(
                    """
                    SELECT MAX(dt_refer) FROM demonstracoes
                    WHERE cd_cvm=%s AND tipo_doc='DFP' AND consolidacao='con'
                      AND demonstracao IN ('DRE','BPA','BPP')
                    """,
                    (cd_cvm,),
                )
                dt_row = cur.fetchone()
                dt_refer = dt_row[0] if dt_row and dt_row[0] else None
        if dt_refer is None:
            console.print(f"[red]Sem DFP consolidada para {denom}[/red]")
            raise typer.Exit(1)
        ind = calcular_indicadores(cd_cvm, dt_refer)
        indicadores = {
            "pl": ind.pl,
            "roe": ind.roe,
            "roic": ind.roic,
            "divida_liquida_ebitda": ind.divida_liquida_ebitda,
            "f_score": ind.f_score,
        }
        contexto["empresa"] = ind.ticker
        contexto["data_referencia"] = ind.dt_refer

    if use_tecnico:
        from .rag.tools import get_indicadores_tecnicos
        tecnicos = get_indicadores_tecnicos(ticker, "6m")

    resultado = executar_agentes(ticker, indicadores=indicadores, tecnicos=tecnicos, contexto=contexto)

    t = Table("campo", "valor")
    t.add_row("Ticker", resultado.ticker)
    t.add_row("Sinal final", resultado.sinal_final)
    t.add_row("Confiança", str(resultado.confianca_final))
    t.add_row("Score composto", str(resultado.score_composto))
    t.add_row("Síntese", resultado.justificativa_sintese)
    console.print(t)
    console.print("\nRiscos principais:")
    for r in resultado.riscos_principais:
        console.print(f"  - {r}")
    console.print("\nPareceres por agente:")
    for p in resultado.pareceres:
        console.print(f"  [{p.nome}] {p.sinal} (conf {p.confianca}): {p.justificativa}")


# ---------------- backtest ----------------
@backtest_app.command("run")
def backtest_run(
    ticker: str = typer.Option("PETR4", help="Ticker para backtest"),
    capital: float = typer.Option(100000.0, help="Capital inicial"),
    comissao: float = typer.Option(0.001, help="Comissão por operação"),
    n_dias: int = typer.Option(252, help="Número de dias simulados"),
) -> None:
    """Executa backtest point-in-time com sinais dos agentes."""
    import random
    from datetime import date, timedelta

    rng = random.Random(42)
    preco_base = 30.0
    precos = [preco_base]
    datas = []
    sinais = []
    data_atual = date.today() - timedelta(days=n_dias)
    for i in range(n_dias):
        variacao = rng.gauss(0, 0.02)
        preco = max(preco_base * (1 + variacao), 1.0)
        precos.append(preco)
        datas.append((data_atual + timedelta(days=i)).isoformat())
        # sinal simples: compra se preço caiu >1%, venda se subiu >1%
        if variacao < -0.01:
            sinais.append(1)
        elif variacao > 0.01:
            sinais.append(-1)
        else:
            sinais.append(0)
        preco_base = preco

    resultado = run_backtest(
        nome=f"backtest-{ticker}",
        ticker=ticker,
        precos=precos,
        datas=datas,
        sinais=sinais,
        capital_inicial=capital,
        comissao=comissao,
    )

    t = Table("métrica", "valor")
    t.add_row("Ticker", resultado.ticker)
    t.add_row("Período", f"{resultado.periodo_ini} a {resultado.periodo_fim}")
    t.add_row("Retorno total", f"{resultado.retorno_total:.2%}")
    t.add_row("Sharpe", f"{resultado.sharpe:.2f}")
    t.add_row("Drawdown máximo", f"{resultado.drawdown_max:.2%}")
    t.add_row("Nº operações", str(resultado.n_operacoes))
    console.print(t)


# ---------------- avaliacao ----------------
@avaliacao_app.command("regressao")
def avaliacao_regressao(
    resumo_csv: Path,
    referencia_json: Path = typer.Option(None, help="Arquivo de referência (opcional)"),
    limiar: float = typer.Option(0.05, help="Queda máxima tolerada na acurácia"),
) -> None:
    """Compara um resumo do benchmark com uma referência (regressão CI)."""
    import csv

    resumo_atual = []
    with open(resumo_csv, newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            resumo_atual.append(linha)

    referencia = {}
    if referencia_json and referencia_json.exists():
        referencia = carregar_referencia(referencia_json)

    resultados = comparar_com_referencia(resumo_atual, referencia, limiar_queda=limiar)
    saida = resumo_csv.parent / "regressao_report.md"
    gerar_relatorio_regressao(resultados, saida)

    regressoes = [r for r in resultados if r.regressou]
    console.print(f"Analisados {len(resultados)} (modelo, tarefa). Regressões: {len(regressoes)}")
    console.print(f"Relatório: {saida}")
    if regressoes:
        raise typer.Exit(1)


@avaliacao_app.command("salvar-referencia")
def avaliacao_salvar_referencia(
    resumo_csv: Path,
    saida: Path,
) -> None:
    """Salva o resumo do benchmark como referência de regressão."""
    import csv

    resumo_atual = []
    with open(resumo_csv, newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            resumo_atual.append(linha)
    salvar_referencia(resumo_atual, saida)
    console.print(f"[green]Referência salva em {saida}[/green]")


# ---------------- rag cache/rerank (utilitários) ----------------
@rag_app.command("cache-limpar")
def rag_cache_limpar(diretorio: Path = typer.Option(Path("data/cache"), help="Diretório do cache")):
    """Remove arquivos de cache de respostas e embeddings."""
    import shutil

    for d in (diretorio, diretorio / "embeddings"):
        if d.exists():
            shutil.rmtree(d)
    console.print(f"[green]cache limpo: {diretorio}[/green]")


@rag_app.command("rerank-test")
def rag_rerank_test(
    consulta: str,
    top_n: int = typer.Option(5, help="Quantidade de resultados após rerank"),
) -> None:
    """Testa o reranker cross-encoder (precisa de sentence-transformers)."""
    from .ollama_client import OllamaClient
    from .rag.index import to_vec
    from .rag.retrieve import hybrid_search

    client = OllamaClient()
    with connect() as conn:
        hits = hybrid_search(conn, client, consulta, k=top_n * 3)
    ordenados = rerank_cross_encoder(consulta, hits, top_n=top_n)
    for i, h in enumerate(ordenados, 1):
        console.print(f"[{i}] score={h.score:.4f} via={h.via} — {h.title or h.doc_type}")


# ---------------- dashboard ----------------
@dashboard_app.command("up")
def dashboard_up(
    porta: int = typer.Option(8501, help="Porta do Streamlit"),
) -> None:
    """Sobe o dashboard Streamlit (Fase 7)."""
    import subprocess
    import sys

    app_path = str(Path(__file__).resolve().parent / "dashboard" / "app.py")
    console.print(f"[green]Iniciando dashboard em http://localhost:{porta}[/green]")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path, "--server.port", str(porta)])


if __name__ == "__main__":
    app()
