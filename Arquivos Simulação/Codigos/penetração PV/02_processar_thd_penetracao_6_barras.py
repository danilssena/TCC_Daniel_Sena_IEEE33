# -*- coding: utf-8 -*-
r"""
02_processar_thd_penetracao_6_barras.py

Pós-processamento dos monitores exportados para o estudo simplificado:
- PEN_100
- PEN_120
- PEN_150

O script:
- lê os CSVs brutos dos monitores exportados pelo OpenDSS;
- identifica automaticamente monitores de barra e monitores de PV;
- calcula THDv por barra;
- calcula THDi nos PVs;
- calcula IHDv e IHDi nas ordens 3, 5 e 7;
- gera arquivos consolidados para a etapa seguinte de gráficos.

Entradas:
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final(gpt)\metodologia\03_penetracao_pv\01_dados_brutos_monitores

Saídas:
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final(gpt)\metodologia\03_penetracao_pv\02_processados_thd
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd


# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
DIRETORIO_PROJETO = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
INPUT_ROOT = DIRETORIO_PROJETO / "metodologia" / "03_penetracao_pv" / "01_dados_brutos_monitores"
OUTPUT_ROOT = DIRETORIO_PROJETO / "metodologia" / "03_penetracao_pv" / "02_processados_thd"

PRINCIPAIS_ORDENS = [3, 5, 7]
CSV_ENCODING = "latin-1"


# ==============================================================================
# HELPERS
# ==============================================================================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


PEN_RE = re.compile(r"PEN_(\d+)", re.IGNORECASE)
MON_BUS_RE = re.compile(r"mon_bus_(\d+)", re.IGNORECASE)
MON_PV_RE = re.compile(r"mon_pv_(\d+)", re.IGNORECASE)


def extract_penetracao(path: Path) -> str:
    for part in path.parts:
        m = PEN_RE.search(part)
        if m:
            return f"PEN_{m.group(1)}"
    return "PEN_UNKNOWN"


def infer_monitor_type(path: Path) -> tuple[str, str]:
    name = path.name.lower()

    m_bus = MON_BUS_RE.search(name)
    if m_bus:
        return "BUS", m_bus.group(1)

    m_pv = MON_PV_RE.search(name)
    if m_pv:
        return "PV", m_pv.group(1)

    if "mon_pac" in name:
        return "PAC", "PAC"

    if "mon_bus10" in name:
        return "REF", "BUS10"

    return "OUTRO", path.stem.upper()


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def compute_thd_from_series(harmonic: pd.Series, mag: pd.Series) -> float:
    harmonic = safe_numeric(harmonic)
    mag = safe_numeric(mag)

    fundamental = mag.loc[harmonic == 1]
    if fundamental.empty:
        return math.nan

    v1 = float(fundamental.iloc[0])
    if abs(v1) < 1e-12:
        return math.nan

    others = mag.loc[harmonic > 1].dropna()
    return float((others.pow(2).sum() ** 0.5) / abs(v1) * 100.0)


def get_ihd(harmonic: pd.Series, mag: pd.Series, ordem: int) -> float:
    harmonic = safe_numeric(harmonic)
    mag = safe_numeric(mag)

    fundamental = mag.loc[harmonic == 1]
    if fundamental.empty:
        return math.nan

    v1 = float(fundamental.iloc[0])
    if abs(v1) < 1e-12:
        return math.nan

    vh = mag.loc[harmonic == ordem]
    if vh.empty:
        return math.nan

    return float(abs(float(vh.iloc[0])) / abs(v1) * 100.0)


def collect_csv_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.csv"))


# ==============================================================================
# PROCESSAMENTO POR ARQUIVO
# ==============================================================================
def process_bus_file(path: Path) -> dict | None:
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    df = normalize_columns(df)

    if "Harmonic" not in df.columns:
        return None

    pen = extract_penetracao(path)
    _, barra = infer_monitor_type(path)
    harm = df["Harmonic"]

    row: dict[str, object] = {
        "penetracao": pen,
        "barra": barra,
        "arquivo": str(path),
    }

    thds = []
    for fase in [1, 2, 3]:
        col = f"V{fase}"
        if col in df.columns:
            thd = compute_thd_from_series(harm, df[col])
            row[f"THDv_fase{fase}_pct"] = thd
            thds.append(thd)

            for ordem in PRINCIPAIS_ORDENS:
                row[f"IHDv_h{ordem}_fase{fase}_pct"] = get_ihd(harm, df[col], ordem)
        else:
            row[f"THDv_fase{fase}_pct"] = math.nan
            for ordem in PRINCIPAIS_ORDENS:
                row[f"IHDv_h{ordem}_fase{fase}_pct"] = math.nan

    thds_validos = [x for x in thds if pd.notna(x)]
    row["THDv_max_pct"] = max(thds_validos) if thds_validos else math.nan
    row["THDv_med_pct"] = sum(thds_validos) / len(thds_validos) if thds_validos else math.nan
    return row


def process_pv_file(path: Path) -> dict | None:
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    df = normalize_columns(df)

    if "Harmonic" not in df.columns:
        return None

    pen = extract_penetracao(path)
    _, pv_bus = infer_monitor_type(path)
    harm = df["Harmonic"]

    row: dict[str, object] = {
        "penetracao": pen,
        "pv_bus": pv_bus,
        "arquivo": str(path),
    }

    thds = []
    for fase in [1, 2, 3]:
        col = f"I{fase}"
        if col in df.columns:
            thd = compute_thd_from_series(harm, df[col])
            row[f"THDi_fase{fase}_pct"] = thd
            thds.append(thd)

            for ordem in PRINCIPAIS_ORDENS:
                row[f"IHDi_h{ordem}_fase{fase}_pct"] = get_ihd(harm, df[col], ordem)
        else:
            row[f"THDi_fase{fase}_pct"] = math.nan
            for ordem in PRINCIPAIS_ORDENS:
                row[f"IHDi_h{ordem}_fase{fase}_pct"] = math.nan

    thds_validos = [x for x in thds if pd.notna(x)]
    row["THDi_max_pct"] = max(thds_validos) if thds_validos else math.nan
    row["THDi_med_pct"] = sum(thds_validos) / len(thds_validos) if thds_validos else math.nan
    return row


# ==============================================================================
# CONSOLIDAÇÃO
# ==============================================================================
def build_bus_order_summary(df_bus: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df_bus.iterrows():
        for ordem in PRINCIPAIS_ORDENS:
            vals = [
                r.get(f"IHDv_h{ordem}_fase1_pct", math.nan),
                r.get(f"IHDv_h{ordem}_fase2_pct", math.nan),
                r.get(f"IHDv_h{ordem}_fase3_pct", math.nan),
            ]
            vals = [v for v in vals if pd.notna(v)]
            rows.append({
                "penetracao": r["penetracao"],
                "barra": r["barra"],
                "ordem": ordem,
                "IHDv_max_pct": max(vals) if vals else math.nan,
                "IHDv_med_pct": sum(vals) / len(vals) if vals else math.nan,
            })
    return pd.DataFrame(rows)


def build_pv_order_summary(df_pv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df_pv.iterrows():
        for ordem in PRINCIPAIS_ORDENS:
            vals = [
                r.get(f"IHDi_h{ordem}_fase1_pct", math.nan),
                r.get(f"IHDi_h{ordem}_fase2_pct", math.nan),
                r.get(f"IHDi_h{ordem}_fase3_pct", math.nan),
            ]
            vals = [v for v in vals if pd.notna(v)]
            rows.append({
                "penetracao": r["penetracao"],
                "pv_bus": r["pv_bus"],
                "ordem": ordem,
                "IHDi_max_pct": max(vals) if vals else math.nan,
                "IHDi_med_pct": sum(vals) / len(vals) if vals else math.nan,
            })
    return pd.DataFrame(rows)


def ordenar_barras(df: pd.DataFrame, col: str) -> pd.DataFrame:
    df = df.copy()
    df["_ord"] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["penetracao", "_ord", col]).drop(columns="_ord").reset_index(drop=True)


# ==============================================================================
# MAIN
# ==============================================================================
def main() -> None:
    print("=" * 100)
    print("02_processar_thd_penetracao_6_barras.py")
    print("Processamento de THDv, THDi, IHDv e IHDi")
    print("=" * 100)
    print(f"Entrada : {INPUT_ROOT}")
    print(f"Saída   : {OUTPUT_ROOT}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    csv_files = collect_csv_files(INPUT_ROOT)
    if not csv_files:
        raise FileNotFoundError(f"Nenhum CSV encontrado em: {INPUT_ROOT}")

    bus_rows = []
    pv_rows = []

    for path in csv_files:
        tipo, _ = infer_monitor_type(path)

        if tipo == "BUS":
            row = process_bus_file(path)
            if row:
                bus_rows.append(row)

        elif tipo == "PV":
            row = process_pv_file(path)
            if row:
                pv_rows.append(row)

    if not bus_rows:
        raise RuntimeError("Nenhum monitor de barra foi processado.")
    if not pv_rows:
        raise RuntimeError("Nenhum monitor de PV foi processado.")

    df_bus = pd.DataFrame(bus_rows)
    df_pv = pd.DataFrame(pv_rows)

    df_bus = ordenar_barras(df_bus, "barra")
    df_pv = ordenar_barras(df_pv, "pv_bus")

    # Arquivos principais
    arq_bus = OUTPUT_ROOT / "THDv_barras_consolidado.csv"
    arq_pv = OUTPUT_ROOT / "THDi_pvs_consolidado.csv"
    df_bus.to_csv(arq_bus, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    df_pv.to_csv(arq_pv, sep=";", decimal=",", index=False, encoding="utf-8-sig")

    # Top 10 barras mais afetadas por penetração
    df_top = (
        df_bus[["penetracao", "barra", "THDv_max_pct", "THDv_med_pct"]]
        .sort_values(["penetracao", "THDv_max_pct"], ascending=[True, False])
        .groupby(["penetracao"], group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )
    df_top.to_csv(OUTPUT_ROOT / "TOP10_barras_mais_afetadas.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")

    # Resumos
    resumo_bus = (
        df_bus.groupby(["penetracao"], as_index=False)
        .agg(
            THDv_max_global_pct=("THDv_max_pct", "max"),
            THDv_media_barras_pct=("THDv_med_pct", "mean"),
            n_barras=("barra", "count"),
        )
    )
    resumo_pv = (
        df_pv.groupby(["penetracao"], as_index=False)
        .agg(
            THDi_max_global_pct=("THDi_max_pct", "max"),
            THDi_media_pvs_pct=("THDi_med_pct", "mean"),
            n_pvs=("pv_bus", "count"),
        )
    )
    resumo_bus.to_csv(OUTPUT_ROOT / "resumo_THDv_por_penetracao.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    resumo_pv.to_csv(OUTPUT_ROOT / "resumo_THDi_por_penetracao.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")

    # Resumo por ordem
    bus_ordens = build_bus_order_summary(df_bus)
    pv_ordens = build_pv_order_summary(df_pv)
    bus_ordens = ordenar_barras(bus_ordens, "barra")
    pv_ordens = ordenar_barras(pv_ordens, "pv_bus")

    bus_ordens.to_csv(OUTPUT_ROOT / "IHDv_barras_ordens_3_5_7.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    pv_ordens.to_csv(OUTPUT_ROOT / "IHDi_pvs_ordens_3_5_7.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")

    print(f"CSVs lidos        : {len(csv_files)}")
    print(f"Monitores de barra: {len(df_bus)}")
    print(f"Monitores de PV   : {len(df_pv)}")

    print("\nResumo THDv por penetração:")
    print(resumo_bus.to_string(index=False))

    print("\nResumo THDi por penetração:")
    print(resumo_pv.to_string(index=False))

    print("\nArquivos gerados:")
    for p in sorted(OUTPUT_ROOT.glob("*.csv")):
        print(f" - {p.name}")

    print("\nProcessamento concluído com sucesso.")


if __name__ == "__main__":
    main()
