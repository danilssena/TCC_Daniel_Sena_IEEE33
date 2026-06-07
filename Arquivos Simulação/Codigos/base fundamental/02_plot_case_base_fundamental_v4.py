# -*- coding: utf-8 -*-
"""
FASE 1 - CASO BASE FUNDAMENTAL
Script 02 (revisado v4): gráficos finais em Plotly

Ajustes desta versão:
- títulos centralizados;
- Figura 1 com paleta curta solicitada pelo usuário:
  azul-marinho (maior fluxo), azul-claro (fluxo intermediário), vermelho (menor fluxo);
- Figura 2 simplificada para uma única fase representativa (Fase A),
  adequada para sistema equilibrado no caso base;
- Figura 3 mantida com o layout aprovado.
"""

from __future__ import annotations

from pathlib import Path
import traceback

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

PROJETO_DIR = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
BUSCOORDS_DSS = PROJETO_DIR / "BusCoords.dss"

METODOLOGIA_DIR = PROJETO_DIR / "metodologia"
FASE1_DIR = METODOLOGIA_DIR / "01_caso_base_fundamental"
PROCESSADOS_DIR = FASE1_DIR / "02_processados"
FIGURAS_DIR = FASE1_DIR / "03_figuras"

ARQ_CSV_FLUXO = PROCESSADOS_DIR / "fluxo_potencia_linhas.csv"
ARQ_CSV_TENSAO = PROCESSADOS_DIR / "perfil_tensao_barras.csv"
ARQ_CSV_PERDAS = PROCESSADOS_DIR / "perdas_por_linha.csv"

FIG_FLUXO_HTML = FIGURAS_DIR / "figura_01_fluxo_potencia_base.html"
FIG_TENSAO_HTML = FIGURAS_DIR / "figura_02_perfil_tensao_base.html"
FIG_PERDAS_HTML = FIGURAS_DIR / "figura_03_perdas_base.html"

FIG_FLUXO_PNG = FIGURAS_DIR / "figura_01_fluxo_potencia_base.png"
FIG_TENSAO_PNG = FIGURAS_DIR / "figura_02_perfil_tensao_base.png"
FIG_PERDAS_PNG = FIGURAS_DIR / "figura_03_perdas_base.png"

LIMITE_INFERIOR_PU = 0.95
LIMITE_SUPERIOR_PU = 1.05

pio.templates.default = "plotly_white"


def garantir_pasta() -> None:
    FIGURAS_DIR.mkdir(parents=True, exist_ok=True)



def normalizar_barra(nome: str) -> str:
    return str(nome).strip().replace('"', '').split('.')[0].upper()



def ler_csv_padrao(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=",")



def ler_buscoords(path: Path) -> dict[str, tuple[float, float]]:
    coords: dict[str, tuple[float, float]] = {}
    if not path.exists():
        return coords
    with open(path, "r", encoding="latin-1", errors="ignore") as f:
        for linha in f:
            s = linha.strip()
            if not s or s.startswith("!") or s.startswith("(") or s.startswith(")"):
                continue
            partes = [p.strip() for p in s.split(",")]
            if len(partes) < 3:
                continue
            try:
                barra = normalizar_barra(partes[0])
                x = float(partes[1])
                y = float(partes[2])
            except Exception:
                continue
            coords[barra] = (x, y)
    return coords



def salvar_figura(fig: go.Figure, html_path: Path, png_path: Path) -> None:
    fig.write_html(str(html_path), include_plotlyjs="cdn")
    try:
        fig.write_image(str(png_path), width=1700, height=950, scale=2)
    except Exception as e:
        print(f"Aviso: não foi possível exportar PNG {png_path.name}: {e}")



def preparar_fluxo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["Bus1", "Bus2"]:
        df[col] = df[col].astype(str).map(normalizar_barra)
    return df



def preparar_tensao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Bus"] = df["Bus"].astype(str).map(normalizar_barra)
    return df.sort_values(["Dist_km", "Bus"]).reset_index(drop=True)



def layout_padrao(fig: go.Figure, titulo: str) -> None:
    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center"),
        margin=dict(l=40, r=40, t=80, b=50),
        font=dict(size=18),
    )



def grafico_fluxo(df_linhas: pd.DataFrame, coords: dict[str, tuple[float, float]]) -> go.Figure:
    fig = go.Figure()
    if df_linhas.empty or not coords:
        layout_padrao(fig, "Fluxo de Potência do Alimentador - dados insuficientes")
        return fig

    pmin = float(df_linhas["P_kW"].min())
    pmax = float(df_linhas["P_kW"].max())
    q1 = float(df_linhas["P_kW"].quantile(0.33))
    q2 = float(df_linhas["P_kW"].quantile(0.66))

    def espessura(p: float) -> float:
        if pmax <= pmin:
            return 4.0
        return 2.2 + 7.0 * ((p - pmin) / (pmax - pmin))

    def cor_fluxo(p: float) -> str:
        # maior fluxo = azul-marinho; intermediário = azul-claro; menor = vermelho
        if p >= q2:
            return "#0B3C8C"   # azul-marinho
        elif p >= q1:
            return "#6EC6FF"   # azul-claro (céu)
        return "#D62828"       # vermelho

    for _, row in df_linhas.iterrows():
        b1 = str(row["Bus1"]).upper()
        b2 = str(row["Bus2"]).upper()
        if b1 not in coords or b2 not in coords:
            continue
        x1, y1 = coords[b1]
        x2, y2 = coords[b2]
        p_kw = float(row["P_kW"])
        fig.add_trace(
            go.Scatter(
                x=[x1, x2],
                y=[y1, y2],
                mode="lines",
                line=dict(width=espessura(p_kw), color=cor_fluxo(p_kw)),
                hovertemplate=(
                    f"Trecho: {row['Trecho']}<br>"
                    f"{b1} → {b2}<br>"
                    f"Fluxo ativo: {p_kw:.2f} kW<extra></extra>"
                ),
                showlegend=False,
            )
        )

    x_barras, y_barras, texto_barras = [], [], []
    for barra, (x, y) in coords.items():
        x_barras.append(x)
        y_barras.append(y)
        texto_barras.append(barra)

    fig.add_trace(
        go.Scatter(
            x=x_barras,
            y=y_barras,
            mode="markers+text",
            text=texto_barras,
            textposition="top center",
            marker=dict(size=6, color="#00A78E"),
            hovertemplate="Barra: %{text}<extra></extra>",
            name="Barras",
        )
    )

    fig.update_layout(
        xaxis_title="Coordenada X",
        yaxis_title="Coordenada Y",
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True, scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    layout_padrao(fig, "Caso Base - Fluxo de Potência do Alimentador")
    return fig



def grafico_tensao(df_tensao: pd.DataFrame, df_linhas: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df_tensao.empty or df_linhas.empty:
        layout_padrao(fig, "Perfil de Tensão - dados insuficientes")
        return fig

    tensao_por_barra = (
        df_tensao.set_index("Bus")[["Dist_km", "pu1", "pu2", "pu3"]]
        .to_dict(orient="index")
    )

    nome = "Fase A (representativa)"
    cor = "#0B3C8C"  # azul-marinho
    col = "pu1"

    for _, row in df_linhas.iterrows():
        b1 = row["Bus1"]
        b2 = row["Bus2"]
        if b1 not in tensao_por_barra or b2 not in tensao_por_barra:
            continue

        d1 = float(tensao_por_barra[b1]["Dist_km"])
        d2 = float(tensao_por_barra[b2]["Dist_km"])
        v1 = float(tensao_por_barra[b1][col])
        v2 = float(tensao_por_barra[b2][col])
        trecho = row["Trecho"]

        fig.add_trace(
            go.Scatter(
                x=[d1, d2],
                y=[v1, v2],
                mode="lines+markers",
                name=nome,
                showlegend=False,
                line=dict(color=cor, dash="solid", width=2.6),
                marker=dict(size=5, color=cor),
                text=[b1, b2],
                hovertemplate=(
                    f"Trecho: {trecho}<br>"
                    f"%{{text}}<br>"
                    f"Distância: %{{x:.3f}} km<br>"
                    f"Tensão: %{{y:.5f}} pu<extra>{nome}</extra>"
                ),
            )
        )

    vmin = float(df_tensao[["pu1", "pu2", "pu3"]].min().min())
    vmax = float(df_tensao[["pu1", "pu2", "pu3"]].max().max())
    y0 = min(LIMITE_INFERIOR_PU - 0.002, vmin - 0.003)
    y1 = max(LIMITE_SUPERIOR_PU + 0.002, vmax + 0.003)

    fig.add_hline(
        y=LIMITE_SUPERIOR_PU,
        line_dash="dash",
        line_color="#2F4F6F",
        annotation_text=f"Limite superior = {LIMITE_SUPERIOR_PU:.2f} pu",
        annotation_position="top right",
    )
    fig.add_hline(
        y=LIMITE_INFERIOR_PU,
        line_dash="dash",
        line_color="#2F4F6F",
        annotation_text=f"Limite inferior = {LIMITE_INFERIOR_PU:.2f} pu",
        annotation_position="bottom right",
    )

    fig.update_layout(
        xaxis_title="Distância elétrica (km)",
        yaxis_title="Tensão (pu)",
        yaxis=dict(range=[y0, y1]),
        showlegend=False,
    )
    layout_padrao(fig, "Caso Base - Perfil de Tensão por Trecho (Fase A Representativa)")
    return fig



def grafico_perdas(df_perdas: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df_perdas.empty:
        layout_padrao(fig, "Perdas por Linha - dados insuficientes")
        return fig

    df_plot = df_perdas.sort_values("Perda_kW", ascending=False).copy()
    perda_total = float(df_plot["Perda_kW"].sum())
    df_plot["Participacao_%"] = (df_plot["Perda_kW"] / perda_total * 100.0) if perda_total > 0 else 0.0

    fig.add_trace(
        go.Bar(
            x=df_plot["Trecho"],
            y=df_plot["Participacao_%"],
            text=[f"{v:.2f}%" for v in df_plot["Participacao_%"]],
            textposition="outside",
            marker=dict(color="#5D6BE6"),
            hovertemplate="Trecho: %{x}<br>Participação: %{y:.3f}%<extra></extra>",
            name="Participação nas perdas",
        )
    )

    fig.update_layout(
        xaxis_title="Trecho",
        yaxis_title="Participação no total de perdas (%)",
    )
    layout_padrao(fig, "Caso Base - Participação das Linhas nas Perdas Ativas")
    return fig



def main() -> None:
    garantir_pasta()

    df_linhas = preparar_fluxo(ler_csv_padrao(ARQ_CSV_FLUXO))
    df_tensao = preparar_tensao(ler_csv_padrao(ARQ_CSV_TENSAO))
    df_perdas = preparar_fluxo(ler_csv_padrao(ARQ_CSV_PERDAS))
    coords = ler_buscoords(BUSCOORDS_DSS)

    fig1 = grafico_fluxo(df_linhas, coords)
    fig2 = grafico_tensao(df_tensao, df_linhas)
    fig3 = grafico_perdas(df_perdas)

    salvar_figura(fig1, FIG_FLUXO_HTML, FIG_FLUXO_PNG)
    salvar_figura(fig2, FIG_TENSAO_HTML, FIG_TENSAO_PNG)
    salvar_figura(fig3, FIG_PERDAS_HTML, FIG_PERDAS_PNG)

    print("=== FASE 1 - GRÁFICOS PLOTLY (REVISADO V4) ===")
    print("Arquivos gerados:")
    print(f"- {FIG_FLUXO_HTML}")
    print(f"- {FIG_TENSAO_HTML}")
    print(f"- {FIG_PERDAS_HTML}")
    print(f"- {FIG_FLUXO_PNG}")
    print(f"- {FIG_TENSAO_PNG}")
    print(f"- {FIG_PERDAS_PNG}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Erro ao gerar gráficos da Fase 1 (versão revisada v4).")
        traceback.print_exc()
        raise
