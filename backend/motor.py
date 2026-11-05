"""
Agendamento de Reels pela Graph API da Meta (sem navegador e sem cliques).

Substitui o fluxo de PyAutoGUI: cada .mp4 vai direto para a Página e já fica
programado, em 3 chamadas por vídeo (iniciar -> enviar -> programar).

Uso:
    python Agendamento_API.py verificar
    python Agendamento_API.py agendar --pasta "E:\\Cortes" --data 14/10/2026 --hora 08:30
    python Agendamento_API.py agendar --pasta "E:\\Cortes" --simular
    python Agendamento_API.py status
    python Agendamento_API.py cancelar ID_DO_VIDEO

Configuração (uma vez só): copie ".env.exemplo" para ".env" e preencha.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

import requests
from dotenv import dotenv_values, set_key

# CONFIGURAÇÕES
PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ENV = os.path.join(PASTA_SCRIPT, ".env")
ARQUIVO_HISTORICO = os.path.join(PASTA_SCRIPT, "historico_api.json")

VERSAO_API = "v26.0"
GRAPH = "https://graph.facebook.com"

videos_por_dia = 10
hora_inicial = "10:00"
intervalo_minutos = 60

# LIMITES DA META (guia "Reels Publishing")
ANTECEDENCIA_MINIMA = timedelta(minutes=15)  # a API exige mais de 10 min
ANTECEDENCIA_MAXIMA = timedelta(days=28)  # a API aceita até 29 dias
REELS_POR_24H = 30
DURACAO_REEL = (3, 90)  # segundos
FPS_REEL = (24, 60)

FASES = ("uploading_phase", "processing_phase", "publishing_phase")
# A documentação usa as duas grafias
CONCLUIDO = ("complete", "completed")

CODIGOS_PASSAGEIROS = {1, 2}
CODIGOS_LIMITE = {4, 17, 32, 341, 613, 80001}
# Token inválido ou sem permissão: não adianta tentar o próximo vídeo
CODIGOS_ACESSO = {10, 190, 200, 368}

sessao = requests.Session()


class ErroAPI(Exception):
    def __init__(self, mensagem, codigo=None, passageiro=False):
        super().__init__(mensagem)
        self.codigo = codigo
        self.passageiro = passageiro

    @property
    def limite(self):
        return self.codigo in CODIGOS_LIMITE

    @property
    def acesso(self):
        return self.codigo in CODIGOS_ACESSO


# CONFIGURAÇÃO E HISTÓRICO
def carregar_config(exigir_pagina=True):
    if not os.path.exists(ARQUIVO_ENV):
        sys.exit(f"⚠️ Não achei {ARQUIVO_ENV}. Copie .env.exemplo para .env e preencha.")

    config = {k: (v or "").strip() for k, v in dotenv_values(ARQUIVO_ENV).items()}

    if exigir_pagina:
        faltando = [k for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN") if not config.get(k)]
        if faltando:
            sys.exit(f"⚠️ Faltando no .env: {', '.join(faltando)}")

    return config


def carregar_historico():
    if not os.path.exists(ARQUIVO_HISTORICO):
        return {}
    try:
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            historico = json.load(f)
    except (OSError, ValueError):
        historico = None
    if not isinstance(historico, dict):
        # Sem histórico confiável não dá para saber o que já foi agendado
        sys.exit(f"⚠️ {ARQUIVO_HISTORICO} está ilegível. Corrija ou renomeie o arquivo antes de agendar.")
    return historico


def salvar_historico(historico):
    temporario = ARQUIVO_HISTORICO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_HISTORICO)


def chave_video(caminho):
    return os.path.normcase(os.path.abspath(caminho))


def agendados_nas_ultimas_24h(historico, page_id):
    corte = (datetime.now() - timedelta(hours=24)).isoformat()
    return sum(
        1 for r in historico.values()
        if r.get("pagina") == page_id
        and r.get("etapa") == "agendado"
        and r.get("criado_em", "") >= corte
    )


# CHAMADAS À API
def ler_json(resposta):
    try:
        corpo = resposta.json()
    except ValueError:
        return {}
    return corpo if isinstance(corpo, dict) else {}


def erro_da_resposta(resposta, corpo):
    erro = corpo.get("error") or {}
    info = corpo.get("debug_info") or {}

    mensagem = (
        erro.get("error_user_msg")
        or erro.get("message")
        or info.get("message")
        or f"HTTP {resposta.status_code}"
    )
    codigo = erro.get("code")
    passageiro = (
        resposta.status_code >= 500
        or codigo in CODIGOS_PASSAGEIROS
        or bool(erro.get("is_transient"))
        or bool(info.get("retriable"))
    )

    if codigo is not None:
        mensagem = f"{mensagem} (código {codigo}/{erro.get('error_subcode', '-')})"

    return ErroAPI(mensagem, codigo, passageiro)


def chamar(metodo, url, token, dados=None, params=None, tentativas=3):
    """Chama a Graph API, repetindo sozinho quando a falha é passageira."""
    # O token vai no corpo (POST) ou no cabeçalho, nunca na URL, para não
    # aparecer em mensagens de erro nem em logs.
    cabecalhos = {}
    if metodo == "POST":
        dados = dict(dados or {}, access_token=token)
    else:
        cabecalhos["Authorization"] = f"Bearer {token}"

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = sessao.request(
                metodo, url, params=params, data=dados, headers=cabecalhos, timeout=(15, 120)
            )
        except requests.RequestException as e:
            erro = ErroAPI(f"falha de rede ({type(e).__name__})", passageiro=True)
        else:
            corpo = ler_json(resposta)
            if resposta.ok and "error" not in corpo:
                return corpo
            erro = erro_da_resposta(resposta, corpo)

        if not erro.passageiro or tentativa == tentativas:
            raise erro

        time.sleep(5 * tentativa)


def conferir_pagina(page_id, token):
    """Garante que o token é mesmo da página do .env e devolve o nome dela."""
    eu = chamar("GET", f"{GRAPH}/{VERSAO_API}/me", token, params={"fields": "id,name"})

    if eu.get("id") != page_id:
        sys.exit(
            f"⚠️ O token é de '{eu.get('name')}' (id {eu.get('id')}), mas FB_PAGE_ID é "
            f"{page_id}. Use o token da PÁGINA, não o do seu perfil."
        )

    return eu.get("name")


def consultar_status(video_id, token):
    corpo = chamar(
        "GET", f"{GRAPH}/{VERSAO_API}/{video_id}", token, params={"fields": "status"}
    )
    return corpo.get("status") or {}


def descrever_erros(erros):
    if isinstance(erros, dict):
        erros = [erros]
    if isinstance(erros, list):
        return "; ".join(
            str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in erros
        )
    return str(erros or "erro")


def para_datetime(valor):
    """publish_time da Meta (timestamp ou texto ISO) -> horário local."""
    if not valor:
        return None
    try:
        return datetime.fromtimestamp(int(valor))
    except (TypeError, ValueError, OSError):
        pass
    try:
        instante = datetime.strptime(str(valor), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return instante.astimezone().replace(tzinfo=None)


def resumir_status(status):
    """Devolve (situacao, detalhe, horario); situacao é 'ok', 'processando' ou 'erro'."""
    for nome in FASES:
        fase = status.get(nome) or {}
        erros = fase.get("errors") or fase.get("error")
        if fase.get("status") == "error" or erros:
            return "erro", f"{nome}: {descrever_erros(erros)}", None

    if status.get("video_status") in ("error", "expired", "upload_failed"):
        return "erro", f"vídeo {status['video_status']}", None

    publicacao = status.get("publishing_phase") or {}
    estado = (publicacao.get("publish_status") or "").lower()
    horario = para_datetime(publicacao.get("publish_time"))
    processado = (status.get("processing_phase") or {}).get("status") in CONCLUIDO

    if estado == "error":
        return "erro", "a Meta recusou a publicação", None

    if processado and estado in ("scheduled", "published"):
        return "ok", estado, horario

    if processado and estado == "draft":
        return "erro", "ficou como rascunho, não como programado", None

    return "processando", estado or status.get("video_status") or "aguardando", horario


# ENVIO
class LeitorComProgresso:
    """Entrega o arquivo em blocos para o requests e mostra o andamento."""

    def __init__(self, caminho, inicio=0):
        self.total = os.path.getsize(caminho)
        self.restante = self.total - inicio
        self.enviado = inicio
        self.ultimo_aviso = -1
        self.arquivo = open(caminho, "rb")
        self.arquivo.seek(inicio)

    def __len__(self):
        # O requests usa isso para mandar Content-Length em vez de chunked
        return self.restante

    def __iter__(self):
        return iter(lambda: self.read(1024 * 1024), b"")

    def read(self, tamanho=-1):
        bloco = self.arquivo.read(tamanho)
        self.enviado += len(bloco)

        dezena = int(self.enviado * 10 / self.total) if self.total else 10
        if dezena != self.ultimo_aviso:
            self.ultimo_aviso = dezena
            print(f"      {dezena * 10:3d}%", end="\r", flush=True)

        return bloco

    def close(self):
        self.arquivo.close()


def iniciar_envio(page_id, token):
    corpo = chamar(
        "POST",
        f"{GRAPH}/{VERSAO_API}/{page_id}/video_reels",
        token,
        dados={"upload_phase": "start"},
    )
    return corpo["video_id"], corpo["upload_url"]


def enviar_arquivo(upload_url, caminho, video_id, token, tentativas=4):
    tamanho = os.path.getsize(caminho)
    inicio = 0

    for tentativa in range(1, tentativas + 1):
        leitor = LeitorComProgresso(caminho, inicio)
        try:
            resposta = sessao.post(
                upload_url,
                data=leitor,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": str(inicio),
                    "file_size": str(tamanho),
                    "Content-Type": "application/octet-stream",
                },
                timeout=(15, 900),
            )
        except requests.RequestException as e:
            erro = ErroAPI(f"falha de rede no envio ({type(e).__name__})", passageiro=True)
        else:
            corpo = ler_json(resposta)
            if resposta.ok and corpo.get("success"):
                return
            erro = erro_da_resposta(resposta, corpo)
        finally:
            leitor.close()

        if not erro.passageiro or tentativa == tentativas:
            raise erro

        print(f"      ⚠️ {erro} - retomando ({tentativa}/{tentativas - 1})...")
        time.sleep(5 * tentativa)

        # Retoma de onde a Meta parou de receber, em vez de reenviar tudo
        # ("bytes_transfered" é a grafia da própria API)
        try:
            fase = consultar_status(video_id, token).get("uploading_phase") or {}
            inicio = int(fase.get("bytes_transfered") or 0)
        except (ErroAPI, ValueError):
            inicio = 0

        if inicio >= tamanho:
            return


def programar(page_id, video_id, quando, legenda, token):
    dados = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "SCHEDULED",
        # Horário do Windows convertido para timestamp (segundos, UTC)
        "scheduled_publish_time": int(quando.timestamp()),
    }
    if legenda:
        dados["description"] = legenda

    try:
        chamar(
            "POST",
            f"{GRAPH}/{VERSAO_API}/{page_id}/video_reels",
            token,
            dados=dados,
            tentativas=1,
        )
    except ErroAPI as erro:
        # A resposta pode ter se perdido com o reel já programado: confere
        # antes de desistir, para não agendar o mesmo vídeo duas vezes.
        if erro.passageiro and ja_programado(video_id, token):
            return
        raise


def ja_programado(video_id, token):
    try:
        fase = consultar_status(video_id, token).get("publishing_phase") or {}
    except ErroAPI:
        return False
    return (fase.get("publish_status") or "").lower() in ("scheduled", "published")


# AGENDA
def ordem_natural(nome):
    # clip_2 antes de clip_10 (o sorted() puro coloca clip_10 primeiro)
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", nome)]


def listar_videos(pasta):
    return sorted(
        (f for f in os.listdir(pasta) if f.lower().endswith(".mp4")),
        key=ordem_natural,
    )


def interpretar_data(texto):
    if not texto:
        return datetime.now() + timedelta(days=1)

    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass

    sys.exit("⚠️ Data inválida. Use, por exemplo, 21/09/2026.")


def interpretar_hora(texto):
    try:
        hora = datetime.strptime(texto, "%H:%M")
    except ValueError:
        sys.exit("⚠️ Hora inválida. Use, por exemplo, 08:30.")
    return hora.hour, hora.minute


def montar_agenda(pasta, arquivos, data, hora, minuto, intervalo, por_dia):
    agenda = []

    for indice, nome in enumerate(arquivos):
        dia = data + timedelta(days=indice // por_dia)
        primeiro = datetime(dia.year, dia.month, dia.day, hora, minuto)
        quando = primeiro + timedelta(minutes=intervalo * (indice % por_dia))
        agenda.append((os.path.join(pasta, nome), quando))

    return agenda


def problema_no_video(caminho):
    """Motivo de a API recusar o vídeo como Reel, ou None se estiver ok."""
    if not shutil.which("ffprobe"):
        return None

    try:
        saida = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                "-of", "json", caminho,
            ],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        ).stdout
        dados = json.loads(saida)
        video = dados["streams"][0]
        duracao = float(dados["format"]["duration"])
        numerador, denominador = video["r_frame_rate"].split("/")
        fps = float(numerador) / float(denominador)
        lados = sorted((int(video["width"]), int(video["height"])))
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError, subprocess.SubprocessError):
        # Sem leitura confiável, deixa a própria Meta validar
        return None

    if not DURACAO_REEL[0] <= duracao <= DURACAO_REEL[1]:
        return f"duração {duracao:.0f}s (3 a 90s)"
    if not FPS_REEL[0] <= round(fps) <= FPS_REEL[1]:
        return f"{fps:.0f} fps (24 a 60)"
    if lados[0] < 540 or lados[1] < 960:
        return f"{video['width']}x{video['height']} (mín. 540x960)"

    return None


def ler_legenda(caminho, legenda_padrao):
    """Legenda do vídeo: um .txt com o mesmo nome ganha da legenda padrão."""
    arquivo_txt = os.path.splitext(caminho)[0] + ".txt"
    if os.path.exists(arquivo_txt):
        with open(arquivo_txt, "rb") as f:
            bruto = f.read()
        try:
            return bruto.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            return bruto.decode("cp1252", errors="replace").strip()
    return legenda_padrao


# COMANDOS
def comando_verificar(args):
    config = carregar_config()
    token = config["FB_PAGE_TOKEN"]

    nome = conferir_pagina(config["FB_PAGE_ID"], token)
    print(f"✅ Token válido para a página: {nome} ({config['FB_PAGE_ID']})")

    print("   Validade e permissões: confira em developers.facebook.com/tools/debug/accesstoken")


def comando_token(args):
    """Troca o token curto do Graph API Explorer pelo token longo da Página."""
    config = carregar_config(exigir_pagina=False)

    faltando = [k for k in ("FB_APP_ID", "FB_APP_SECRET", "FB_USER_TOKEN") if not config.get(k)]
    if faltando:
        sys.exit(f"⚠️ Faltando no .env: {', '.join(faltando)}")

    try:
        resposta = sessao.get(
            f"{GRAPH}/{VERSAO_API}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": config["FB_APP_ID"],
                "client_secret": config["FB_APP_SECRET"],
                "fb_exchange_token": config["FB_USER_TOKEN"],
            },
            timeout=(15, 60),
        )
    except requests.RequestException as e:
        # Só o tipo do erro: a mensagem completa traria o segredo junto com a URL
        sys.exit(f"⚠️ Falha de rede ({type(e).__name__})")

    corpo = ler_json(resposta)
    if "access_token" not in corpo:
        sys.exit(f"⚠️ A Meta recusou a troca: {erro_da_resposta(resposta, corpo)}")

    paginas = chamar(
        "GET",
        f"{GRAPH}/{VERSAO_API}/me/accounts",
        corpo["access_token"],
        params={"fields": "id,name,tasks,access_token", "limit": 100},
    ).get("data", [])

    if not paginas:
        sys.exit(
            "⚠️ Esse token não enxerga nenhuma página. Gere de novo marcando a página "
            "e a permissão business_management."
        )

    if args.pagina:
        paginas = [p for p in paginas if args.pagina in (p["id"], p["name"])]

    if len(paginas) != 1:
        print("Rode de novo escolhendo a página com --pagina ID:")
        for p in paginas:
            print(f"   {p['id']}  {p['name']}")
        sys.exit(1)

    pagina = paginas[0]
    if "CREATE_CONTENT" not in pagina.get("tasks", []):
        sys.exit(f"⚠️ Seu perfil não tem permissão de criar conteúdo em '{pagina['name']}'.")

    set_key(ARQUIVO_ENV, "FB_PAGE_ID", pagina["id"])
    set_key(ARQUIVO_ENV, "FB_PAGE_TOKEN", pagina["access_token"])

    print(f"✅ Token da página '{pagina['name']}' gravado no .env")
    print("   Agora apague FB_USER_TOKEN e FB_APP_SECRET do .env: não são mais necessários.")


def comando_agendar(args):
    if not os.path.isdir(args.pasta):
        sys.exit(f"⚠️ Pasta não encontrada: {args.pasta}")

    if args.intervalo < 1 or args.por_dia < 1 or (args.limite is not None and args.limite < 1):
        sys.exit("⚠️ --intervalo, --por-dia e --limite precisam ser maiores que zero.")
    if (args.por_dia - 1) * args.intervalo >= 24 * 60:
        sys.exit("⚠️ Com esse intervalo os vídeos de um dia não cabem em 24h.")

    arquivos = listar_videos(args.pasta)
    if not arquivos:
        sys.exit("⚠️ Nenhum .mp4 na pasta.")

    hora, minuto = interpretar_hora(args.hora)
    agenda = montar_agenda(
        args.pasta, arquivos, interpretar_data(args.data), hora, minuto, args.intervalo, args.por_dia
    )

    ultimo_do_dia = agenda[min(args.por_dia, len(agenda)) - 1][1]
    if ultimo_do_dia.date() != agenda[0][1].date():
        print("⚠️ AVISO: os horários do dia passam da meia-noite e invadem o dia seguinte.")

    historico = carregar_historico()
    agora = datetime.now()
    fila = []
    # Horários já tomados por outros arquivos, para não empilhar dois reels no mesmo minuto
    ocupados = {
        r.get("quando"): chave for chave, r in historico.items()
        if r.get("etapa") in ("enviado", "agendado")
    }

    print(f"\n{'#':>3}  {'Quando':<16}  {'Situação':<26}  Arquivo")
    for indice, (caminho, quando) in enumerate(agenda, 1):
        anterior = historico.get(chave_video(caminho)) or {}
        if anterior.get("tamanho") != os.path.getsize(caminho) or args.forcar:
            anterior = {}
        dono = ocupados.get(quando.isoformat(timespec="minutes"))

        if anterior.get("etapa") == "agendado":
            situacao = f"já agendado {datetime.fromisoformat(anterior['quando']):%d/%m %H:%M}"
        elif quando - agora < ANTECEDENCIA_MINIMA:
            situacao = "horário já passou"
        elif quando - agora > ANTECEDENCIA_MAXIMA:
            situacao = "além de 28 dias"
        elif dono and dono != chave_video(caminho) and not args.forcar:
            situacao = "horário já ocupado"
        else:
            situacao = problema_no_video(caminho)
            if not situacao:
                # "enviado" = upload feito mas sem confirmação do agendamento
                retomar = anterior.get("video_id") if anterior.get("etapa") == "enviado" else None
                situacao = "retomar" if retomar else "novo"
                fila.append((caminho, quando, retomar))

        print(f"{indice:>3}  {quando:%d/%m/%y %H:%M}    {situacao:<26}  {os.path.basename(caminho)}")

    if args.limite:
        fila = fila[: args.limite]
    if args.forcar and fila:
        print("⚠️ --forcar: tudo o que está na fila será enviado DE NOVO, mesmo o que já foi agendado.")

    print(f"\n{len(fila)} de {len(agenda)} vídeos para agendar.")

    if args.simular or not fila:
        return

    config = carregar_config()
    page_id = config["FB_PAGE_ID"]
    token = config["FB_PAGE_TOKEN"]

    print(f"Página: {conferir_pagina(page_id, token)} ({page_id})")

    if not args.sim and input("Confirmar o agendamento? [s/N] ").strip().lower() != "s":
        sys.exit("Cancelado.")

    agendados = []
    falhas = 0

    for posicao, (caminho, quando, retomar) in enumerate(fila, 1):
        nome = os.path.basename(caminho)

        if agendados_nas_ultimas_24h(historico, page_id) >= REELS_POR_24H:
            print(f"⚠️ Limite da Meta: {REELS_POR_24H} reels por API a cada 24h.")
            print("   Rode o mesmo comando amanhã: os já agendados são pulados.")
            falhas += len(fila) - posicao + 1
            break

        if retomar:
            if (historico.get(chave_video(caminho)) or {}).get("pagina") != page_id:
                retomar = None
            else:
                try:
                    if consultar_status(retomar, token).get("video_status") in ("expired", "error", "upload_failed"):
                        retomar = None
                except ErroAPI:
                    pass

        registro = {
            "arquivo": caminho,
            "tamanho": os.path.getsize(caminho),
            "quando": quando.isoformat(timespec="minutes"),
            "pagina": page_id,
            "video_id": retomar,
            "etapa": "enviado" if retomar else "novo",
        }
        historico[chave_video(caminho)] = registro

        print(f"[{posicao}/{len(fila)}] {nome} -> {quando:%d/%m/%y %H:%M}")

        try:
            legenda = ler_legenda(caminho, args.legenda)

            if not retomar:
                video_id, upload_url = iniciar_envio(page_id, token)
                registro.update(video_id=video_id, etapa="iniciado")
                salvar_historico(historico)

                enviar_arquivo(upload_url, caminho, video_id, token)
                registro["etapa"] = "enviado"
                salvar_historico(historico)

            video_id = registro["video_id"]
            if not (retomar and ja_programado(video_id, token)):
                programar(page_id, video_id, quando, legenda, token)

            registro.update(etapa="agendado", criado_em=datetime.now().isoformat(timespec="seconds"))
            salvar_historico(historico)

        except (ErroAPI, OSError) as erro:
            falhas += 1
            registro["erro"] = str(erro)
            salvar_historico(historico)
            print(f"      ⚠️ Falhou: {erro}")

            if not isinstance(erro, ErroAPI):
                continue

            if erro.limite or erro.acesso:
                if erro.limite:
                    print("      A Meta limitou as publicações por API. Rode o mesmo comando mais tarde:")
                    print("      os que já foram agendados são pulados automaticamente.")
                else:
                    print("      Token inválido ou sem permissão. Gere outro e rode de novo.")
                falhas += len(fila) - posicao
                break

            continue

        agendados.append((nome, video_id, quando, registro))
        print(f"      ✅ Programado (id {video_id})")

    confirmados, problemas = conferir_processamento(agendados, token, args.espera, historico)
    processando = len(agendados) - confirmados - problemas
    pendencias = falhas + problemas + processando

    print(
        f"\n{'⚠️' if pendencias else '✅'} {confirmados} confirmados, "
        f"{processando} ainda processando, {falhas + problemas} com problema."
    )
    if processando:
        print("   Rode 'status' daqui a alguns minutos para confirmar os que faltam.")
    if pendencias:
        sys.exit(1)


def conferir_processamento(agendados, token, espera, historico):
    """Confere na Meta se cada reel ficou mesmo programado, e no horário certo.

    Devolve (confirmados, com problema).
    """
    if not agendados:
        return 0, 0

    print("\nConferindo na Meta...")
    pendentes = list(agendados)
    confirmados = 0
    problemas = 0
    limite = time.time() + espera

    while pendentes:
        for item in list(pendentes):
            nome, video_id, quando, registro = item
            try:
                situacao, detalhe, horario = resumir_status(consultar_status(video_id, token))
            except ErroAPI as erro:
                # Falha passageira: tenta de novo na próxima volta
                situacao = "processando" if erro.passageiro else "erro"
                detalhe, horario = str(erro), None

            if situacao == "processando":
                continue

            pendentes.remove(item)

            if situacao == "erro":
                problemas += 1
                # Sai de "agendado" para a próxima execução reenviar só este vídeo
                registro.update(etapa="falhou", erro=detalhe)
                salvar_historico(historico)
                print(f"   ⚠️ {nome}: {detalhe}")
            elif horario and abs((horario - quando).total_seconds()) > 60:
                problemas += 1
                print(f"   ⚠️ {nome}: a Meta gravou {horario:%d/%m %H:%M}, esperado {quando:%d/%m %H:%M}")
            else:
                confirmados += 1
                print(f"   ✅ {nome}: programado para {horario or quando:%d/%m %H:%M}")

        if not pendentes or time.time() > limite:
            break

        time.sleep(10)

    for nome, _, _, _ in pendentes:
        print(f"   ⏳ {nome}: ainda processando (confira depois com 'status')")

    return confirmados, problemas


def comando_status(args):
    config = carregar_config()
    token = config["FB_PAGE_TOKEN"]
    agora = datetime.now().isoformat(timespec="minutes")

    historico = carregar_historico()
    registros = [
        r for r in historico.values()
        if r.get("video_id") and r.get("etapa") == "agendado"
        and (args.todos or r.get("quando", "") >= agora)
    ]

    if not registros:
        print("Nenhum agendamento futuro no histórico.")
        return

    for r in sorted(registros, key=lambda r: r.get("quando", "")):
        try:
            situacao, detalhe, horario = resumir_status(consultar_status(r["video_id"], token))
        except ErroAPI as erro:
            situacao, detalhe, horario = "sem resposta", str(erro), None

        if situacao == "erro":
            # A Meta recusou depois do envio: libera para o próximo 'agendar' reenviar
            r.update(etapa="falhou", erro=detalhe)
            salvar_historico(historico)

        quando = datetime.fromisoformat(r["quando"])
        print(
            f"{horario or quando:%d/%m/%y %H:%M}  {situacao:<11}  {detalhe:<12}  "
            f"{r['video_id']}  {os.path.basename(r.get('arquivo', ''))}"
        )


def comando_cancelar(args):
    config = carregar_config()
    chamar("DELETE", f"{GRAPH}/{VERSAO_API}/{args.video_id}", config["FB_PAGE_TOKEN"])

    historico = carregar_historico()
    for registro in historico.values():
        if registro.get("video_id") == args.video_id:
            registro["etapa"] = "cancelado"
    salvar_historico(historico)

    print(f"✅ Reel {args.video_id} apagado.")


def main():
    # Console do Windows: garante que os emojis não derrubem o script
    for saida in (sys.stdout, sys.stderr):
        saida.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Agenda Reels na Página pela Graph API.")
    comandos = parser.add_subparsers(dest="comando", required=True)

    comandos.add_parser("verificar", help="testa o token e a página do .env")

    p = comandos.add_parser("token", help="gera o token longo da página a partir do .env")
    p.add_argument("--pagina", help="id ou nome da página, se o token enxergar mais de uma")

    p = comandos.add_parser("agendar", help="envia e programa os .mp4 de uma pasta")
    p.add_argument("--pasta", required=True)
    p.add_argument("--data", help="DD/MM/AAAA do primeiro dia (padrão: amanhã)")
    p.add_argument("--hora", default=hora_inicial, help="HH:MM do primeiro vídeo do dia")
    p.add_argument("--intervalo", type=int, default=intervalo_minutos, help="minutos entre vídeos")
    p.add_argument("--por-dia", type=int, default=videos_por_dia, dest="por_dia")
    p.add_argument("--legenda", default="", help="legenda padrão (um .txt ao lado do vídeo tem prioridade)")
    p.add_argument("--limite", type=int, help="agenda só os N primeiros da fila (bom para testar)")
    p.add_argument("--simular", action="store_true", help="só mostra a agenda, não envia nada")
    p.add_argument("--sim", action="store_true", help="não pede confirmação")
    p.add_argument("--forcar", action="store_true", help="reenvia mesmo o que já consta como agendado")
    p.add_argument("--espera", type=int, default=600, help="segundos aguardando o processamento")

    p = comandos.add_parser("status", help="consulta na Meta os agendamentos do histórico")
    p.add_argument("--todos", action="store_true", help="inclui os que já passaram")

    # A Meta não documenta o DELETE para reels programados; confira no Planner depois
    p = comandos.add_parser("cancelar", help="apaga um reel programado")
    p.add_argument("video_id")

    args = parser.parse_args()

    try:
        {
            "verificar": comando_verificar,
            "token": comando_token,
            "agendar": comando_agendar,
            "status": comando_status,
            "cancelar": comando_cancelar,
        }[args.comando](args)
    except ErroAPI as erro:
        sys.exit(f"⚠️ Erro da API: {erro}")


if __name__ == "__main__":
    main()
