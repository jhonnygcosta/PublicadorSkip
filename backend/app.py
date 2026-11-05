"""
Publicador Skip: API local que a interface usa para agendar Reels.

O trabalho pesado (enviar, programar, conferir na Meta) fica em motor.py, que é
o Agendamento_API.py original. Aqui só organizamos as chamadas para a tela.

Rodar:  python -m uvicorn app:app --port 8765   (dentro de backend/)
"""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta

from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import motor

PASTA_FRONT = os.path.join(os.path.dirname(motor.PASTA_SCRIPT), "frontend", "dist")

app = FastAPI(title="Publicador Skip")


# CONTAS (uma por influenciador/página)
# Ficam em backend/contas.json: {"ativa": page_id, "contas": {page_id: {"nome", "token"}}}
ARQUIVO_CONTAS = os.path.join(motor.PASTA_SCRIPT, "contas.json")
trava_contas = threading.Lock()


def carregar_contas():
    if os.path.exists(ARQUIVO_CONTAS):
        with open(ARQUIVO_CONTAS, encoding="utf-8") as f:
            return json.load(f)

    # Primeira vez: traz a página que estava no .env (Diogo Defante)
    dados = {"ativa": None, "contas": {}}
    for env in (motor.ARQUIVO_ENV, os.path.join(os.path.dirname(motor.PASTA_SCRIPT), ".env")):
        if not os.path.exists(env):
            continue
        valores = {k: (v or "").strip() for k, v in dotenv_values(env).items()}
        pid, tok = valores.get("FB_PAGE_ID", ""), valores.get("FB_PAGE_TOKEN", "")
        if pid.isdigit() and tok.startswith("EAA"):
            try:
                nome = motor.conferir_pagina(pid, tok)
            except (SystemExit, motor.ErroAPI):
                nome = f"Página {pid}"
            dados = {"ativa": pid, "contas": {pid: {"nome": nome, "token": tok}}}
            salvar_contas(dados)
            break
    return dados


def salvar_contas(dados):
    temporario = ARQUIVO_CONTAS + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_CONTAS)


def ler_config(page_id=None):
    """Config da conta ativa (ou da pedida), no formato que o motor usa. None se não houver."""
    dados = carregar_contas()
    pid = page_id or dados.get("ativa")
    conta = dados["contas"].get(pid) if pid else None
    if not conta:
        return None
    return {"FB_PAGE_ID": pid, "FB_PAGE_TOKEN": conta["token"], "nome": conta["nome"]}


def nome_da_pagina(config):
    try:
        return motor.conferir_pagina(config["FB_PAGE_ID"], config["FB_PAGE_TOKEN"])
    except SystemExit as e:
        raise HTTPException(400, str(e.code))
    except motor.ErroAPI as e:
        raise HTTPException(400, f"A Meta recusou o token: {e}")


def resumo_contas():
    dados = carregar_contas()
    ativa = dados["contas"].get(dados.get("ativa") or "")
    lista = [{"pagina_id": pid, "nome": c["nome"]} for pid, c in dados["contas"].items()]
    if not ativa:
        return {"configurado": False, "contas": lista}
    return {"configurado": True, "pagina_id": dados["ativa"], "nome": ativa["nome"], "contas": lista}


def guardar_conta(page_id, nome, token, ativar=True):
    with trava_contas:
        dados = carregar_contas()
        dados["contas"][page_id] = {"nome": nome, "token": token}
        if ativar or not dados.get("ativa"):
            dados["ativa"] = page_id
        salvar_contas(dados)


class Conta(BaseModel):
    page_id: str
    token: str


class Escolha(BaseModel):
    pagina_id: str


class TrocaToken(BaseModel):
    app_id: str
    app_secret: str
    user_token: str


@app.get("/api/conta")
def conta():
    return resumo_contas()


@app.post("/api/conta")
def salvar_conta(dados: Conta):
    config = {"FB_PAGE_ID": dados.page_id.strip(), "FB_PAGE_TOKEN": dados.token.strip()}
    nome = nome_da_pagina(config)  # só grava se a Meta aceitar
    guardar_conta(config["FB_PAGE_ID"], nome, config["FB_PAGE_TOKEN"])
    return resumo_contas()


@app.post("/api/conta/ativa")
def escolher_conta(dados: Escolha):
    if tarefa and not tarefa.get("fim"):
        raise HTTPException(409, "Espere o envio em andamento terminar antes de trocar de influenciador.")
    with trava_contas:
        contas = carregar_contas()
        if dados.pagina_id not in contas["contas"]:
            raise HTTPException(404, "Conta não encontrada.")
        contas["ativa"] = dados.pagina_id
        salvar_contas(contas)
    return resumo_contas()


@app.post("/api/conta/remover")
def remover_conta(dados: Escolha):
    with trava_contas:
        contas = carregar_contas()
        contas["contas"].pop(dados.pagina_id, None)
        if contas.get("ativa") == dados.pagina_id:
            contas["ativa"] = next(iter(contas["contas"]), None)
        salvar_contas(contas)
    return resumo_contas()


@app.post("/api/gerar-token")
def gerar_token(dados: TrocaToken):
    """Token curto do Graph API Explorer -> token longo de usuário -> tokens permanentes das páginas."""
    try:
        resposta = motor.sessao.get(
            f"{motor.GRAPH}/{motor.VERSAO_API}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": dados.app_id.strip(),
                "client_secret": dados.app_secret.strip(),
                "fb_exchange_token": dados.user_token.strip(),
            },
            timeout=(15, 60),
        )
    except Exception as e:
        raise HTTPException(400, f"Falha de rede ({type(e).__name__})")

    corpo = motor.ler_json(resposta)
    if "access_token" not in corpo:
        raise HTTPException(400, f"A Meta recusou a troca: {motor.erro_da_resposta(resposta, corpo)}")

    try:
        paginas = motor.chamar(
            "GET", f"{motor.GRAPH}/{motor.VERSAO_API}/me/accounts", corpo["access_token"],
            params={"fields": "id,name,tasks,access_token", "limit": 100},
        ).get("data", [])
    except motor.ErroAPI as e:
        raise HTTPException(400, str(e))

    if not paginas:
        raise HTTPException(400, "Esse token não enxerga nenhuma página. Gere de novo marcando a página "
                                 "e as permissões pages_manage_posts, pages_read_engagement e business_management.")

    salvas, sem_permissao = [], []
    for p in paginas:
        if "CREATE_CONTENT" not in p.get("tasks", []):
            sem_permissao.append(p["name"])
            continue
        guardar_conta(p["id"], p["name"], p["access_token"], ativar=False)
        salvas.append({"pagina_id": p["id"], "nome": p["name"]})

    return {**resumo_contas(), "salvas": salvas, "sem_permissao": sem_permissao}


# PRÉVIA
class Agenda(BaseModel):
    pasta: str
    data: str | None = None  # AAAA-MM-DD (padrão: amanhã)
    hora: str = motor.hora_inicial
    intervalo: int = motor.intervalo_minutos
    por_dia: int = motor.videos_por_dia
    legenda: str = ""
    limite: int | None = None


def validar(agenda):
    if not os.path.isdir(agenda.pasta):
        raise HTTPException(400, "Pasta não encontrada.")
    if agenda.intervalo < 1 or agenda.por_dia < 1:
        raise HTTPException(400, "Intervalo e vídeos por dia precisam ser maiores que zero.")
    if (agenda.por_dia - 1) * agenda.intervalo >= 24 * 60:
        raise HTTPException(400, "Com esse intervalo os vídeos de um dia não cabem em 24h.")
    try:
        hora, minuto = map(int, agenda.hora.split(":"))
        dia = datetime.strptime(agenda.data, "%Y-%m-%d") if agenda.data else datetime.now() + timedelta(days=1)
        datetime(dia.year, dia.month, dia.day, hora, minuto)
    except ValueError:
        raise HTTPException(400, "Data ou hora inválida.")
    return dia, hora, minuto


def montar_previa(agenda):
    """Mesma análise do 'agendar --simular': o que entra, o que é pulado e por quê."""
    dia, hora, minuto = validar(agenda)
    arquivos = motor.listar_videos(agenda.pasta)
    plano = motor.montar_agenda(agenda.pasta, arquivos, dia, hora, minuto, agenda.intervalo, agenda.por_dia)

    historico = motor.carregar_historico()
    agora = datetime.now()
    pagina = (ler_config() or {}).get("FB_PAGE_ID")
    ocupados = {
        r.get("quando"): chave for chave, r in historico.items()
        if r.get("etapa") in ("enviado", "agendado") and r.get("pagina") == pagina
    }

    itens = []
    for caminho, quando in plano:
        chave = motor.chave_video(caminho)
        anterior = historico.get(chave) or {}
        if anterior.get("tamanho") != os.path.getsize(caminho):
            anterior = {}
        dono = ocupados.get(quando.isoformat(timespec="minutes"))

        entra, retomar = False, None
        if anterior.get("etapa") == "agendado":
            situacao = f"Já agendado para {datetime.fromisoformat(anterior['quando']):%d/%m %H:%M}"
        elif quando - agora < motor.ANTECEDENCIA_MINIMA:
            situacao = "Horário já passou"
        elif quando - agora > motor.ANTECEDENCIA_MAXIMA:
            situacao = "Além de 28 dias"
        elif dono and dono != chave:
            situacao = "Horário já ocupado"
        else:
            situacao = motor.problema_no_video(caminho)
            if not situacao:
                retomar = anterior.get("video_id") if anterior.get("etapa") == "enviado" else None
                situacao = "Retomar envio" if retomar else "Pronto"
                entra = True

        itens.append({
            "caminho": caminho,
            "arquivo": os.path.basename(caminho),
            "quando": quando.isoformat(timespec="minutes"),
            "situacao": situacao,
            "entra": entra,
            "retomar": retomar,
            "tamanho": os.path.getsize(caminho),
        })

    fila = [i for i in itens if i["entra"]]
    if agenda.limite:
        fila = fila[: agenda.limite]
    return itens, fila


@app.post("/api/previa")
def previa(agenda: Agenda):
    itens, fila = montar_previa(agenda)
    return {"itens": itens, "na_fila": len(fila), "limite_24h": motor.REELS_POR_24H}


# ENVIO EM SEGUNDO PLANO
tarefa = None
trava = threading.Lock()


class LeitorDaTela(motor.LeitorComProgresso):
    """Mesmo leitor do motor, mas avisa a tela em vez de imprimir."""

    def read(self, tamanho=-1):
        bloco = self.arquivo.read(tamanho)
        self.enviado += len(bloco)
        if tarefa and tarefa.get("atual") is not None:
            item = tarefa["itens"][tarefa["atual"]]
            item["progresso"] = round(self.enviado * 100 / self.total) if self.total else 100
        return bloco


motor.LeitorComProgresso = LeitorDaTela


def publicados_em_24h(historico, page_id, quando):
    """Reels programados para as 24h anteriores a `quando`.

    O motor conta pelo horário do ENVIO, mas em 24/10/2026 a Meta aceitou o 31º
    envio do dia: o limite de 30 vale para a publicação, não para o upload.
    """
    inicio = (quando - timedelta(hours=24)).isoformat(timespec="minutes")
    fim = quando.isoformat(timespec="minutes")
    return sum(
        1 for r in historico.values()
        if r.get("pagina") == page_id
        and r.get("etapa") == "agendado"
        and inicio < r.get("quando", "") <= fim
    )


def executar(fila, legenda_padrao, config):
    page_id, token = config["FB_PAGE_ID"], config["FB_PAGE_TOKEN"]
    historico = motor.carregar_historico()
    itens = tarefa["itens"]

    for posicao, item in enumerate(itens):
        if tarefa["parar"]:
            item.update(etapa="cancelado", detalhe="Parado por você")
            continue

        tarefa["atual"] = posicao
        caminho = item["caminho"]
        quando = datetime.fromisoformat(item["quando"])

        if publicados_em_24h(historico, page_id, quando) >= motor.REELS_POR_24H:
            item.update(etapa="limite", detalhe=f"Já há {motor.REELS_POR_24H} reels nas 24h antes deste horário")
            continue
        retomar = item["retomar"]

        if retomar:
            try:
                if motor.consultar_status(retomar, token).get("video_status") in ("expired", "error", "upload_failed"):
                    retomar = None
            except motor.ErroAPI:
                pass

        registro = {
            "arquivo": caminho,
            "tamanho": os.path.getsize(caminho),
            "quando": item["quando"],
            "pagina": page_id,
            "video_id": retomar,
            "etapa": "enviado" if retomar else "novo",
        }
        historico[motor.chave_video(caminho)] = registro

        try:
            legenda = motor.ler_legenda(caminho, legenda_padrao)
            if not retomar:
                item["etapa"] = "enviando"
                video_id, upload_url = motor.iniciar_envio(page_id, token)
                registro.update(video_id=video_id, etapa="iniciado")
                motor.salvar_historico(historico)

                motor.enviar_arquivo(upload_url, caminho, video_id, token)
                registro["etapa"] = "enviado"
                motor.salvar_historico(historico)

            item.update(etapa="programando", progresso=100)
            video_id = registro["video_id"]
            if not (retomar and motor.ja_programado(video_id, token)):
                motor.programar(page_id, video_id, quando, legenda, token)

            registro.update(etapa="agendado", criado_em=datetime.now().isoformat(timespec="seconds"))
            motor.salvar_historico(historico)
            item.update(etapa="processando", video_id=video_id, detalhe="Programado; a Meta está processando")

            # Confere os anteriores entre um envio e outro, para a tela ir confirmando junto
            conferir_uma_vez(historico, token)

        except (motor.ErroAPI, OSError) as erro:
            registro["erro"] = str(erro)
            motor.salvar_historico(historico)
            item.update(etapa="erro", detalhe=str(erro))

            if isinstance(erro, motor.ErroAPI) and (erro.limite or erro.acesso):
                motivo = "A Meta limitou as publicações" if erro.limite else "Token inválido ou sem permissão"
                for resto in itens[posicao + 1:]:
                    resto.update(etapa="cancelado", detalhe=motivo)
                break

    tarefa["atual"] = None
    conferir(historico, token)


def conferir_uma_vez(historico, token):
    """Pergunta à Meta, uma vez, como estão os reels ainda em processamento."""
    for item in [i for i in tarefa["itens"] if i["etapa"] == "processando"]:
        try:
            situacao, detalhe, horario = motor.resumir_status(motor.consultar_status(item["video_id"], token))
        except motor.ErroAPI as erro:
            if erro.passageiro:
                continue
            situacao, detalhe, horario = "erro", str(erro), None

        if situacao == "erro":
            registro = historico.get(motor.chave_video(item["caminho"]))
            if registro:
                registro.update(etapa="falhou", erro=detalhe)
                motor.salvar_historico(historico)
            item.update(etapa="erro", detalhe=detalhe)
        elif situacao == "ok":
            quando = datetime.fromisoformat(item["quando"])
            if horario and abs((horario - quando).total_seconds()) > 60:
                item.update(etapa="erro", detalhe=f"A Meta gravou {horario:%d/%m %H:%M}")
            else:
                item.update(etapa="confirmado", detalhe=f"Programado para {horario or quando:%d/%m %H:%M}")


def conferir(historico, token, espera=600):
    """Depois do último envio, segue conferindo até todos confirmarem (ou dar o tempo)."""
    tarefa["conferindo"] = True
    limite = time.time() + espera

    while time.time() < limite:
        conferir_uma_vez(historico, token)
        if not any(i["etapa"] == "processando" for i in tarefa["itens"]):
            break
        time.sleep(10)

    for item in tarefa["itens"]:
        if item["etapa"] == "processando":
            item["detalhe"] = "Ainda processando: confira depois em Agendados"
    tarefa.update(conferindo=False, fim=datetime.now().isoformat(timespec="seconds"))


@app.post("/api/agendar")
def agendar(agenda: Agenda):
    global tarefa
    config = ler_config()
    if not config:
        raise HTTPException(400, "Configure a página e o token primeiro.")

    with trava:
        if tarefa and not tarefa.get("fim"):
            raise HTTPException(409, "Já existe um envio em andamento.")

        _, fila = montar_previa(agenda)
        if not fila:
            raise HTTPException(400, "Nenhum vídeo pronto para agendar.")

        tarefa = {
            "id": uuid.uuid4().hex[:8],
            "inicio": datetime.now().isoformat(timespec="seconds"),
            "fim": None,
            "parar": False,
            "atual": None,
            "conferindo": False,
            "itens": [
                {**i, "etapa": "na fila", "progresso": 0, "detalhe": "", "video_id": None}
                for i in fila
            ],
        }

    def rodar():
        try:
            executar(fila, agenda.legenda, config)
        except Exception as erro:  # nunca deixa a tarefa "rodando" para sempre
            tarefa.update(erro=str(erro), fim=datetime.now().isoformat(timespec="seconds"))

    threading.Thread(target=rodar, daemon=True).start()
    return tarefa


@app.get("/api/tarefa")
def ver_tarefa():
    return tarefa


@app.post("/api/tarefa/parar")
def parar_tarefa():
    if tarefa and not tarefa.get("fim"):
        tarefa["parar"] = True
    return tarefa


# AGENDADOS
@app.get("/api/agendados")
def agendados(conferir_meta: bool = False, todos: bool = False):
    historico = motor.carregar_historico()
    agora = datetime.now().isoformat(timespec="minutes")
    ativa = ler_config()
    config = ativa if conferir_meta else None
    pagina = (ativa or {}).get("FB_PAGE_ID")

    lista = []
    for r in historico.values():
        if r.get("pagina") != pagina:
            continue
        if not r.get("video_id") or r.get("etapa") not in ("agendado", "falhou", "cancelado"):
            continue
        if not todos and r.get("quando", "") < agora:
            continue

        item = {
            "video_id": r["video_id"],
            "arquivo": os.path.basename(r.get("arquivo", "")),
            "quando": r.get("quando"),
            "etapa": r.get("etapa"),
            "detalhe": r.get("erro", ""),
        }
        if config and r.get("etapa") == "agendado":
            try:
                situacao, detalhe, _ = motor.resumir_status(motor.consultar_status(r["video_id"], config["FB_PAGE_TOKEN"]))
                item.update(meta=situacao, detalhe=detalhe)
            except motor.ErroAPI as erro:
                item.update(meta="sem resposta", detalhe=str(erro))
        lista.append(item)

    return sorted(lista, key=lambda i: i["quando"] or "")


@app.post("/api/cancelar/{video_id}")
def cancelar(video_id: str):
    config = ler_config()
    if not config:
        raise HTTPException(400, "Configure a página e o token primeiro.")
    try:
        motor.chamar("DELETE", f"{motor.GRAPH}/{motor.VERSAO_API}/{video_id}", config["FB_PAGE_TOKEN"])
    except motor.ErroAPI as erro:
        raise HTTPException(400, str(erro))

    historico = motor.carregar_historico()
    for registro in historico.values():
        if registro.get("video_id") == video_id:
            registro["etapa"] = "cancelado"
    motor.salvar_historico(historico)
    return {"ok": True}


# ESCOLHER PASTA (janela do Windows; só funciona com o servidor no próprio PC)
@app.post("/api/escolher-pasta")
def escolher_pasta():
    codigo = (
        "import tkinter as tk; from tkinter import filedialog; r = tk.Tk(); r.withdraw(); "
        "r.attributes('-topmost', True); print(filedialog.askdirectory(title='Pasta dos vídeos') or '')"
    )
    # O filho escreve em UTF-8 de propósito: no Windows o padrão é cp1252 e quebra pastas com acento
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    resultado = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, env=ambiente,
    )
    saida = (resultado.stdout or b"").decode("utf-8", errors="replace").strip()
    if resultado.returncode != 0 and not saida:
        erro = (resultado.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        raise HTTPException(500, f"Não consegui abrir a janela de pastas: {erro[-1] if erro else 'erro desconhecido'}")
    return {"pasta": os.path.normpath(saida) if saida else None}


# INTERFACE (build do frontend)
if os.path.isdir(PASTA_FRONT):
    app.mount("/assets", StaticFiles(directory=os.path.join(PASTA_FRONT, "assets")), name="assets")

    @app.get("/{caminho:path}")
    def interface(caminho: str):
        arquivo = os.path.join(PASTA_FRONT, caminho)
        if caminho and os.path.isfile(arquivo):
            return FileResponse(arquivo)
        return FileResponse(os.path.join(PASTA_FRONT, "index.html"))
