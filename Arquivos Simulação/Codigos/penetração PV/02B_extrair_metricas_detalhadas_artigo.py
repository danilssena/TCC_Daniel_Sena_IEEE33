# -*- coding: utf-8 -*-
r"""
02B_extrair_metricas_detalhadas_artigo.py

OBJETIVO
Extrair, a partir dos CSVs brutos dos monitores do OpenDSS, métricas mais
detalhadas e compatíveis com o estilo das figuras do artigo-base:
- tensão nominal por fase nos pontos de conexão;
- THDv total por fase em barras monitoradas;
- THDi total por fase nos PVs;
- espectros IHDv por fase e por ordem;
- espectros IHDi por fase e por ordem.

IMPORTANTE
O script atual de pós-processamento consolidou muita coisa em "máximo" e "médio".
Isso é bom para síntese, mas ruim para reproduzir figuras como as do artigo,
que trabalham explicitamente com:
- fases A/B/C;
- ordens harmônicas específicas;
- nós/pontos de conexão individualizados. fileciteturn41file0

ENTRADA
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\01_dados_brutos_monitores

SAÍDA
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\02b_metricas_detalhadas_artigo
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
ROOT = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
RAW_ROOT = ROOT / "metodologia" / "03_penetracao_pv" / "01_dados_brutos_monitores"
OUT_ROOT = ROOT / "metodologia" / "03_penetracao_pv" / "02b_metricas_detalhadas_artigo"

PENS = ["PEN_100", "PEN_120", "PEN_150"]
BARRAS_PV = [130, 140, 150, 160, 170, 180]
ORDENS_ANALISE = [3, 5, 7, 9, 11, 13, 15]
CSV_ENCODING = "latin-1"

MON_BUS_RE = re.compile(r"mon_bus_(\d+)", re.IGNORECASE)
MON_PV_RE = re.compile(r"mon_pv_(\d+)", re.IGNORECASE)


# ==============================================================================
# HELPERS
# ==============================================================================
def ler_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def arquivo_bus(pen: str, barra: int | str) -> Path:
    pasta = RAW_ROOT / pen
    candidatos = list(pasta.glob(f"*mon_bus_{barra}_*.csv"))
    if not candidatos:
        raise FileNotFoundError(f"Arquivo de monitor da barra {barra} não encontrado em {pasta}")
    return candidatos[0]


def arquivo_pv(pen: str, barra: int | str) -> Path:
    pasta = RAW_ROOT / pen
    candidatos = list(pasta.glob(f"*mon_pv_{barra}_*.csv"))
    if not candidatos:
        raise FileNotFoundError(f"Arquivo de monitor do PV {barra} não encontrado em {pasta}")
    return candidatos[0]


def arquivo_bus10(pen: str) -> Path:
    pasta = RAW_ROOT / pen
    candidatos = list(pasta.glob("*mon_bus10_*.csv"))
    if not candidatos:
        raise FileNotFoundError(f"Arquivo do monitor BUS10 não encontrado em {pasta}")
    return candidatos[0]


def valor_fundamental(df: pd.DataFrame, col: str) -> float:
    h = pd.to_numeric(df["Harmonic"], errors="coerce")
    s = pd.to_numeric(df[col], errors="coerce")
    fund = s.loc[h == 1]
    if fund.empty:
        return math.nan
    return float(fund.iloc[0])


def thd_percent(df: pd.DataFrame, col: str) -> float:
    h = pd.to_numeric(df["Harmonic"], errors="coerce")
    s = pd.to_numeric(df[col], errors="coerce")

    fund = s.loc[h == 1]
    if fund.empty:
        return math.nan
    base = float(fund.iloc[0])
    if abs(base) < 1e-12:
        return math.nan

    harm = s.loc[h > 1].dropna()
    return float((harm.pow(2).sum() ** 0.5) / abs(base) * 100.0)


def ihd_percent(df: pd.DataFrame, col: str, ordem: int) -> float:
    h = pd.to_numeric(df["Harmonic"], errors="coerce")
    s = pd.to_numeric(df[col], errors="coerce")

    fund = s.loc[h == 1]
    if fund.empty:
        return math.nan
    base = float(fund.iloc[0])
    if abs(base) < 1e-12:
        return math.nan

    xh = s.loc[h == ordem]
    if xh.empty:
        return math.nan
    return float(abs(float(xh.iloc[0])) / abs(base) * 100.0)


def pu_relativo_barra10(df_bus: pd.DataFrame, df_bus10: pd.DataFrame, fase: int) -> float:
    col = f"V{fase}"
    vb = valor_fundamental(df_bus, col)
    v10 = valor_fundamental(df_bus10, col)
    if pd.isna(vb) or pd.isna(v10) or abs(v10) < 1e-12:
        return math.nan
    return float(vb / v10)


# ==============================================================================
# EXTRAÇÃO
# ==============================================================================
def extrair_tensao_nominal_pcc() -> pd.DataFrame:
    regs = []
    for pen in PENS:
        df_ref = ler_csv(arquivo_bus10(pen))
        for barra in BARRAS_PV:
            df_bus = ler_csv(arquivo_bus(pen, barra))
            reg = {
                "penetracao": pen,
                "barra": barra,
                "Vfund_faseA_abs": valor_fundamental(df_bus, "V1"),
                "Vfund_faseB_abs": valor_fundamental(df_bus, "V2"),
                "Vfund_faseC_abs": valor_fundamental(df_bus, "V3"),
                "Vfund_faseA_pu_rel_BUS10": pu_relativo_barra10(df_bus, df_ref, 1),
                "Vfund_faseB_pu_rel_BUS10": pu_relativo_barra10(df_bus, df_ref, 2),
                "Vfund_faseC_pu_rel_BUS10": pu_relativo_barra10(df_bus, df_ref, 3),
            }
            regs.append(reg)
    return pd.DataFrame(regs)


def extrair_thdv_total_por_fase_barras_pv() -> pd.DataFrame:
    regs = []
    for pen in PENS:
        for barra in BARRAS_PV:
            df_bus = ler_csv(arquivo_bus(pen, barra))
            regs.append({
                "penetracao": pen,
                "barra": barra,
                "THDv_faseA_pct": thd_percent(df_bus, "V1"),
                "THDv_faseB_pct": thd_percent(df_bus, "V2"),
                "THDv_faseC_pct": thd_percent(df_bus, "V3"),
            })
    return pd.DataFrame(regs)


def extrair_thdi_total_por_fase_pvs() -> pd.DataFrame:
    regs = []
    for pen in PENS:
        for barra in BARRAS_PV:
            df_pv = ler_csv(arquivo_pv(pen, barra))
            regs.append({
                "penetracao": pen,
                "pv_barra": barra,
                "THDi_faseA_pct": thd_percent(df_pv, "I1"),
                "THDi_faseB_pct": thd_percent(df_pv, "I2"),
                "THDi_faseC_pct": thd_percent(df_pv, "I3"),
            })
    return pd.DataFrame(regs)


def extrair_ihdv_espectro_por_fase() -> pd.DataFrame:
    regs = []
    for pen in PENS:
        for barra in BARRAS_PV:
            df_bus = ler_csv(arquivo_bus(pen, barra))
            for ordem in ORDENS_ANALISE:
                regs.append({
                    "penetracao": pen,
                    "barra": barra,
                    "ordem": ordem,
                    "IHDv_faseA_pct": ihd_percent(df_bus, "V1", ordem),
                    "IHDv_faseB_pct": ihd_percent(df_bus, "V2", ordem),
                    "IHDv_faseC_pct": ihd_percent(df_bus, "V3", ordem),
                })
    return pd.DataFrame(regs)


def extrair_ihdi_espectro_por_fase() -> pd.DataFrame:
    regs = []
    for pen in PENS:
        for barra in BARRAS_PV:
            df_pv = ler_csv(arquivo_pv(pen, barra))
            for ordem in ORDENS_ANALISE:
                regs.append({
                    "penetracao": pen,
                    "pv_barra": barra,
                    "ordem": ordem,
                    "IHDi_faseA_pct": ihd_percent(df_pv, "I1", ordem),
                    "IHDi_faseB_pct": ihd_percent(df_pv, "I2", ordem),
                    "IHDi_faseC_pct": ihd_percent(df_pv, "I3", ordem),
                })
    return pd.DataFrame(regs)


def extrair_espectro_completo_barra_critica() -> pd.DataFrame:
    regs = []
    barra = 180
    for pen in PENS:
        df_bus = ler_csv(arquivo_bus(pen, barra))
        df_pv = ler_csv(arquivo_pv(pen, barra))
        for ordem in [1] + ORDENS_ANALISE:
            regs.append({
                "penetracao": pen,
                "barra_critica": barra,
                "ordem": ordem,
                "IHDv_faseA_pct": ihd_percent(df_bus, "V1", ordem) if ordem != 1 else 100.0,
                "IHDv_faseB_pct": ihd_percent(df_bus, "V2", ordem) if ordem != 1 else 100.0,
                "IHDv_faseC_pct": ihd_percent(df_bus, "V3", ordem) if ordem != 1 else 100.0,
                "IHDi_faseA_pct": ihd_percent(df_pv, "I1", ordem) if ordem != 1 else 100.0,
                "IHDi_faseB_pct": ihd_percent(df_pv, "I2", ordem) if ordem != 1 else 100.0,
                "IHDi_faseC_pct": ihd_percent(df_pv, "I3", ordem) if ordem != 1 else 100.0,
            })
    return pd.DataFrame(regs)


# ==============================================================================
# MAIN
# ==============================================================================
def main() -> None:
    print("=" * 100)
    print("02B_extrair_metricas_detalhadas_artigo.py")
    print("Extração detalhada por fase e por ordem harmônica")
    print("=" * 100)
    print(f"Entrada : {RAW_ROOT}")
    print(f"Saída   : {OUT_ROOT}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    df_tensao = extrair_tensao_nominal_pcc()
    df_thdv = extrair_thdv_total_por_fase_barras_pv()
    df_thdi = extrair_thdi_total_por_fase_pvs()
    df_ihdv = extrair_ihdv_espectro_por_fase()
    df_ihdi = extrair_ihdi_espectro_por_fase()
    df_espec = extrair_espectro_completo_barra_critica()

    arquivos = {
        "01_tensao_nominal_pcc_por_fase.csv": df_tensao,
        "02_thdv_total_por_fase_barras_pv.csv": df_thdv,
        "03_thdi_total_por_fase_pvs.csv": df_thdi,
        "04_ihdv_espectro_por_fase_barras_pv.csv": df_ihdv,
        "05_ihdi_espectro_por_fase_pvs.csv": df_ihdi,
        "06_espectro_completo_barra_critica.csv": df_espec,
    }

    for nome, df in arquivos.items():
        df.to_csv(OUT_ROOT / nome, sep=";", decimal=",", index=False, encoding="utf-8-sig")

    print("\nArquivos gerados:")
    for nome in arquivos:
        print(f" - {nome}")

    print("\nConcluído com sucesso.")


if __name__ == "__main__":
    main()
