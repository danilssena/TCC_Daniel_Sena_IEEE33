# -*- coding: utf-8 -*-
r"""
04B_auditar_perdas_e_gerar_G09_refinado.py

SAÍDAS
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\04_perdas_ativas
- auditoria_perdas_por_cenario.csv
- G09_Perdas_ativas_totais_por_cenario_refinado.html
- G09_Perdas_ativas_totais_por_cenario_refinado.png
- G09_Perdas_ativas_totais_por_cenario_refinado.svg
"""

from __future__ import annotations

from pathlib import Path
import traceback

import pandas as pd
import py_dss_interface
import plotly.graph_objects as go

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
ROOT = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
MASTER = ROOT / "masterH_caso_base_minimo.dss"

OUT_DIR = ROOT / "metodologia" / "03_penetracao_pv" / "04_perdas_ativas"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_OUT = OUT_DIR / "auditoria_perdas_por_cenario.csv"
HTML_OUT = OUT_DIR / "G09_Perdas_ativas_totais_por_cenario_refinado.html"
PNG_OUT = OUT_DIR / "G09_Perdas_ativas_totais_por_cenario_refinado.png"
SVG_OUT = OUT_DIR / "G09_Perdas_ativas_totais_por_cenario_refinado.svg"

BARRAS_PV = ["130", "140", "150", "160", "170", "180"]
P_BASE_PEN_KW = 3000.0
PENETRACOES = {
    "CASO_BASE": 0.00,
    "PEN_100": 1.00,
    "PEN_120": 1.20,
    "PEN_150": 1.50,
}
KVA_PMPP_RATIO = 1.10
XHL_TRAFO_PV = 5.75

COR_BASE = "black"
COR_P100 = "#0B3C8C"
COR_P120 = "#C62828"
COR_P150 = "#6EC6FF"

MAP_CORES = {
    "CASO_BASE": COR_BASE,
    "PEN_100": COR_P100,
    "PEN_120": COR_P120,
    "PEN_150": COR_P150,
}

# ==============================================================================
# HELPERS
# ==============================================================================
def compilar(dss) -> None:
    dss.text("Clear")
    dss.text(f'Compile "{MASTER}"')


def solve_snapshot(dss) -> None:
    dss.text("Set Mode=Snap")
    dss.text("Set ControlMode=Static")
    dss.text("Solve")
    if not dss.solution.converged:
        raise RuntimeError("Fluxo de carga não convergiu.")


def criar_pvs_6_barras(dss, penetracao: float) -> tuple[float, float]:
    pv_total_kw = P_BASE_PEN_KW * penetracao
    pmpp_por_pv = pv_total_kw / len(BARRAS_PV)
    kva_por_pv = pmpp_por_pv * KVA_PMPP_RATIO

    for bus in BARRAS_PV:
        trafo = f"TR_PV_{bus}"
        bus_pv = f"BUS_PV_{bus}"
        pv = f"PV_{bus}"

        dss.text(f"New Transformer.{trafo} phases=3 windings=2 xhl={XHL_TRAFO_PV}")
        dss.text(f"~ wdg=1 bus={bus} conn=wye kv=13.8 kVA={kva_por_pv:.6f}")
        dss.text(f"~ wdg=2 bus={bus_pv} conn=wye kv=0.22 kVA={kva_por_pv:.6f}")

        dss.text(f"New PVSystem.{pv} phases=3 bus1={bus_pv} kv=0.22")
        dss.text(f"~ pmpp={pmpp_por_pv:.6f} kVA={kva_por_pv:.6f} pf=1")

    return pmpp_por_pv, kva_por_pv


def perdas_metodo_a_circuit_losses(dss) -> tuple[float, float]:
    """Retorna perdas totais pelo circuito.losses em kW/kvar."""
    losses = list(dss.circuit.losses)
    if len(losses) < 2:
        raise RuntimeError("Não foi possível ler dss.circuit.losses.")
    p_w = float(losses[0])
    q_var = float(losses[1])
    return p_w / 1000.0, q_var / 1000.0


def _losses_active_element(dss, element_name: str) -> tuple[float, float]:
    ok = dss.circuit.set_active_element(element_name)
    if ok == 0:
        return 0.0, 0.0
    losses = list(dss.cktelement.losses)
    if len(losses) < 2:
        return 0.0, 0.0
    return float(losses[0]) / 1000.0, float(losses[1]) / 1000.0


def perdas_metodo_b_soma_elementos(dss) -> tuple[float, float]:
    """
    Soma perdas de linhas e transformadores, via cktelement.losses.
    É uma checagem independente de circuit.losses.
    """
    p_kw = 0.0
    q_kvar = 0.0

    try:
        line_names = [n for n in list(dss.lines.names) if n]
    except Exception:
        line_names = []

    try:
        trafo_names = [n for n in list(dss.transformers.names) if n]
    except Exception:
        trafo_names = []

    for name in line_names:
        p, q = _losses_active_element(dss, f"Line.{name}")
        p_kw += p
        q_kvar += q

    for name in trafo_names:
        p, q = _losses_active_element(dss, f"Transformer.{name}")
        p_kw += p
        q_kvar += q

    return p_kw, q_kvar


def total_power(dss) -> tuple[float, float]:
    tp = list(dss.circuit.total_power)
    if len(tp) < 2:
        return float("nan"), float("nan")
    return abs(float(tp[0])), abs(float(tp[1]))


def montar_cenario(dss, nome: str, pen: float) -> dict:
    compilar(dss)

    pmpp_por_pv = 0.0
    kva_por_pv = 0.0
    potencia_fv_total_kw = 0.0

    if nome != "CASO_BASE":
        pmpp_por_pv, kva_por_pv = criar_pvs_6_barras(dss, pen)
        potencia_fv_total_kw = P_BASE_PEN_KW * pen

    solve_snapshot(dss)

    pA_kw, qA_kvar = perdas_metodo_a_circuit_losses(dss)
    pB_kw, qB_kvar = perdas_metodo_b_soma_elementos(dss)
    p_total_kw, q_total_kvar = total_power(dss)

    erro_abs_kw = abs(pA_kw - pB_kw)
    erro_rel_pct = (erro_abs_kw / pA_kw * 100.0) if abs(pA_kw) > 1e-12 else 0.0

    return {
        "cenario": nome,
        "penetracao_pct": int(round(pen * 100)),
        "potencia_fv_total_kw": potencia_fv_total_kw,
        "pmpp_por_pv_kw": pmpp_por_pv,
        "kva_por_pv": kva_por_pv,
        "perdas_ativas_metodo_A_kw": pA_kw,
        "perdas_reativas_metodo_A_kvar": qA_kvar,
        "perdas_ativas_metodo_B_kw": pB_kw,
        "perdas_reativas_metodo_B_kvar": qB_kvar,
        "erro_absoluto_kw": erro_abs_kw,
        "erro_relativo_pct": erro_rel_pct,
        "potencia_total_suprida_kw": p_total_kw,
        "potencia_total_suprida_kvar": q_total_kvar,
    }


def gerar_g09(df: pd.DataFrame) -> go.Figure:
    ordem = ["CASO_BASE", "PEN_100", "PEN_120", "PEN_150"]
    df = df.copy()
    df["ordem_plot"] = df["cenario"].map({k: i for i, k in enumerate(ordem)})
    df = df.sort_values("ordem_plot")

    y = df["perdas_ativas_metodo_A_kw"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["cenario"],
        y=y,
        marker_color=[MAP_CORES.get(c, "gray") for c in df["cenario"]],
        text=[f"{v:.2f} kW" for v in y],
        textposition="outside",
        textfont=dict(size=18),
        hovertemplate="Cenário %{x}<br>Perdas ativas=%{y:.3f} kW<extra></extra>",
        name="Perdas ativas totais",
    ))

    fig.update_layout(
        title=dict(
            text="G09. Perdas ativas totais por cenário",
            x=0.5,
            xanchor="center",
            font=dict(size=28),
        ),
        template="plotly_white",
        width=1300,
        height=760,
        xaxis=dict(
            title=dict(text="Cenário", font=dict(size=20)),
            tickfont=dict(size=16),
        ),
        yaxis=dict(
            title=dict(text="Perdas ativas totais (kW)", font=dict(size=20)),
            tickfont=dict(size=16),
        ),
        font=dict(size=16),
        margin=dict(l=90, r=40, t=110, b=80),
        showlegend=False,
    )
    return fig


# ==============================================================================
# MAIN
# ==============================================================================
def main() -> None:
    print("=" * 100)
    print("04B_auditar_perdas_e_gerar_G09_refinado.py")
    print("=" * 100)
    print(f"Master: {MASTER}")
    print(f"Saída : {OUT_DIR}")

    dss = py_dss_interface.DSS()
    registros = []

    for nome, pen in PENETRACOES.items():
        print(f"\nRodando {nome}...")
        registros.append(montar_cenario(dss, nome, pen))

    df = pd.DataFrame(registros)
    df.to_csv(CSV_OUT, sep=";", decimal=",", index=False, encoding="utf-8-sig")

    print("\nResumo da auditoria:")
    cols = [
        "cenario",
        "perdas_ativas_metodo_A_kw",
        "perdas_ativas_metodo_B_kw",
        "erro_absoluto_kw",
        "erro_relativo_pct",
        "potencia_total_suprida_kw",
    ]
    print(df[cols].to_string(index=False))

    fig = gerar_g09(df)
    fig.write_html(str(HTML_OUT), include_plotlyjs="cdn")

    try:
        fig.write_image(str(PNG_OUT), width=1300, height=760, scale=2)
        fig.write_image(str(SVG_OUT), width=1300, height=760, scale=2)
        print(f"\nGráfico salvo em:\n - {HTML_OUT}\n - {PNG_OUT}\n - {SVG_OUT}")
    except Exception as e:
        print("\nHTML gerado, mas PNG/SVG não puderam ser exportados.")
        print("Motivo:", e)
        print(f"Arquivo HTML: {HTML_OUT}")

    print(f"\nCSV salvo em:\n - {CSV_OUT}")
    print("\nConcluído com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Erro na execução.")
        traceback.print_exc()
        raise
