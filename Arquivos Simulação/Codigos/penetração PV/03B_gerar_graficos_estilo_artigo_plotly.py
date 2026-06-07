# -*- coding: utf-8 -*-
r"""
03B_gerar_graficos_estilo_artigo_plotly.py

Gera gráficos em estilo mais próximo ao artigo-base, agora usando as métricas
detalhadas por fase e por ordem harmônica extraídas dos monitores.

IMPORTANTE
Como o sistema IEEE 33 adotado no TCC está equilibrado, as fases A, B e C
apresentam valores coincidentes na maior parte das grandezas. Portanto,
algumas figuras "por fase" ficarão com barras iguais/repetidas. Isso não é
erro do código: é uma consequência direta da modelagem trifásica equilibrada.

ENTRADAS
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\02b_metricas_detalhadas_artigo

SAÍDAS
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\03_graficos_artigo
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
INP = ROOT / "metodologia" / "03_penetracao_pv" / "02b_metricas_detalhadas_artigo"
OUT = ROOT / "metodologia" / "03_penetracao_pv" / "03_graficos_artigo"

PENS = ["PEN_100", "PEN_120", "PEN_150"]
BARRAS = [130, 140, 150, 160, 170, 180]
BARRA_CRITICA = 180

COR_A = "#0B3C8C"   # azul marinho
COR_B = "#C62828"   # vermelho
COR_C = "#6EC6FF"   # azul claro
COR_P100 = "#0B3C8C"
COR_P120 = "#C62828"
COR_P150 = "#6EC6FF"
COR_LIM = "#7A7A7A"

def ler(nome: str) -> pd.DataFrame:
    path = INP / nome
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")

def salvar(fig: go.Figure, nome: str, w=1400, h=800):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT / f"{nome}.html"), include_plotlyjs="cdn")
    try:
        fig.write_image(str(OUT / f"{nome}.png"), width=w, height=h, scale=2)
        fig.write_image(str(OUT / f"{nome}.svg"), width=w, height=h, scale=2)
        print(f"OK  -> {nome}")
    except Exception as e:
        print(f"AVISO -> {nome}: HTML gerado; PNG/SVG não exportados. Motivo: {e}")

def layout_padrao(titulo: str, x: str, y: str):
    return dict(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        template="plotly_white",
        width=1400,
        height=800,
        xaxis_title=x,
        yaxis_title=y,
        font=dict(size=15),
        margin=dict(l=70, r=30, t=100, b=70),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.12, yanchor="bottom"),
    )

def ordem_pen(s):
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 0

def fig16_tensao_nominal_pcc():
    df = ler("01_tensao_nominal_pcc_por_fase.csv")
    # usa PEN_150 por ser o cenário mais severo, mais próximo da lógica do artigo
    sub = df[df["penetracao"] == "PEN_150"].copy()
    sub = sub.sort_values("barra")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["Vfund_faseA_pu_rel_BUS10"], name="Fase A", marker_color=COR_A))
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["Vfund_faseB_pu_rel_BUS10"], name="Fase B", marker_color=COR_B))
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["Vfund_faseC_pu_rel_BUS10"], name="Fase C", marker_color=COR_C))
    fig.update_layout(**layout_padrao(
        "Figura 16. Tensão nominal nos pontos de conexão (PEN_150)",
        "Barras com inserção fotovoltaica",
        "Tensão (p.u., relativa à barra 10)"
    ), barmode="group")
    salvar(fig, "Figura_16_Tensao_nominal_pontos_conexao_PEN150")

def fig15_thdv_total_por_fase():
    df = ler("02_thdv_total_por_fase_barras_pv.csv")
    sub = df[df["penetracao"] == "PEN_150"].copy().sort_values("barra")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["THDv_faseA_pct"], name="Fase A", marker_color=COR_A))
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["THDv_faseB_pct"], name="Fase B", marker_color=COR_B))
    fig.add_trace(go.Bar(x=sub["barra"], y=sub["THDv_faseC_pct"], name="Fase C", marker_color=COR_C))
    fig.add_hline(y=5.0, line_dash="dash", line_color=COR_LIM, annotation_text="Limite 5%")
    fig.update_layout(**layout_padrao(
        "Figura 15. THDv total por fase nos pontos de conexão (PEN_150)",
        "Barras com inserção fotovoltaica",
        "THDv (%)"
    ), barmode="group")
    salvar(fig, "Figura_15_THDv_total_por_fase_PEN150")

def fig18_thdi_total_por_fase():
    df = ler("03_thdi_total_por_fase_pvs.csv")
    sub = df[df["penetracao"] == "PEN_150"].copy().sort_values("pv_barra")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=sub["pv_barra"], y=sub["THDi_faseA_pct"], name="Fase A", marker_color=COR_A))
    fig.add_trace(go.Bar(x=sub["pv_barra"], y=sub["THDi_faseB_pct"], name="Fase B", marker_color=COR_B))
    fig.add_trace(go.Bar(x=sub["pv_barra"], y=sub["THDi_faseC_pct"], name="Fase C", marker_color=COR_C))
    fig.update_layout(**layout_padrao(
        "Figura 18. THDi total por fase nos sistemas fotovoltaicos (PEN_150)",
        "Barras com inserção fotovoltaica",
        "THDi (%)"
    ), barmode="group")
    salvar(fig, "Figura_18_THDi_total_por_fase_PEN150")

def fig14_ihdv_estilo_artigo():
    df = ler("04_ihdv_espectro_por_fase_barras_pv.csv")
    sub = df[df["penetracao"] == "PEN_150"].copy()
    sub = sub[sub["ordem"].isin([3,5,7,9,11,13])]
    sub = sub.sort_values(["ordem", "barra"])

    labels = []
    valsA = []; valsB = []; valsC = []
    for ordem in [3,5,7,9,11,13]:
        d = sub[sub["ordem"] == ordem].sort_values("barra")
        # pega média entre as barras PV para manter gráfico legível
        valsA.append(d["IHDv_faseA_pct"].mean())
        valsB.append(d["IHDv_faseB_pct"].mean())
        valsC.append(d["IHDv_faseC_pct"].mean())
        labels.append(str(ordem))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=valsA, name="Fase A", marker_color=COR_A))
    fig.add_trace(go.Bar(x=labels, y=valsB, name="Fase B", marker_color=COR_B))
    fig.add_trace(go.Bar(x=labels, y=valsC, name="Fase C", marker_color=COR_C))
    fig.update_layout(**layout_padrao(
        "Figura 14. Espectro IHDv médio por fase nas barras com PV (PEN_150)",
        "Ordem harmônica",
        "IHDv (%)"
    ), barmode="group")
    salvar(fig, "Figura_14_Espectro_IHDv_medio_PEN150")

def fig17_ihdi_estilo_artigo():
    df = ler("05_ihdi_espectro_por_fase_pvs.csv")
    sub = df[df["penetracao"] == "PEN_150"].copy()
    sub = sub[sub["ordem"].isin([3,5,7,9,11,13])]
    sub = sub.sort_values(["ordem", "pv_barra"])

    labels = []
    valsA = []; valsB = []; valsC = []
    for ordem in [3,5,7,9,11,13]:
        d = sub[sub["ordem"] == ordem].sort_values("pv_barra")
        valsA.append(d["IHDi_faseA_pct"].mean())
        valsB.append(d["IHDi_faseB_pct"].mean())
        valsC.append(d["IHDi_faseC_pct"].mean())
        labels.append(str(ordem))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=valsA, name="Fase A", marker_color=COR_A))
    fig.add_trace(go.Bar(x=labels, y=valsB, name="Fase B", marker_color=COR_B))
    fig.add_trace(go.Bar(x=labels, y=valsC, name="Fase C", marker_color=COR_C))
    fig.update_layout(**layout_padrao(
        "Figura 17. Espectro IHDi médio por fase nos sistemas fotovoltaicos (PEN_150)",
        "Ordem harmônica",
        "IHDi (%)"
    ), barmode="group")
    salvar(fig, "Figura_17_Espectro_IHDi_medio_PEN150")

def fig_extra_comparativo_pens_barra_critica():
    df = ler("06_espectro_completo_barra_critica.csv")
    sub = df[df["ordem"].isin([3,5,7,9,11,13,15])].copy()
    sub = sub.sort_values(["penetracao", "ordem"], key=lambda s: s.map(ordem_pen) if s.name=="penetracao" else s)

    fig = make_subplots(rows=1, cols=2, subplot_titles=["IHDv na barra crítica 180", "IHDi no PV da barra crítica 180"])
    for pen, cor in zip(PENS, [COR_P100, COR_P120, COR_P150]):
        d = sub[sub["penetracao"] == pen].sort_values("ordem")
        fig.add_trace(go.Scatter(
            x=d["ordem"], y=d["IHDv_faseA_pct"], mode="lines+markers", name=f"{pen} - IHDv",
            line=dict(color=cor, width=3), marker=dict(size=7), showlegend=True
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=d["ordem"], y=d["IHDi_faseA_pct"], mode="lines+markers", name=f"{pen} - IHDi",
            line=dict(color=cor, width=3), marker=dict(size=7), showlegend=False
        ), row=1, col=2)

    fig.update_layout(
        title=dict(text="Figura extra. Comparação espectral na barra crítica", x=0.5, xanchor="center"),
        template="plotly_white",
        width=1500, height=700,
        font=dict(size=15),
        margin=dict(l=70, r=20, t=90, b=60),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.12, yanchor="bottom")
    )
    fig.update_xaxes(title_text="Ordem harmônica", row=1, col=1)
    fig.update_xaxes(title_text="Ordem harmônica", row=1, col=2)
    fig.update_yaxes(title_text="IHDv (%)", row=1, col=1)
    fig.update_yaxes(title_text="IHDi (%)", row=1, col=2)
    salvar(fig, "Figura_extra_Comparacao_espectral_barra_critica", w=1500, h=700)

def main():
    print("="*100)
    print("03B_gerar_graficos_estilo_artigo_plotly.py")
    print("="*100)
    print(f"Entrada: {INP}")
    print(f"Saída  : {OUT}")

    fig16_tensao_nominal_pcc()
    fig15_thdv_total_por_fase()
    fig18_thdi_total_por_fase()
    fig14_ihdv_estilo_artigo()
    fig17_ihdi_estilo_artigo()
    fig_extra_comparativo_pens_barra_critica()

    print("\nConcluído com sucesso.")

if __name__ == "__main__":
    main()
