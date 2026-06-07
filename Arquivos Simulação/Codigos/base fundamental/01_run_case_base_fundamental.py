# -*- coding: utf-8 -*-
"""
FASE 1 - CASO BASE FUNDAMENTAL
Script 01: simulação + extração de dados base

Objetivo
--------
1) Compilar o Master.dss (sem PV)
2) Resolver o fluxo de potência em regime fundamental (Snapshot)
3) Extrair tensões por barra, fluxos por linha e perdas por linha
4) Calcular distância elétrica acumulada até cada barra
5) Salvar CSVs e um resumo textual dentro da pasta metodologia

Saídas
------
IEEE_Final\metodologia\01_caso_base_fundamental\
  01_dados_brutos\
  02_processados\
  03_figuras\
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import math
import re
import traceback

import pandas as pd
import py_dss_interface


# ==========================================================
# CONFIGURAÇÕES DO PROJETO
# ==========================================================
PROJETO_DIR = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
MASTER_DSS = PROJETO_DIR / "Master.dss"
BUSCOORDS_DSS = PROJETO_DIR / "BusCoords.dss"

METODOLOGIA_DIR = PROJETO_DIR / "metodologia"
FASE1_DIR = METODOLOGIA_DIR / "01_caso_base_fundamental"
DADOS_BRUTOS_DIR = FASE1_DIR / "01_dados_brutos"
PROCESSADOS_DIR = FASE1_DIR / "02_processados"
FIGURAS_DIR = FASE1_DIR / "03_figuras"

ARQ_EXP_VOLT = DADOS_BRUTOS_DIR / "EXP_VOLTAGES.csv"
ARQ_CSV_FLUXO = PROCESSADOS_DIR / "fluxo_potencia_linhas.csv"
ARQ_CSV_TENSAO = PROCESSADOS_DIR / "perfil_tensao_barras.csv"
ARQ_CSV_PERDAS = PROCESSADOS_DIR / "perdas_por_linha.csv"
ARQ_TXT_RESUMO = PROCESSADOS_DIR / "resumo_caso_base_fundamental.txt"

BARRA_FONTE_PREFERIDA = "SOURCEBUS"
BASEKV_MIN = 1.0


# ==========================================================
# HELPERS
# ==========================================================
def garantir_pastas() -> None:
    for pasta in [METODOLOGIA_DIR, FASE1_DIR, DADOS_BRUTOS_DIR, PROCESSADOS_DIR, FIGURAS_DIR]:
        pasta.mkdir(parents=True, exist_ok=True)


def normalizar_barra(nome: str) -> str:
    return str(nome).strip().replace('"', '').split('.')[0].upper()


def converter_para_km(length_value: float, unit_code: int) -> float:
    try:
        length_value = float(length_value)
    except Exception:
        return 0.0

    mapa = {
        1: 1.609344,      # mi -> km
        2: 0.3048,        # kft -> km
        3: 1.0,           # km -> km
        4: 0.001,         # m -> km
        5: 0.0003048,     # ft -> km
        6: 0.0000254,     # in -> km
        7: 0.00001,       # cm -> km
    }
    return length_value * mapa.get(unit_code, 1.0)


def extrair_fluxo_kw(powers: list[float]) -> float:
    if not powers:
        return 0.0
    if len(powers) >= 6:
        return abs(float(powers[0]) + float(powers[2]) + float(powers[4]))
    if len(powers) >= 2:
        return abs(float(powers[0]))
    return 0.0


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
            barra = normalizar_barra(partes[0])
            try:
                x = float(partes[1])
                y = float(partes[2])
            except Exception:
                continue
            coords[barra] = (x, y)
    return coords


def calcular_distancias(df_linhas: pd.DataFrame, barra_raiz: str) -> dict[str, float]:
    grafo = defaultdict(list)
    for _, row in df_linhas.iterrows():
        b1 = str(row["Bus1"]).upper()
        b2 = str(row["Bus2"]).upper()
        dist = float(row["Comprimento_km"])
        grafo[b1].append((b2, dist))
        grafo[b2].append((b1, dist))

    if barra_raiz not in grafo:
        barra_raiz = str(df_linhas.iloc[0]["Bus1"]).upper()

    distancias = {barra_raiz: 0.0}
    fila = deque([barra_raiz])
    while fila:
        atual = fila.popleft()
        for vizinho, comp in grafo[atual]:
            if vizinho not in distancias:
                distancias[vizinho] = distancias[atual] + comp
                fila.append(vizinho)
    return distancias


# ==========================================================
# EXTRAÇÃO OPENDSS
# ==========================================================
def compilar_e_resolver(dss: py_dss_interface.DSS) -> None:
    dss.text("Clear")
    dss.text(f'Compile "{MASTER_DSS}"')
    dss.text("Set Mode=Snap")
    dss.text("Set ControlMode=Static")
    dss.text("Solve")
    if not dss.solution.converged:
        raise RuntimeError("Fluxo de potência do caso base não convergiu.")


def obter_linhas(dss: py_dss_interface.DSS) -> tuple[pd.DataFrame, str]:
    nomes = list(dss.lines.names)
    if not nomes:
        raise RuntimeError("Nenhuma linha encontrada no circuito.")

    registros = []
    for nome in nomes:
        dss.lines.name = nome
        bus1 = normalizar_barra(dss.lines.bus1)
        bus2 = normalizar_barra(dss.lines.bus2)

        try:
            comprimento = float(dss.lines.length)
        except Exception:
            comprimento = 0.0
        try:
            unidade = int(dss.lines.units)
        except Exception:
            unidade = 3
        comprimento_km = converter_para_km(comprimento, unidade)

        dss.circuit.set_active_element(f"Line.{nome}")
        powers = list(dss.cktelement.powers)
        losses = list(dss.cktelement.losses)
        currents = list(dss.cktelement.currents_mag_ang)

        fluxo_kw = extrair_fluxo_kw(powers)
        perda_kw = abs(float(losses[0])) / 1000.0 if losses else 0.0
        perda_kvar = abs(float(losses[1])) / 1000.0 if len(losses) > 1 else 0.0

        mags = [abs(v) for v in currents[0::2][:3]] if currents else []
        i_max = max(mags) if mags else 0.0

        registros.append({
            "Linha": f"Line.{nome}",
            "Trecho": str(nome),
            "Bus1": bus1,
            "Bus2": bus2,
            "Comprimento_km": comprimento_km,
            "P_kW": fluxo_kw,
            "Perda_kW": perda_kw,
            "Perda_kvar": perda_kvar,
            "I_max_A": i_max,
        })

    df = pd.DataFrame(registros)
    buses = set(df["Bus1"]).union(set(df["Bus2"]))
    if BARRA_FONTE_PREFERIDA in buses:
        barra_raiz = BARRA_FONTE_PREFERIDA
    elif "10" in buses:
        barra_raiz = "10"
    else:
        barra_raiz = str(df.iloc[0]["Bus1"]).upper()
    return df.sort_values("Linha").reset_index(drop=True), barra_raiz


def exportar_tensoes(dss: py_dss_interface.DSS) -> pd.DataFrame:
    dss.text(f'Export Voltages "{ARQ_EXP_VOLT}"')
    if not ARQ_EXP_VOLT.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {ARQ_EXP_VOLT}")

    df = pd.read_csv(ARQ_EXP_VOLT, encoding="latin-1")
    df.columns = [c.strip() for c in df.columns]
    mapa = {c.lower(): c for c in df.columns}
    obrig = ["bus", "basekv", "pu1", "pu2", "pu3"]
    faltantes = [c for c in obrig if c not in mapa]
    if faltantes:
        raise RuntimeError(f"EXP_VOLTAGES.csv sem colunas esperadas: {faltantes}")

    out = df[[mapa["bus"], mapa["basekv"], mapa["pu1"], mapa["pu2"], mapa["pu3"]]].copy()
    out.columns = ["Bus", "BasekV", "pu1", "pu2", "pu3"]
    out["Bus"] = out["Bus"].astype(str).map(normalizar_barra)
    for col in ["BasekV", "pu1", "pu2", "pu3"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Bus"]).reset_index(drop=True)
    out = out[out["BasekV"] >= BASEKV_MIN].copy()
    return out


def montar_perfil_tensao(df_linhas: pd.DataFrame, df_tensoes: pd.DataFrame, barra_raiz: str) -> pd.DataFrame:
    distancias = calcular_distancias(df_linhas, barra_raiz)
    out = df_tensoes.copy()
    out["Dist_km"] = out["Bus"].map(distancias)
    out = out.dropna(subset=["Dist_km"]).copy()
    out = out.sort_values(["Dist_km", "Bus"]).reset_index(drop=True)
    return out[["Bus", "BasekV", "Dist_km", "pu1", "pu2", "pu3"]]


def salvar_resumo(df_linhas: pd.DataFrame, df_tensoes: pd.DataFrame, barra_raiz: str) -> None:
    p_total_kw = float(df_linhas["P_kW"].max()) if not df_linhas.empty else 0.0
    perda_total_kw = float(df_linhas["Perda_kW"].sum()) if not df_linhas.empty else 0.0
    vmin = float(df_tensoes[["pu1", "pu2", "pu3"]].min().min()) if not df_tensoes.empty else float("nan")
    vmax = float(df_tensoes[["pu1", "pu2", "pu3"]].max().max()) if not df_tensoes.empty else float("nan")

    texto = []
    texto.append("=== RESUMO - CASO BASE FUNDAMENTAL ===")
    texto.append(f"Barra raiz: {barra_raiz}")
    texto.append(f"Número de linhas: {len(df_linhas)}")
    texto.append(f"Número de barras avaliadas: {len(df_tensoes)}")
    texto.append(f"Fluxo máximo por trecho: {p_total_kw:.4f} kW")
    texto.append(f"Perda ativa total nas linhas: {perda_total_kw:.4f} kW")
    texto.append(f"Tensão mínima (pu): {vmin:.6f}")
    texto.append(f"Tensão máxima (pu): {vmax:.6f}")
    texto.append("")
    texto.append("Validação esperada:")
    texto.append("- Convergência do fluxo de potência em Snapshot")
    texto.append("- Perfil de tensão coerente com a topologia radial")
    texto.append("- Perdas compatíveis com a rede-base")
    ARQ_TXT_RESUMO.write_text("\n".join(texto), encoding="utf-8")


# ==========================================================
# MAIN
# ==========================================================
def main() -> None:
    garantir_pastas()
    dss = py_dss_interface.DSS()
    compilar_e_resolver(dss)

    df_linhas, barra_raiz = obter_linhas(dss)
    df_tensoes = exportar_tensoes(dss)
    df_perfil = montar_perfil_tensao(df_linhas, df_tensoes, barra_raiz)

    df_linhas.to_csv(ARQ_CSV_FLUXO, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    df_perfil.to_csv(ARQ_CSV_TENSAO, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    df_linhas[["Linha", "Trecho", "Bus1", "Bus2", "Perda_kW", "Perda_kvar"]].to_csv(
        ARQ_CSV_PERDAS, sep=";", decimal=",", index=False, encoding="utf-8-sig"
    )
    salvar_resumo(df_linhas, df_perfil, barra_raiz)

    print("=== FASE 1 - CASO BASE FUNDAMENTAL ===")
    print(f"Master DSS   : {MASTER_DSS}")
    print(f"Pasta Fase 1 : {FASE1_DIR}")
    print(f"Barra raiz   : {barra_raiz}")
    print("\nArquivos gerados:")
    print(f"- {ARQ_EXP_VOLT}")
    print(f"- {ARQ_CSV_FLUXO}")
    print(f"- {ARQ_CSV_TENSAO}")
    print(f"- {ARQ_CSV_PERDAS}")
    print(f"- {ARQ_TXT_RESUMO}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\nERRO NA FASE 1 - CASO BASE FUNDAMENTAL")
        print(str(e))
        print(traceback.format_exc())
        raise
