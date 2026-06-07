# -*- coding: utf-8 -*-
r"""
03_gerar_graficos_penetracao_6_barras_plotly_v3.py
GRÁFICOS GERADOS
G01 - THDv máximo global por penetração
G02 - Perfil de THDv por barra (subplots PEN_100 / PEN_120 / PEN_150)
G03 - THDi nos 6 PVs (comparativo por penetração)
G04 - Espectro IHDv na barra crítica 180 (comparativo)
G05 - Espectro IHDi no PV crítico 180 (comparativo)
G06 - Heatmap THDv (barra x penetração)
G07 - Heatmap IHDv PEN_150 (ordem x barra)
G08 - Top 10 barras mais afetadas por penetração

ENTRADAS
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\02_processados_thd

SAÍDAS
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\03_graficos
"""

from __future__ import annotations

from pathlib import Path
import math
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
ROOT = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
PROC = ROOT / "metodologia" / "03_penetracao_pv" / "02_processados_thd"
OUT = ROOT / "metodologia" / "03_penetracao_pv" / "03_graficos"

ARQ_THDV = PROC / "THDv_barras_consolidado.csv"
ARQ_THDI = PROC / "THDi_pvs_consolidado.csv"
ARQ_IHDV = PROC / "IHDv_barras_ordens_3_5_7.csv"
ARQ_IHDI = PROC / "IHDi_pvs_ordens_3_5_7.csv"
ARQ_TOP10 = PROC / "TOP10_barras_mais_afetadas.csv"
ARQ_RES_THDV = PROC / "resumo_THDv_por_penetracao.csv"
ARQ_RES_THDI = PROC / "resumo_THDi_por_penetracao.csv"

PENS = ["PEN_100", "PEN_120", "PEN_150"]
BARRAS_PV = [130, 140, 150, 160, 170, 180]
BARRA_CRITICA = 180
ORDENS_FOCO = [3, 5, 7]
LIMITE_THDV = 5.0

COR_P100 = "#0B3C8C"   # azul marinho
COR_P120 = "#C62828"   # vermelho
COR_P150 = "#6EC6FF"   # azul claro
COR_LIM = "#7A7A7A"

MAP_CORES = {"PEN_100": COR_P100, "PEN_120": COR_P120, "PEN_150": COR_P150}


# ==============================================================================
# HELPERS
# ==============================================================================
def ler_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")


def cor_pen(pen: str) -> str:
    return MAP_CORES.get(str(pen), "black")


def num_pen(pen: str) -> int:
    m = re.search(r"(\d+)", str(pen))
    return int(m.group(1)) if m else 0


def ordenar_pen(df: pd.DataFrame, col: str = "penetracao") -> pd.DataFrame:
    df = df.copy()
    df["_ord_pen"] = df[col].map(num_pen)
    return df.sort_values(["_ord_pen"]).drop(columns="_ord_pen")


def ordenar_barra(df: pd.DataFrame, col: str = "barra") -> pd.DataFrame:
    df = df.copy()
    df["_ord_barra"] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["_ord_barra", col]).drop(columns="_ord_barra")


def salvar_fig(fig: go.Figure, nome_base: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    html = OUT / f"{nome_base}.html"
    png = OUT / f"{nome_base}.png"
    svg = OUT / f"{nome_base}.svg"

    fig.write_html(str(html), include_plotlyjs="cdn")
    try:
        fig.write_image(str(png), width=1400, height=820, scale=2)
        fig.write_image(str(svg), width=1400, height=820, scale=2)
        print(f"OK  -> {nome_base}.html / .png / .svg")
    except Exception as e:
        print(f"AVISO -> {nome_base}: HTML gerado; PNG/SVG não exportados. Motivo: {e}")


def layout_padrao(titulo: str, x: str, y: str) -> dict:
    return dict(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        template="plotly_white",
        width=1400,
        height=820,
        xaxis_title=x,
        yaxis_title=y,
        font=dict(size=15),
        margin=dict(l=70, r=30, t=100, b=70),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.10,
            yanchor="bottom"
        )
    )


# ==============================================================================
# GRÁFICOS
# ==============================================================================
def g01_thdv_global():
    df = ordenar_pen(ler_csv(ARQ_RES_THDV))
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["penetracao"],
        y=df["THDv_max_global_pct"],
        mode="lines+markers+text",
        text=[f"{v:.2f}%" for v in df["THDv_max_global_pct"]],
        textposition="top center",
        name="THDv máximo global",
        line=dict(color=COR_P100, width=3),
        marker=dict(size=10)
    ))
    fig.add_hline(y=LIMITE_THDV, line_dash="dash", line_color=COR_LIM, annotation_text="Limite 8%")

    fig.update_layout(**layout_padrao(
        "G01. THDv máximo global por nível de penetração",
        "Nível de penetração",
        "THDv máximo (%)"
    ))
    salvar_fig(fig, "G01_THDv_maximo_global")


def g02_perfil_thdv_por_barra():
    df = ordenar_barra(ordenar_pen(ler_csv(ARQ_THDV)))
    fig = make_subplots(rows=1, cols=3, subplot_titles=PENS, shared_yaxes=True)

    for i, pen in enumerate(PENS, start=1):
        s = df[df["penetracao"] == pen].copy()
        fig.add_trace(go.Scatter(
            x=s["barra"],
            y=s["THDv_max_pct"],
            mode="lines+markers",
            name=pen,
            line=dict(color=cor_pen(pen), width=3),
            marker=dict(size=6),
            showlegend=False,
            hovertemplate="Barra %{x}<br>THDv=%{y:.3f}%<extra></extra>"
        ), row=1, col=i)

        for b in BARRAS_PV:
            fig.add_vline(x=b, line_width=1, line_dash="dot", line_color="lightgray", row=1, col=i)

    fig.add_hline(y=LIMITE_THDV, line_dash="dash", line_color=COR_LIM, row=1, col=1)
    fig.add_hline(y=LIMITE_THDV, line_dash="dash", line_color=COR_LIM, row=1, col=2)
    fig.add_hline(y=LIMITE_THDV, line_dash="dash", line_color=COR_LIM, row=1, col=3)

    fig.update_layout(
        title=dict(text="G02. Perfil de THDv por barra", x=0.5, xanchor="center"),
        template="plotly_white",
        width=1500,
        height=620,
        font=dict(size=14),
        margin=dict(l=70, r=20, t=90, b=60)
    )
    fig.update_xaxes(title_text="Barra")
    fig.update_yaxes(title_text="THDv máximo (%)")
    salvar_fig(fig, "G02_Perfil_THDv_por_barra")


def g03_thdi_nos_pvs():
    df = ordenar_pen(ler_csv(ARQ_THDI))
    df["pv_bus"] = pd.to_numeric(df["pv_bus"], errors="coerce")
    fig = go.Figure()

    for pen in PENS:
        s = df[df["penetracao"] == pen].sort_values("pv_bus")
        fig.add_trace(go.Scatter(
            x=s["pv_bus"],
            y=s["THDi_max_pct"],
            mode="lines+markers",
            name=pen,
            line=dict(color=cor_pen(pen), width=3),
            marker=dict(size=8)
        ))

    fig.update_layout(**layout_padrao(
        "G03. THDi máximo nos pontos de inserção fotovoltaica",
        "Barra com PV",
        "THDi máximo (%)"
    ))
    salvar_fig(fig, "G03_THDi_nos_PVs")


def g04_espectro_ihdv_barra_critica():
    df = ler_csv(ARQ_IHDV)
    s = df[df["barra"] == BARRA_CRITICA].copy()
    s = ordenar_pen(s)
    fig = go.Figure()

    for pen in PENS:
        d = s[s["penetracao"] == pen].sort_values("ordem")
        fig.add_trace(go.Bar(
            x=[str(int(v)) for v in d["ordem"]],
            y=d["IHDv_max_pct"],
            name=pen,
            marker_color=cor_pen(pen)
        ))

    fig.update_layout(
        **layout_padrao(
            f"G04. Espectro IHDv na barra crítica {BARRA_CRITICA}",
            "Ordem harmônica",
            "IHDv máximo (%)"
        ),
        barmode="group"
    )
    salvar_fig(fig, "G04_Espectro_IHDv_barra_critica")


def g05_espectro_ihdi_pv_critico():
    df = ler_csv(ARQ_IHDI)
    s = df[df["pv_bus"] == BARRA_CRITICA].copy()
    s = ordenar_pen(s)
    fig = go.Figure()

    for pen in PENS:
        d = s[s["penetracao"] == pen].sort_values("ordem")
        fig.add_trace(go.Bar(
            x=[str(int(v)) for v in d["ordem"]],
            y=d["IHDi_max_pct"],
            name=pen,
            marker_color=cor_pen(pen)
        ))

    fig.update_layout(
        **layout_padrao(
            f"G05. Espectro IHDi no PV da barra crítica {BARRA_CRITICA}",
            "Ordem harmônica",
            "IHDi máximo (%)"
        ),
        barmode="group"
    )
    salvar_fig(fig, "G05_Espectro_IHDi_PV_critico")


def g06_heatmap_thdv():
    df = ordenar_barra(ordenar_pen(ler_csv(ARQ_THDV)))
    piv = df.pivot_table(index="barra", columns="penetracao", values="THDv_max_pct")
    piv = piv[PENS]

    fig = go.Figure(data=go.Heatmap(
        z=piv.values,
        x=piv.columns.tolist(),
        y=piv.index.tolist(),
        colorbar=dict(title="THDv (%)"),
        hovertemplate="Barra %{y}<br>%{x}<br>THDv=%{z:.3f}%<extra></extra>"
    ))
    fig.update_layout(**layout_padrao(
        "G06. Mapa térmico de THDv (barra × penetração)",
        "Nível de penetração",
        "Barra"
    ))
    salvar_fig(fig, "G06_Heatmap_THDv")


def g07_heatmap_ihdv_pen150():
    df = ler_csv(ARQ_IHDV)
    s = df[df["penetracao"] == "PEN_150"].copy()
    s["barra"] = pd.to_numeric(s["barra"], errors="coerce")
    s = s.sort_values(["ordem", "barra"])

    piv = s.pivot_table(index="ordem", columns="barra", values="IHDv_max_pct")
    fig = go.Figure(data=go.Heatmap(
        z=piv.values,
        x=[str(int(v)) for v in piv.columns.tolist()],
        y=[str(int(v)) for v in piv.index.tolist()],
        colorbar=dict(title="IHDv (%)"),
        hovertemplate="Ordem %{y}<br>Barra %{x}<br>IHDv=%{z:.3f}%<extra></extra>"
    ))
    fig.update_layout(**layout_padrao(
        "G07. Mapa térmico de IHDv em PEN_150 (ordem × barra)",
        "Barra",
        "Ordem harmônica"
    ))
    salvar_fig(fig, "G07_Heatmap_IHDv_PEN150")


def g08_top10_barras():
    df = ler_csv(ARQ_TOP10)
    fig = make_subplots(rows=3, cols=1, subplot_titles=PENS, shared_xaxes=False)

    for i, pen in enumerate(PENS, start=1):
        s = df[df["penetracao"] == pen].copy()
        s["barra"] = pd.to_numeric(s["barra"], errors="coerce")
        s = s.sort_values("THDv_max_pct", ascending=True)

        fig.add_trace(go.Bar(
            x=s["THDv_max_pct"],
            y=s["barra"].astype(int).astype(str),
            orientation="h",
            name=pen,
            marker_color=cor_pen(pen),
            showlegend=False,
            hovertemplate="Barra %{y}<br>THDv=%{x:.3f}%<extra></extra>"
        ), row=i, col=1)

    fig.update_layout(
        title=dict(text="G08. Top 10 barras mais afetadas por THDv", x=0.5, xanchor="center"),
        template="plotly_white",
        width=1200,
        height=1100,
        font=dict(size=14),
        margin=dict(l=70, r=20, t=90, b=60)
    )
    fig.update_xaxes(title_text="THDv máximo (%)")
    fig.update_yaxes(title_text="Barra")
    salvar_fig(fig, "G08_TOP10_barras_mais_afetadas")


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    print("=" * 100)
    print("03_gerar_graficos_penetracao_6_barras_plotly_v3.py")
    print("Conjunto refinado de gráficos finais")
    print("=" * 100)
    print(f"Entrada: {PROC}")
    print(f"Saída  : {OUT}")

    g01_thdv_global()
    g02_perfil_thdv_por_barra()
    g03_thdi_nos_pvs()
    g04_espectro_ihdv_barra_critica()
    g05_espectro_ihdi_pv_critico()
    g06_heatmap_thdv()
    g07_heatmap_ihdv_pen150()
    g08_top10_barras()

    print("\nConcluído com sucesso.")


if __name__ == "__main__":
    main()
