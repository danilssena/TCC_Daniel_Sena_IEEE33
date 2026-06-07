# -*- coding: utf-8 -*-
r"""
02_plot_case_base_harmonic.py


"""

from __future__ import annotations

from pathlib import Path
import traceback

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


PROJETO_DIR = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
FASE2_DIR = PROJETO_DIR / "metodologia" / "02_caso_base_harmonico"
INPUT_CSV = FASE2_DIR / "02_processados" / "THDv_barras_caso_base.csv"
OUTPUT_DIR = FASE2_DIR / "03_figuras"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ARQ_HTML = OUTPUT_DIR / "figura_01_thdv_caso_base_harmonico.html"
ARQ_PNG = OUTPUT_DIR / "figura_01_thdv_caso_base_harmonico.png"

COR_BARRAS = "#123B7A"
COR_LIMITE = "#C00000"
COR_EIXO = "#1F3558"
COR_GRID = "rgba(180, 190, 205, 0.35)"
COR_FUNDO = "white"


def ler_dados(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    df = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    if df.empty:
        raise ValueError("O arquivo de THDv está vazio.")

    colunas_necessarias = {"barra", "THDv_max_pct"}
    faltando = colunas_necessarias - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {sorted(faltando)}")

    df["barra_num"] = pd.to_numeric(df["barra"], errors="coerce")
    df["THDv_max_pct"] = pd.to_numeric(df["THDv_max_pct"], errors="coerce")
    df = df.sort_values(["barra_num", "barra"]).reset_index(drop=True)
    return df


def construir_figura(df: pd.DataFrame) -> go.Figure:
    x_vals = df["barra_num"].tolist()
    y_vals = df["THDv_max_pct"].fillna(0.0).tolist()

    ymax = max(max(y_vals, default=0.0), 0.05)
    ymax = max(ymax * 1.25, 0.1)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=x_vals,
            y=y_vals,
            name="THDv por barra",
            marker=dict(
                color=COR_BARRAS,
                line=dict(color=COR_BARRAS, width=0.8),
            ),
            hovertemplate="Barra %{x}<br>THDv = %{y:.6f}%<extra></extra>",
        )
    )

    fig.add_hline(
        y=5.0,
        line=dict(color=COR_LIMITE, width=2, dash="dash"),
        annotation_text="Limite de referência = 5%",
        annotation_position="top right",
        annotation_font=dict(size=14, color=COR_LIMITE),
    )

    fig.update_layout(
        title=dict(
            text="Caso Base Harmônico - THDv por Barra",
            x=0.5,
            xanchor="center",
            font=dict(size=28, color=COR_EIXO),
        ),
        template="plotly_white",
        paper_bgcolor=COR_FUNDO,
        plot_bgcolor=COR_FUNDO,
        font=dict(size=16, color=COR_EIXO),
        width=1600,
        height=900,
        bargap=0.18,
        margin=dict(l=80, r=40, t=90, b=80),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.03,
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.8)",
        ),
    )

    fig.update_xaxes(
        title_text="Barra",
        tickmode="array",
        tickvals=x_vals,
        ticktext=[str(int(v)) if pd.notna(v) else "" for v in x_vals],
        showline=True,
        linewidth=1.2,
        linecolor=COR_EIXO,
        showgrid=False,
        ticks="outside",
        tickfont=dict(size=14),
        title_font=dict(size=20),
    )

    fig.update_yaxes(
        title_text="THDv máximo (%)",
        range=[0, ymax],
        showline=True,
        linewidth=1.2,
        linecolor=COR_EIXO,
        showgrid=True,
        gridcolor=COR_GRID,
        griddash="dot",
        zeroline=True,
        zerolinecolor=COR_GRID,
        ticks="outside",
        tickfont=dict(size=14),
        title_font=dict(size=20),
    )

    return fig


def main() -> None:
    print("=" * 90)
    print("FASE 2 - GRÁFICO DO CASO BASE HARMÔNICO")
    print("=" * 90)
    print(f"Entrada : {INPUT_CSV}")
    print(f"Saída   : {OUTPUT_DIR}")

    df = ler_dados(INPUT_CSV)

    if df["THDv_max_pct"].fillna(0).abs().sum() == 0:
        print("Observação: todos os valores de THDv são nulos, como esperado para o caso base limpo.")

    fig = construir_figura(df)

    fig.write_html(str(ARQ_HTML))
    print(f"HTML gerado: {ARQ_HTML}")

    try:
        pio.write_image(fig, str(ARQ_PNG), width=1600, height=900, scale=2)
        print(f"PNG gerado : {ARQ_PNG}")
    except Exception as e:
        print("Aviso: não foi possível gerar o PNG automaticamente.")
        print("Motivo:", e)
        print("O HTML foi gerado normalmente.")

    print("\nConcluído com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Erro ao gerar o gráfico da Fase 2.")
        traceback.print_exc()
        raise
