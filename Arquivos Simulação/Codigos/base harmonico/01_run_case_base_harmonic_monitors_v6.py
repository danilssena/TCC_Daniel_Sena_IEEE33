# -*- coding: utf-8 -*-
"""
FASE 2 - CASO BASE HARMÔNICO LIMPO (V6)
Limpeza explícita das cargas VIA PYTHON

Ideia central:
- compilar o master harmônico mínimo;
- criar, via Python/OpenDSS, um spectrum limpo para a fonte e para as cargas;
- aplicar spectrum limpo explicitamente em TODAS as cargas;
- depois seguir o mesmo pipeline:
    monitores em todas as barras -> Snapshot -> Harmonic -> exportação -> THDv

Observação metodológica:
- esta mesma rotina de limpeza das cargas sera mantida também nos casos com PV;
- ou seja, nos cenários com penetração FV, os harmônicos devem vir do PVSystem,
  e não de emissão residual/default das cargas.
"""

from __future__ import annotations

import glob
import math
import os
import re
import shutil
from pathlib import Path

import pandas as pd
import py_dss_interface

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
DIRETORIO_PROJETO = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
CAMINHO_MASTER_USADO = DIRETORIO_PROJETO / "masterH_caso_base_minimo.dss"

PASTA_FASE2 = DIRETORIO_PROJETO / "metodologia" / "02_caso_base_harmonico"
PASTA_DADOS_BRUTOS = PASTA_FASE2 / "01_dados_brutos"
PASTA_MONITORES = PASTA_DADOS_BRUTOS / "monitores_csv"
PASTA_PROCESSADOS = PASTA_FASE2 / "02_processados"

for pasta in [PASTA_DADOS_BRUTOS, PASTA_MONITORES, PASTA_PROCESSADOS]:
    pasta.mkdir(parents=True, exist_ok=True)

ARQ_CADASTRO = PASTA_DADOS_BRUTOS / "cadastro_monitores_barras.csv"
ARQ_THDV = PASTA_PROCESSADOS / "THDv_barras_caso_base.csv"
ARQ_RESUMO = PASTA_PROCESSADOS / "resumo_thdv_caso_base.txt"

CSV_ENCODING = "latin-1"
CRIAR_MONITOR_PAC = True
CRIAR_MONITOR_SUBXF_REFERENCIA = True
MON_BUS_RE = re.compile(r"mon_bus_(\d+)", re.IGNORECASE)

# ordens explicitadas para evitar emissão residual/default
ORDENS = [1, 3, 5, 7, 9, 11, 13, 15]
TXT_HARM = " ".join(str(h) for h in ORDENS)
TXT_MAG_LIMPO = "100 " + " ".join("0" for _ in ORDENS[1:])
TXT_ANG_LIMPO = " ".join("0" for _ in ORDENS)


# ==============================================================================
# HELPERS
# ==============================================================================
def normalizar_bus(bus: str) -> str:
    return str(bus).split(".")[0].strip().upper()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


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


def limpar_csvs_monitor_em_pasta(pasta: Path) -> None:
    if not pasta.exists():
        return
    for arq in pasta.glob("*.csv"):
        try:
            arq.unlink()
        except Exception:
            pass


def limpar_exports_antigos_na_raiz() -> None:
    for arq in DIRETORIO_PROJETO.glob("*_Mon_*.csv"):
        try:
            arq.unlink()
        except Exception:
            pass


# ==============================================================================
# LIMPEZA EXPLÍCITA VIA PYTHON
# ==============================================================================
def criar_spectra_limpos(dss) -> None:
    dss.text(
        f"New Spectrum.FonteBaseLimpa NumHarm={len(ORDENS)} "
        f"harmonic=({TXT_HARM}) %mag=({TXT_MAG_LIMPO}) angle=({TXT_ANG_LIMPO})"
    )
    dss.text(
        f"New Spectrum.LoadClean NumHarm={len(ORDENS)} "
        f"harmonic=({TXT_HARM}) %mag=({TXT_MAG_LIMPO}) angle=({TXT_ANG_LIMPO})"
    )


def aplicar_fonte_limpa(dss) -> None:
    # tenta aplicar diretamente na fonte padrão do circuito
    dss.text("Edit Vsource.Source spectrum=FonteBaseLimpa")


def aplicar_cargas_limpas(dss) -> int:
    """
    Aplica explicitamente spectrum=LoadClean em todas as cargas do circuito.
    Retorna o número de cargas editadas.
    """
    try:
        nomes_cargas = list(dss.loads.names)
    except Exception:
        nomes_cargas = []

    editadas = 0
    for nome in nomes_cargas:
        try:
            dss.text(f"Edit Load.{nome} spectrum=LoadClean")
            editadas += 1
        except Exception:
            pass
    return editadas


def checar_propriedade_load(dss, nome: str, prop: str) -> str:
    try:
        return str(dss.text(f"? Load.{nome}.{prop}")).strip()
    except Exception:
        return "ERRO"


# ==============================================================================
# MONITORES
# ==============================================================================
def criar_monitor_se_nao_existir(dss, comando_new: str, nome_monitor: str) -> None:
    try:
        existentes = {str(m).upper() for m in list(dss.monitors.names) if m}
    except Exception:
        existentes = set()
    if nome_monitor.upper() not in existentes:
        dss.text(comando_new)


def criar_monitores_todas_barras_por_linha(dss) -> int:
    criados = 0
    try:
        linhas = list(dss.lines.names)
    except Exception:
        linhas = []

    for ln in linhas:
        dss.lines.name = ln
        b2 = normalizar_bus(dss.lines.bus2)
        if not b2:
            continue

        nome = f"MON_BUS_{b2}"
        try:
            existentes = {str(m).upper() for m in list(dss.monitors.names) if m}
        except Exception:
            existentes = set()

        if nome.upper() in existentes:
            continue

        dss.text(f"New Monitor.{nome} element=Line.{ln} terminal=2 mode=0 VIPolar=yes")
        criados += 1

    return criados


def criar_monitores(dss) -> int:
    if CRIAR_MONITOR_PAC:
        criar_monitor_se_nao_existir(
            dss,
            "New Monitor.MON_PAC element=Transformer.SubXF terminal=2 mode=0 VIPolar=yes",
            "MON_PAC",
        )

    if CRIAR_MONITOR_SUBXF_REFERENCIA:
        criar_monitor_se_nao_existir(
            dss,
            "New Monitor.MON_BUS10 element=Transformer.SubXF terminal=2 mode=0 VIPolar=yes",
            "MON_BUS10",
        )

    return criar_monitores_todas_barras_por_linha(dss)


def exportar_monitores(dss, pasta_destino: Path) -> int:
    pasta_destino.mkdir(parents=True, exist_ok=True)
    limpar_csvs_monitor_em_pasta(pasta_destino)
    limpar_exports_antigos_na_raiz()

    try:
        monitores = [m for m in list(dss.monitors.names) if m]
    except Exception:
        monitores = []

    exportados = 0
    for mon in monitores:
        dss.text(f"Export Monitors {mon}")

        candidatos = glob.glob(str(DIRETORIO_PROJETO / f"*_Mon_{mon}_*.csv"))
        if not candidatos:
            print(f"⚠️ CSV do monitor {mon} não encontrado.")
            continue

        candidatos.sort(key=os.path.getmtime, reverse=True)
        origem = Path(candidatos[0])
        destino = pasta_destino / origem.name

        if destino.exists():
            destino.unlink()

        shutil.move(str(origem), str(destino))
        exportados += 1

    return exportados


# ==============================================================================
# SOLUÇÃO ELÉTRICA
# ==============================================================================
def compilar_sistema(dss) -> None:
    dss.text("Clear")
    dss.text(f'Compile "{CAMINHO_MASTER_USADO}"')


def resolver_snapshot_e_harmonico(dss) -> None:
    dss.text("Set Mode=Snap")
    dss.text("Set ControlMode=Static")
    dss.text("Solve")
    if not dss.solution.converged:
        raise RuntimeError("O fluxo fundamental não convergiu.")

    dss.text("Set Mode=Harmonic")
    dss.text("Solve")
    if not dss.solution.converged:
        raise RuntimeError("A solução harmônica não convergiu.")


# ==============================================================================
# PÓS-PROCESSAMENTO
# ==============================================================================
def infer_monitor_type(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    m_bus = MON_BUS_RE.search(name)
    if m_bus:
        return "BUS", m_bus.group(1)
    if "mon_pac" in name:
        return "PAC", "PAC"
    if "mon_bus10" in name:
        return "REF", "BUS10"
    return "OUTRO", path.stem.upper()


def process_bus_file(path: Path) -> dict | None:
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    df = normalize_columns(df)

    if "Harmonic" not in df.columns:
        return None

    _, barra = infer_monitor_type(path)
    harm = df["Harmonic"]

    row: dict[str, object] = {"barra": barra, "arquivo": str(path)}
    thds = []
    for fase in [1, 2, 3]:
        col = f"V{fase}"
        if col in df.columns:
            thd = compute_thd_from_series(harm, df[col])
            row[f"THDv_fase{fase}_pct"] = thd
            thds.append(thd)
        else:
            row[f"THDv_fase{fase}_pct"] = math.nan

    validos = [x for x in thds if pd.notna(x)]
    row["THDv_max_pct"] = max(validos) if validos else math.nan
    row["THDv_med_pct"] = sum(validos) / len(validos) if validos else math.nan
    return row


def processar_thdv_barras(pasta_monitores: Path) -> pd.DataFrame:
    bus_rows = []
    for path in sorted(pasta_monitores.glob("*.csv")):
        tipo, _ = infer_monitor_type(path)
        if tipo == "BUS":
            row = process_bus_file(path)
            if row:
                bus_rows.append(row)

    if not bus_rows:
        raise RuntimeError("Nenhum monitor de barra válido foi processado.")

    df_bus = pd.DataFrame(bus_rows)
    df_bus["barra_num"] = pd.to_numeric(df_bus["barra"], errors="coerce")
    return df_bus.sort_values(["barra_num", "barra"]).drop(columns="barra_num").reset_index(drop=True)


def salvar_resumo(
    df_bus: pd.DataFrame,
    qtd_monitores_totais: int,
    qtd_monitores_exportados: int,
    qtd_cargas_editadas: int,
    exemplo_check: str,
) -> None:
    linhas = [
        "=== RESUMO - CASO BASE HARMÔNICO LIMPO (V6) ===",
        f"Master utilizado: {CAMINHO_MASTER_USADO}",
        f"Monitores planejados: {qtd_monitores_totais}",
        f"Monitores exportados: {qtd_monitores_exportados}",
        f"Barras processadas: {len(df_bus)}",
        f"Cargas editadas com spectrum limpo: {qtd_cargas_editadas}",
        f"Exemplo de checagem (? Load.carga_1.spectrum): {exemplo_check}",
    ]

    if df_bus["THDv_max_pct"].notna().any():
        maior = df_bus.loc[df_bus["THDv_max_pct"].idxmax()]
        media = float(df_bus["THDv_med_pct"].mean())
        linhas.append(f"THDv médio do sistema: {media:.6f} %")
        linhas.append(f"Maior THDv máximo: barra {maior['barra']} = {maior['THDv_max_pct']:.6f} %")
    else:
        linhas.append("Não foi possível calcular THDv do sistema.")

    linhas += [
        "",
        "Interpretação:",
        "- Caso base executado com fonte limpa e cargas explicitamente limpas via Python.",
        "- Esta mesma rotina deve ser mantida também nos cenários com PV, para garantir",
        "  que os harmônicos venham do PVSystem e não de emissão residual das cargas.",
    ]

    ARQ_RESUMO.write_text("\n".join(linhas), encoding="utf-8")


# ==============================================================================
# MAIN
# ==============================================================================
def main() -> None:
    print("=" * 100)
    print("FASE 2 - CASO BASE HARMÔNICO LIMPO (V6)")
    print("LIMPEZA EXPLÍCITA DAS CARGAS VIA PYTHON")
    print("=" * 100)
    print(f"Master utilizado: {CAMINHO_MASTER_USADO}")

    dss = py_dss_interface.DSS()
    compilar_sistema(dss)

    criar_spectra_limpos(dss)
    aplicar_fonte_limpa(dss)
    qtd_cargas_editadas = aplicar_cargas_limpas(dss)

    exemplo_check = checar_propriedade_load(dss, "carga_1", "spectrum")
    print(f"Cargas editadas com spectrum limpo: {qtd_cargas_editadas}")
    print(f"Checagem exemplo - Load.carga_1.spectrum = {exemplo_check}")

    qtd_barras_criadas = criar_monitores(dss)
    try:
        qtd_monitores_totais = len([m for m in list(dss.monitors.names) if m])
    except Exception:
        qtd_monitores_totais = 0

    print(f"Monitores de barras criados nesta compilação: {qtd_barras_criadas}")
    print(f"Monitores totais presentes no circuito: {qtd_monitores_totais}")

    cadastro = []
    for name in [m for m in list(dss.monitors.names) if m]:
        tipo, ident = infer_monitor_type(Path(str(name)))
        cadastro.append({"monitor": str(name), "tipo": tipo, "identificador": ident})
    pd.DataFrame(cadastro).to_csv(ARQ_CADASTRO, sep=";", decimal=",", index=False, encoding="utf-8-sig")

    resolver_snapshot_e_harmonico(dss)
    qtd_exportados = exportar_monitores(dss, PASTA_MONITORES)
    print(f"Monitores exportados: {qtd_exportados}")

    df_bus = processar_thdv_barras(PASTA_MONITORES)
    df_bus.to_csv(ARQ_THDV, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    salvar_resumo(df_bus, qtd_monitores_totais, qtd_exportados, qtd_cargas_editadas, exemplo_check)

    print("\nTop 10 barras por THDv máximo:")
    print(df_bus.sort_values("THDv_max_pct", ascending=False).head(10).to_string(index=False))

    print("\nArquivos gerados:")
    print(f"- {ARQ_CADASTRO}")
    print(f"- {ARQ_THDV}")
    print(f"- {ARQ_RESUMO}")
    print(f"- Pasta de monitores: {PASTA_MONITORES}")


if __name__ == "__main__":
    main()
