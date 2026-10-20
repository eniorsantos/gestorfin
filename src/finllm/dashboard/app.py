"""Dashboard Streamlit — finllm Fase 7.

Execução: streamlit run src/finllm/dashboard/app.py
"""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from .db import (
    estatisticas_gerais,
    listar_empresas,
    listar_setores,
    listar_consultas,
    listar_alertas,
    criar_alerta,
    indicadores_ticker,
)

st.set_page_config(page_title="finllm — Análise Financeira", page_icon="📈", layout="wide")

st.title("📈 finllm — Análise Financeira com LLM Local")
st.caption("Dashboard Fase 7 — RAG sobre dados da CVM, indicadores, técnicos, agentes, alertas e screener.")

# ----------------------------- Sidebar -----------------------------
st.sidebar.header("Navegação")
pagina = st.sidebar.radio(
    "Página",
    ["Visão geral", "Screener B3", "Indicadores", "Técnico", "Agentes", "Alertas", "Auditoria (consultas)"],
    index=0,
)

st.sidebar.divider()
stats = estatisticas_gerais()
st.sidebar.metric("Empresas", stats.get("empresas", 0))
st.sidebar.metric("Demonstrações", stats.get("demonstacoes", 0))
st.sidebar.metric("Chunks (RAG)", stats.get("chunks", 0))
st.sidebar.metric("Consultas auditadas", stats.get("consultas", 0))
st.sidebar.metric("Alertas", stats.get("alertas", 0))

# ----------------------------- Página: Visão geral -----------------------------
if pagina == "Visão geral":
    st.subheader("Visão geral do ambiente")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Empresas cadastradas", stats.get("empresas", 0))
    col2.metric("Linhas de demonstrações", stats.get("demonstacoes", 0))
    col3.metric("Chunks indexados (RAG)", stats.get("chunks", 0))
    col4.metric("Consultas auditadas", stats.get("consultas", 0))
    col5.metric("Alertas ativos", stats.get("alertas", 0))

    st.divider()
    st.markdown("### Últimas consultas auditadas")
    consultas = listar_consultas(limit=10)
    if consultas:
        for c in consultas:
            with st.expander(f"#{c['id']} — {c['pergunta'][:80]}...", expanded=False):
                st.write("**Modelo:**", c["modelo"])
                st.write("**Criado em:**", c["criado_em"])
                resp = c.get("resposta")
                if resp:
                    try:
                        resp_obj = json.loads(resp) if isinstance(resp, str) else resp
                        st.write("**Resposta:**", resp_obj.get("resposta", "") if isinstance(resp_obj, dict) else resp_obj)
                        st.write("**Valor:**", resp_obj.get("valor") if isinstance(resp_obj, dict) else "")
                        st.write("**Não encontrado:**", resp_obj.get("nao_encontrado") if isinstance(resp_obj, dict) else "")
                    except Exception:
                        st.write("**Resposta:**", resp)
                val = c.get("validacao")
                if val:
                    try:
                        val_obj = json.loads(val) if isinstance(val, str) else val
                        st.write("**Validação numérica:**", "OK" if val_obj.get("ok") else f"⚠ {val_obj.get('unsupported')}")
                    except Exception:
                        st.write("**Validação:**", val)
    else:
        st.info("Nenhuma consulta auditada ainda. Rode `finllm rag ask` para gerar consultas.")

# ----------------------------- Página: Screener B3 -----------------------------
elif pagina == "Screener B3":
    st.subheader("Screener da B3")
    st.caption("Filtre empresas por setor e visualize indicadores fundamentalistas.")

    setores = listar_setores()
    setor_sel = st.selectbox("Setor", ["Todos"] + setores, index=0)

    empresas = listar_empresas(limit=200, setor=None if setor_sel == "Todos" else setor_sel)
    if not empresas:
        st.warning("Nenhuma empresa encontrada. Carregue o cadastro da CVM (`finllm cvm load`).")
    else:
        st.write(f"{len(empresas)} empresa(s)")
        dados_tabela = []
        for emp in empresas:
            ind = indicadores_ticker(emp["denom"])
            dados_tabela.append({
                "CD_CVM": emp["cd_cvm"],
                "Empresa": emp["denom"],
                "Setor": emp["setor"] or "—",
                "Situação": emp["situacao"] or "—",
                "P/L": ind.get("pl"),
                "ROE": ind.get("roe"),
                "ROIC": ind.get("roic"),
                "Dív.Líq./EBITDA": ind.get("divida_liquida_ebitda"),
                "F-Score": ind.get("f_score"),
            })
        st.dataframe(dados_tabela, use_container_width=True, hide_index=True)

# ----------------------------- Página: Indicadores -----------------------------
elif pagina == "Indicadores":
    st.subheader("Indicadores Fundamentalistas")
    st.caption("Cálculos determinísticos a partir dos dados estruturados da CVM (Fase 3).")

    ticker = st.text_input("Ticker / nome da empresa", value="PETROBRAS")
    if st.button("Calcular indicadores"):
        ind = indicadores_ticker(ticker)
        if not ind or "mensagem" in ind:
            st.warning(ind.get("mensagem", "Empresa não encontrada ou sem dados."))
        else:
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("P/L", f"{ind['pl']:.2f}" if ind.get("pl") is not None else "n/d")
            col2.metric("ROE", f"{ind['roe']:.2%}" if ind.get("roe") is not None else "n/d")
            col3.metric("ROIC", f"{ind['roic']:.2%}" if ind.get("roic") is not None else "n/d")
            col4.metric("Dív.Líq./EBITDA", f"{ind['divida_liquida_ebitda']:.2f}" if ind.get("divida_liquida_ebitda") is not None else "n/d")
            col5.metric("F-Score", str(ind["f_score"]) if ind.get("f_score") is not None else "n/d")
            st.write("**Empresa:**", ind.get("empresa"))
            st.write("**CD_CVM:**", ind.get("cd_cvm"))
            st.write("**Data referência:**", ind.get("data_referencia"))

# ----------------------------- Página: Técnico -----------------------------
elif pagina == "Técnico":
    st.subheader("Indicadores Técnicos")
    st.caption("OHLCV, SMA/EMA/RSI/MACD/Bollinger, suportes e resistências (Fase 4).")

    ticker = st.text_input("Ticker", value="PETR4")
    periodo = st.selectbox("Período", ["1m", "6m", "1a", "5a"], index=1)
    if st.button("Calcular técnicos"):
        try:
            from .db import indicadores_ticker as _ind  # placeholder não usado
        except Exception:
            pass
        try:
            from ..rag.tools import get_indicadores_tecnicos
            tec = get_indicadores_tecnicos(ticker, periodo)
            if "mensagem" in tec:
                st.warning(tec["mensagem"])
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric("Sinal", tec.get("sinal", "neutro"))
                col2.metric("RSI 14", f"{tec['rsi_14']:.2f}" if tec.get("rsi_14") is not None else "n/d")
                col3.metric("MACD hist", f"{tec['macd_hist']:.4f}" if tec.get("macd_hist") is not None else "n/d")
                st.write("**SMA 20:**", tec.get("sma_20"))
                st.write("**SMA 50:**", tec.get("sma_50"))
                st.write("**Suporte:**", tec.get("suporte"))
                st.write("**Resistência:**", tec.get("resistencia"))
        except Exception as e:
            st.error(f"Erro ao calcular indicadores técnicos: {e}")

# ----------------------------- Página: Agentes -----------------------------
elif pagina == "Agentes":
    st.subheader("Agentes de Análise")
    st.caption("Fundamentalista, técnico, risco (advogado do diabo) e sintetizador com score composto (Fase 5).")

    ticker = st.text_input("Ticker / empresa", value="WEGE3", key="agentes_ticker")
    col_a, col_b = st.columns(2)
    use_fund = col_a.checkbox("Fundamentalista", value=True)
    use_tec = col_b.checkbox("Técnico", value=True)

    if st.button("Executar agentes"):
        try:
            from ..agentes import executar_agentes
            indicadores = {}
            tecnicos = {}
            contexto = {}
            if use_fund:
                ind = indicadores_ticker(ticker)
                if ind and "mensagem" not in ind:
                    indicadores = {
                        "pl": ind.get("pl"),
                        "roe": ind.get("roe"),
                        "roic": ind.get("roic"),
                        "divida_liquida_ebitda": ind.get("divida_liquida_ebitda"),
                        "f_score": ind.get("f_score"),
                    }
                    contexto["empresa"] = ind.get("empresa")
                    contexto["data_referencia"] = ind.get("data_referencia")
            if use_tec:
                try:
                    from ..rag.tools import get_indicadores_tecnicos
                    tecnicos = get_indicadores_tecnicos(ticker, "6m")
                except Exception:
                    tecnicos = {}
            resultado = executar_agentes(ticker, indicadores=indicadores, tecnicos=tecnicos, contexto=contexto)

            st.metric("Sinal final", resultado.sinal_final)
            st.metric("Confiança", f"{resultado.confianca_final:.2%}")
            st.metric("Score composto", f"{resultado.score_composto:.3f}")
            st.write("**Síntese:**", resultado.justificativa_sintese)
            if resultado.riscos_principais:
                st.write("**Riscos principais:**")
                for r in resultado.riscos_principais:
                    st.write(f"- {r}")
            st.write("**Pareceres por agente:**")
            for p in resultado.pareceres:
                with st.expander(f"{p.nome} — {p.sinal} (conf {p.confianca:.2f})"):
                    st.write(p.justificativa)
                    if p.evidencias:
                        st.write("Evidências:", "; ".join(p.evidencias))
                    if p.riscos:
                        st.write("Riscos:", "; ".join(p.riscos))
        except Exception as e:
            st.error(f"Erro ao executar agentes: {e}")

# ----------------------------- Página: Alertas -----------------------------
elif pagina == "Alertas":
    st.subheader("Alertas")
    st.caption("Crie alertas de preço/indicador para tickers (tabela `alertas`).")

    with st.form("novo_alerta"):
        col1, col2, col3, col4 = st.columns(4)
        ticker_alerta = col1.text_input("Ticker", value="PETR4")
        tipo_alerta = col2.selectbox("Tipo", ["preco", "indicador", "noticia"], index=0)
        condicao_alerta = col3.text_input("Condição", value=">= 30.00")
        valor_alerta = col4.number_input("Valor referência", value=30.0, step=0.1)
        submit = st.form_submit_button("Criar alerta")
        if submit:
            try:
                aid = criar_alerta(ticker_alerta, tipo_alerta, condicao_alerta, valor_alerta)
                if aid > 0:
                    st.success(f"Alerta #{aid} criado para {ticker_alerta}.")
                else:
                    st.warning("Banco não disponível; alerta não persistido.")
            except Exception as e:
                st.error(f"Erro ao criar alerta: {e}")

    st.divider()
    st.write("### Alertas cadastrados")
    alertas = listar_alertas(ativo=True)
    if alertas:
        for a in alertas:
            status = "✅ Ativo" if a["ativo"] else "❌ Inativo"
            disparado = f" (disparado em {a['disparado_em']})" if a["disparado_em"] else ""
            st.write(f"#{a['id']} — {a['ticker']} ({a['tipo']}) {a['condicao']} {a['valor_referencia']} — {status}{disparado}")
    else:
        st.info("Nenhum alerta cadastrado.")

# ----------------------------- Página: Auditoria -----------------------------
elif pagina == "Auditoria (consultas)":
    st.subheader("Auditoria de Consultas")
    st.caption("Toda chamada de `finllm rag ask` é registrada aqui para rastreabilidade.")

    consultas = listar_consultas(limit=100)
    if consultas:
        for c in consultas:
            with st.expander(f"#{c['id']} — {c['pergunta'][:100]}", expanded=False):
                st.write("**Modelo:**", c["modelo"])
                st.write("**Criado em:**", c["criado_em"])
                resp_raw = c.get("resposta")
                if resp_raw:
                    try:
                        resp = json.loads(resp_raw) if isinstance(resp_raw, str) else resp_raw
                        st.write("**Resposta:**", resp.get("resposta", "") if isinstance(resp, dict) else resp)
                        st.write("**Valor:**", resp.get("valor") if isinstance(resp, dict) else "")
                        st.write("**Não encontrado:**", resp.get("nao_encontrado") if isinstance(resp, dict) else "")
                    except Exception:
                        st.write("**Resposta:**", resp_raw)
                val_raw = c.get("validacao")
                if val_raw:
                    try:
                        val = json.loads(val_raw) if isinstance(val_raw, str) else val_raw
                        st.write("**Validação:**", "✅ OK" if val.get("ok") else f"⚠ {val.get('unsupported')}")
                    except Exception:
                        st.write("**Validação:**", val_raw)
    else:
        st.info("Nenhuma consulta auditada ainda.")

st.divider()
st.caption("finllm — Apoio à análise financeira. Não é recomendação de investimento.")
