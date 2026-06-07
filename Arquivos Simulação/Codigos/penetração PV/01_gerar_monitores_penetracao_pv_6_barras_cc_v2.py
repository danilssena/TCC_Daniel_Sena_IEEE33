# -*- coding: utf-8 -*-
r"""
01_gerar_monitores_penetracao_pv_6_barras_cc_v1.py

Cenários com penetração fotovoltaica simplificados para o TCC:
- seleção de 6 barras a partir do estudo de curto-circuito;
- monitores em TODAS as barras do alimentador;
- PV inserido APENAS nas 6 barras selecionadas;
- divisão IGUAL da potência total FV entre as 6 barras;
- cargas harmonicamente limpas via Python;
- harmônicos vindos apenas dos inversores FV.

Critério elétrico adotado:
- usar as 6 barras de carga com MENOR corrente de curto-circuito trifásica
  (ALL-Node Fault Currents), por serem eletricamente mais fracas e,
  portanto, mais sensíveis à amplificação de distorções harmônicas.

Barras selecionadas:
- 130, 140, 150, 160, 170, 180

Correntes de curto-circuito trifásico (A):
- 130 -> 764
- 140 -> 704
- 150 -> 656
- 160 -> 608
- 170 -> 521
- 180 -> 490

Saídas:
D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final\metodologia\03_penetracao_pv\
    01_dados_brutos_monitores\
        PEN_100\
        PEN_120\
        PEN_150\
"""

from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

import pandas as pd
import py_dss_interface

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
DIRETORIO_PROJETO = Path(r"D:\Notebook\TCC\MTcc\IEEE33\IEEE_Final")
CAMINHO_MASTER = DIRETORIO_PROJETO / "masterH_caso_base_minimo.dss"

PASTA_METODOLOGIA = DIRETORIO_PROJETO / "metodologia"
PASTA_ETAPA = PASTA_METODOLOGIA / "03_penetracao_pv"
PASTA_DADOS_BRUTOS = PASTA_ETAPA / "01_dados_brutos_monitores"

PENETRACOES = [1.00, 1.20, 1.50]
P_BASE_PENETRACAO_KW = 3000.0
KVA_PMPP_RATIO = 1.10

BARRAS_PV = ["130", "140", "150", "160", "170", "180"]

ICC_TRIFASICO_A = {
    "130": 764.0,
    "140": 704.0,
    "150": 656.0,
    "160": 608.0,
    "170": 521.0,
    "180": 490.0,
}

ORDENS = [1, 3, 5, 7, 9, 11, 13, 15]
TXT_HARM = " ".join(str(h) for h in ORDENS)
TXT_MAG_LIMPO = "100 " + " ".join("0" for _ in ORDENS[1:])
TXT_ANG_LIMPO = " ".join("0" for _ in ORDENS)
TXT_MAG_PV = "100 3.28 4.65 5.99 1.70 1.67 1.55 0.91"
TXT_ANG_PV = "0 83.68 61.05 270.97 111.93 351.06 234.97 168.24"

CRIAR_MONITOR_PAC = True
CRIAR_MONITOR_SUBXF_REFERENCIA = True


# ==============================================================================
# HELPERS
# ==============================================================================
def normalizar_bus(bus: str) -> str:
    return str(bus).split(".")[0].strip().upper()


def limpar_csvs_monitor_em_pasta(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
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


def criar_monitor_se_nao_existir(dss, comando_new: str, nome_monitor: str) -> None:
    try:
        existentes = {str(m).upper() for m in list(dss.monitors.names) if m}
    except Exception:
        existentes = set()
    if nome_monitor.upper() not in existentes:
        dss.text(comando_new)


# ==============================================================================
# PREPARAÇÃO DO CIRCUITO
# ==============================================================================
def compilar_sistema(dss) -> None:
    dss.text("Clear")
    dss.text(f'Compile "{CAMINHO_MASTER}"')


def criar_spectra(dss) -> None:
    dss.text(
        f"New Spectrum.FonteBaseLimpa NumHarm={len(ORDENS)} "
        f"harmonic=({TXT_HARM}) %mag=({TXT_MAG_LIMPO}) angle=({TXT_ANG_LIMPO})"
    )
    dss.text(
        f"New Spectrum.LoadClean NumHarm={len(ORDENS)} "
        f"harmonic=({TXT_HARM}) %mag=({TXT_MAG_LIMPO}) angle=({TXT_ANG_LIMPO})"
    )
    dss.text(
        f"New Spectrum.PV_INV NumHarm={len(ORDENS)} "
        f"harmonic=({TXT_HARM}) %mag=({TXT_MAG_PV}) angle=({TXT_ANG_PV})"
    )


def aplicar_limpeza(dss) -> int:
    dss.text("Edit Vsource.Source spectrum=FonteBaseLimpa")
    editadas = 0
    try:
        nomes_cargas = [n for n in list(dss.loads.names) if n]
    except Exception:
        nomes_cargas = []

    for nome in nomes_cargas:
        try:
            dss.text(f"Edit Load.{nome} spectrum=LoadClean")
            editadas += 1
        except Exception:
            pass
    return editadas


# ==============================================================================
# CRIAÇÃO DOS PVs NAS 6 BARRAS SELECIONADAS
# ==============================================================================
def criar_pvs_6_barras(dss, penetracao: float) -> tuple[pd.DataFrame, float, float, float]:
    pv_total_kw = P_BASE_PENETRACAO_KW * penetracao
    n = len(BARRAS_PV)
    if n == 0:
        raise RuntimeError("Nenhuma barra FV foi definida.")

    pmpp_por_pv = pv_total_kw / n
    kva_por_pv = pmpp_por_pv * KVA_PMPP_RATIO

    registros = []
    for bus in BARRAS_PV:
        trafo = f"TR_PV_{bus}"
        bus_pv = f"BUS_PV_{bus}"
        pv = f"PV_{bus}"

        dss.text(f"New Transformer.{trafo} phases=3 windings=2 xhl=5.75")
        dss.text(f"~ wdg=1 bus={bus} conn=wye kv=13.8 kVA={kva_por_pv:.6f}")
        dss.text(f"~ wdg=2 bus={bus_pv} conn=wye kv=0.22 kVA={kva_por_pv:.6f}")

        dss.text(f"New PVSystem.{pv} phases=3 bus1={bus_pv} kv=0.22")
        dss.text(f"~ pmpp={pmpp_por_pv:.6f} kVA={kva_por_pv:.6f} pf=1")
        dss.text("~ spectrum=PV_INV")

        registros.append({
            "bus": bus,
            "icc_trifasico_a": ICC_TRIFASICO_A.get(bus, float("nan")),
            "pmpp_kw": pmpp_por_pv,
            "kva": kva_por_pv,
        })

    df_pv = pd.DataFrame(registros)
    return df_pv, pv_total_kw, pmpp_por_pv, kva_por_pv


# ==============================================================================
# MONITORES
# ==============================================================================
def criar_monitores_todas_barras_por_linha(dss) -> int:
    criados = 0
    try:
        linhas = [ln for ln in list(dss.lines.names) if ln]
    except Exception:
        linhas = []

    for ln in linhas:
        dss.lines.name = ln
        b2 = normalizar_bus(getattr(dss.lines, "bus2", ""))
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


def criar_monitores_pvs(dss, df_pv: pd.DataFrame) -> int:
    criados = 0
    for _, row in df_pv.iterrows():
        bus = str(row["bus"])
        nome = f"MON_PV_{bus}"
        try:
            existentes = {str(m).upper() for m in list(dss.monitors.names) if m}
        except Exception:
            existentes = set()

        if nome.upper() in existentes:
            continue

        dss.text(f"New Monitor.{nome} element=PVSystem.PV_{bus} terminal=1 mode=0 VIPolar=yes")
        criados += 1

    return criados


def criar_monitores(dss, df_pv: pd.DataFrame) -> tuple[int, int]:
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

    qtd_barras = criar_monitores_todas_barras_por_linha(dss)
    qtd_pvs = criar_monitores_pvs(dss, df_pv)
    return qtd_barras, qtd_pvs


# ==============================================================================
# SOLUÇÃO / EXPORTAÇÃO
# ==============================================================================
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


def exportar_monitores(dss, pasta_destino: Path) -> int:
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
# RESUMO
# ==============================================================================
def salvar_resumo(
    pasta_destino: Path,
    penetracao: float,
    qtd_cargas_editadas: int,
    df_pv: pd.DataFrame,
    qtd_monitores_barras: int,
    qtd_monitores_pv: int,
    qtd_exportados: int,
    pv_total_kw: float,
    pmpp_por_pv: float,
    kva_por_pv: float,
) -> None:
    pen_tag = f"PEN_{int(round(penetracao * 100))}"
    resumo = pasta_destino / "resumo_execucao.txt"
    alocacao = pasta_destino / "alocacao_pv_por_barra.csv"

    df_pv.to_csv(alocacao, sep=";", decimal=",", index=False, encoding="utf-8-sig")

    linhas = [
        f"=== RESUMO DA EXECUÇÃO - {pen_tag} ===",
        f"Master utilizado: {CAMINHO_MASTER}",
        f"Cargas limpas via Python: {qtd_cargas_editadas}",
        f"Barras com PV criado: {len(df_pv)}",
        f"Potência total FV: {pv_total_kw:.6f} kW",
        f"PMpp por barra FV: {pmpp_por_pv:.6f} kW",
        f"kVA por barra FV: {kva_por_pv:.6f} kVA",
        f"Monitores de barras criados: {qtd_monitores_barras}",
        f"Monitores de PV criados: {qtd_monitores_pv}",
        f"Monitores exportados: {qtd_exportados}",
        "",
        "Critério de seleção das barras FV:",
        "- seleção das 6 barras de carga com menor corrente de curto-circuito trifásica;",
        "- barras escolhidas: 130, 140, 150, 160, 170 e 180;",
        "- divisão igual da potência total FV entre as 6 barras;",
        "- cargas mantidas harmonicamente limpas via Python;",
        "- harmônicos associados apenas aos inversores FV.",
    ]
    resumo.write_text("\n".join(linhas), encoding="utf-8")


# ==============================================================================
# EXECUÇÃO
# ==============================================================================
def rodar_um_caso(dss, penetracao: float) -> None:
    pen_tag = f"PEN_{int(round(penetracao * 100))}"
    pasta_destino = PASTA_DADOS_BRUTOS / pen_tag

    print("\n" + "=" * 100)
    print(f"RODANDO {pen_tag}")
    print("=" * 100)

    compilar_sistema(dss)
    criar_spectra(dss)
    qtd_cargas_editadas = aplicar_limpeza(dss)

    print(f"Cargas limpas via Python: {qtd_cargas_editadas}")
    print(f"Barras FV selecionadas  : {BARRAS_PV}")

    df_pv, pv_total_kw, pmpp_por_pv, kva_por_pv = criar_pvs_6_barras(dss, penetracao)
    print(f"Potência total FV aplicada: {pv_total_kw:.3f} kW")
    print(f"PMpp por barra FV        : {pmpp_por_pv:.3f} kW")
    print(f"kVA por barra FV         : {kva_por_pv:.3f} kVA")

    qtd_monitores_barras, qtd_monitores_pv = criar_monitores(dss, df_pv)
    print(f"Monitores de barras criados: {qtd_monitores_barras}")
    print(f"Monitores de PV criados    : {qtd_monitores_pv}")

    resolver_snapshot_e_harmonico(dss)
    qtd_exportados = exportar_monitores(dss, pasta_destino)
    print(f"Monitores exportados       : {qtd_exportados}")

    salvar_resumo(
        pasta_destino=pasta_destino,
        penetracao=penetracao,
        qtd_cargas_editadas=qtd_cargas_editadas,
        df_pv=df_pv,
        qtd_monitores_barras=qtd_monitores_barras,
        qtd_monitores_pv=qtd_monitores_pv,
        qtd_exportados=qtd_exportados,
        pv_total_kw=pv_total_kw,
        pmpp_por_pv=pmpp_por_pv,
        kva_por_pv=kva_por_pv,
    )


def main() -> None:
    print("=" * 100)
    print("01_gerar_monitores_penetracao_pv_6_barras_cc_v1.py")
    print("PVs EM 6 BARRAS FRACAS PELO CURTO-CIRCUITO | PEN 100 / 120 / 150")
    print("=" * 100)
    print(f"Projeto      : {DIRETORIO_PROJETO}")
    print(f"Master       : {CAMINHO_MASTER}")
    print(f"Metodologia  : {PASTA_METODOLOGIA}")
    print(f"Saída bruta  : {PASTA_DADOS_BRUTOS}")
    print(f"Barras FV    : {BARRAS_PV}")

    PASTA_DADOS_BRUTOS.mkdir(parents=True, exist_ok=True)

    dss = py_dss_interface.DSS()
    for pen in PENETRACOES:
        rodar_um_caso(dss, pen)

    print("\nConcluído com sucesso.")
    print("Próxima etapa: processar THDv/THDi dos monitores exportados.")


if __name__ == "__main__":
    main()
