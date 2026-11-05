import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, diaSemana, horaMin, megas, type AgendaForm, type ItemTarefa, type Previa, type Tarefa } from "../api";
import { Aviso, btnSecundario, Campo, Cartao, inputCls, Kpi, PageHero, Pilula } from "../components/ui";

const amanha = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso local
};

const PADRAO: AgendaForm = { pasta: "", data: amanha(), hora: "10:00", intervalo: 60, por_dia: 10, legenda: "", limite: null };

function lerForm(chave: string): AgendaForm {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave) ?? "null");
    // a data sempre recomeça em amanhã: a de ontem já passou
    return salvo ? { ...PADRAO, ...salvo, data: amanha() } : PADRAO;
  } catch {
    return PADRAO;
  }
}

export default function Agendar({ configurado, pagina }: { configurado: boolean; pagina?: string }) {
  // Cada influenciador lembra a própria pasta e horários
  const chave = `agenda-form-${pagina ?? "nenhuma"}`;
  const [form, setForm] = useState<AgendaForm>(() => lerForm(chave));
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [tarefa, setTarefa] = useState<Tarefa | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const mudar = <K extends keyof AgendaForm>(k: K, v: AgendaForm[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setPrevia(null);
  };

  useEffect(() => {
    try {
      localStorage.setItem(chave, JSON.stringify(form));
    } catch {
      /* sem localStorage: só não lembra o formulário */
    }
  }, [form, chave]);

  // Retoma a tela de envio se houver um em andamento (ex.: a página foi recarregada)
  useEffect(() => {
    api.tarefa().then((t) => t && !t.fim && setTarefa(t)).catch(() => {});
  }, []);

  const rodando = !!tarefa && !tarefa.fim;
  useEffect(() => {
    if (!rodando) return;
    const id = setInterval(() => api.tarefa().then(setTarefa).catch(() => {}), 1500);
    return () => clearInterval(id);
  }, [rodando]);

  const escolher = async () => {
    setErro("");
    try {
      const { pasta } = await api.escolherPasta();
      if (pasta) mudar("pasta", pasta);
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const verPrevia = async () => {
    setErro("");
    setCarregando(true);
    try {
      setPrevia(await api.previa(form));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  };

  const enviar = async () => {
    if (!previa) return;
    const total = form.limite ? Math.min(form.limite, previa.na_fila) : previa.na_fila;
    if (!confirm(`Enviar e programar ${total} reels na página? Eles vão ao ar nos horários da prévia.`)) return;
    setErro("");
    try {
      setTarefa(await api.agendar(form));
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  if (tarefa) return <Envio tarefa={tarefa} aoFechar={() => { setTarefa(null); setPrevia(null); }} />;

  return (
    <div className="flex flex-col gap-6">
      <PageHero
        eyebrow="Reels · Facebook"
        title="Agendar semana"
        lede="Escolha a pasta, confira a prévia e mande tudo de uma vez. Os reels ficam programados na própria Meta: o PC pode ser desligado depois do envio."
        asset="/brand/3d/cal.png"
      />

      {!configurado && (
        <Aviso tom="alerta">
          Falta conectar a página. <Link className="font-semibold underline" to="/configuracoes">Abrir Configurações</Link>
        </Aviso>
      )}

      <Cartao titulo="1. Vídeos e horários">
        <div className="grid gap-4 md:grid-cols-6">
          <div className="md:col-span-6">
            <Campo label="Pasta dos vídeos" ajuda="Todos os .mp4 da pasta, em ordem de nome. Um .txt com o mesmo nome do vídeo vira a legenda dele.">
              <div className="flex gap-2">
                <input className={`${inputCls} flex-1`} value={form.pasta} onChange={(e) => mudar("pasta", e.target.value)} placeholder="E:\Edição\<influenciador>\Facebook\..." />
                <button type="button" className={btnSecundario} onClick={escolher}>Escolher…</button>
              </div>
            </Campo>
          </div>
          <div className="md:col-span-2">
            <Campo label="Primeiro dia">
              <input type="date" className={inputCls} value={form.data} onChange={(e) => mudar("data", e.target.value)} />
            </Campo>
          </div>
          <div className="md:col-span-1">
            <Campo label="Primeiro horário">
              <input type="time" className={inputCls} value={form.hora} onChange={(e) => mudar("hora", e.target.value)} />
            </Campo>
          </div>
          <div className="md:col-span-1">
            <Campo label="Intervalo (min)">
              <input type="number" min={1} className={inputCls} value={form.intervalo} onChange={(e) => mudar("intervalo", Number(e.target.value))} />
            </Campo>
          </div>
          <div className="md:col-span-1">
            <Campo label="Reels por dia">
              <input type="number" min={1} className={inputCls} value={form.por_dia} onChange={(e) => mudar("por_dia", Number(e.target.value))} />
            </Campo>
          </div>
          <div className="md:col-span-1">
            <Campo label="Enviar só" ajuda="Vazio = todos">
              <input type="number" min={1} className={inputCls} value={form.limite ?? ""} onChange={(e) => mudar("limite", e.target.value ? Number(e.target.value) : null)} />
            </Campo>
          </div>
          <div className="md:col-span-6">
            <Campo label="Legenda padrão (opcional)" ajuda="Usada nos vídeos que não têm .txt próprio.">
              <textarea rows={2} className={inputCls} value={form.legenda} onChange={(e) => mudar("legenda", e.target.value)} />
            </Campo>
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="button" className="skip-btn-primary disabled:opacity-50" disabled={!form.pasta || carregando} onClick={verPrevia}>
            {carregando ? "Analisando vídeos…" : "Ver prévia"}
          </button>
        </div>
      </Cartao>

      {erro && <Aviso>{erro}</Aviso>}

      {previa && <PreviaView previa={previa} limite={form.limite} configurado={configurado} aoEnviar={enviar} />}
    </div>
  );
}

function PreviaView({ previa, limite, configurado, aoEnviar }: { previa: Previa; limite: number | null; configurado: boolean; aoEnviar: () => void }) {
  const pulados = previa.itens.filter((i) => !i.entra);
  const vaoAgora = limite ? Math.min(limite, previa.na_fila) : previa.na_fila;
  const dias = useMemo(() => {
    const grupos = new Map<string, typeof previa.itens>();
    for (const i of previa.itens) {
      const dia = i.quando.slice(0, 10);
      grupos.set(dia, [...(grupos.get(dia) ?? []), i]);
    }
    return [...grupos.entries()];
  }, [previa]);

  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Vídeos na pasta" value={previa.itens.length} />
        <Kpi label="Prontos" value={previa.na_fila} tom="ok" />
        <Kpi label="Pulados" value={pulados.length} tom={pulados.length ? "alerta" : undefined} />
        <Kpi label="Dias" value={dias.length} />
      </div>

      {dias.some(([, itens]) => itens.filter((i) => i.entra).length > previa.limite_24h) && (
        <Aviso tom="alerta">
          A Meta aceita até {previa.limite_24h} reels publicados por API a cada 24h. Algum dia desta agenda passa disso: diminua os reels por dia.
        </Aviso>
      )}

      <Cartao
        titulo="2. Prévia da agenda"
        acao={
          <button type="button" className="skip-btn-primary disabled:opacity-50" disabled={!configurado || !vaoAgora} onClick={aoEnviar}>
            Enviar {vaoAgora} reels
          </button>
        }
      >
        <div className="flex flex-col gap-5">
          {dias.map(([dia, itens]) => (
            <div key={dia}>
              <div className="mb-2 font-[family-name:var(--font-ui)] text-sm font-bold capitalize text-neutral-600 dark:text-neutral-400">
                {diaSemana(`${dia}T12:00`)}
              </div>
              <ul className="divide-y divide-[var(--skip-line)] overflow-hidden rounded-xl border border-[var(--skip-line)]">
                {itens.map((i) => (
                  <li key={i.caminho} className={`flex items-center gap-3 px-3 py-2 text-sm ${i.entra ? "" : "bg-[var(--skip-surface-2)]"}`}>
                    <span className="w-12 font-[family-name:var(--font-impact)] tabular-nums text-[var(--color-skip-indigo)] dark:text-violet-300">{horaMin(i.quando)}</span>
                    <span className={`min-w-0 flex-1 truncate ${i.entra ? "" : "text-neutral-500 line-through"}`} title={i.arquivo}>{i.arquivo}</span>
                    <span className="hidden text-xs text-neutral-500 sm:inline">{megas(i.tamanho)}</span>
                    <Pilula tom={i.entra ? (i.retomar ? "info" : "ok") : i.situacao.startsWith("Já agendado") ? "neutro" : "alerta"}>{i.situacao}</Pilula>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Cartao>
    </>
  );
}

const ROTULO: Record<ItemTarefa["etapa"], [string, Parameters<typeof Pilula>[0]["tom"]]> = {
  "na fila": ["Na fila", "neutro"],
  enviando: ["Enviando", "info"],
  programando: ["Programando", "info"],
  processando: ["Meta processando", "info"],
  confirmado: ["Confirmado", "ok"],
  erro: ["Erro", "erro"],
  cancelado: ["Não enviado", "neutro"],
  limite: ["Acima de 30 em 24h", "alerta"],
};

function Envio({ tarefa, aoFechar }: { tarefa: Tarefa; aoFechar: () => void }) {
  const conta = (etapas: ItemTarefa["etapa"][]) => tarefa.itens.filter((i) => etapas.includes(i.etapa)).length;
  const terminou = !!tarefa.fim;
  const programados = conta(["processando", "confirmado"]);
  const paraAmanha = conta(["limite"]);

  return (
    <div className="flex flex-col gap-6">
      <PageHero
        eyebrow={terminou ? "Envio concluído" : tarefa.conferindo ? "Conferindo na Meta" : "Enviando"}
        title={terminou ? "Pronto" : "Subindo os reels"}
        lede={terminou
          ? "Os confirmados já estão no Planner do Business Suite."
          : "Pode deixar esta aba aberta. Fechar o navegador não para o envio; fechar a janela do Publicador para."}
        asset="/brand/3d/megaphone.png"
      >
        {!terminou && !tarefa.parar && (
          <button type="button" className="pf-hbtn" onClick={() => api.parar()}>Parar depois do atual</button>
        )}
        {terminou && <button type="button" className="pf-hbtn primary" onClick={aoFechar}>Novo agendamento</button>}
      </PageHero>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Total" value={tarefa.itens.length} />
        <Kpi label="Programados" value={programados} tom="ok" />
        <Kpi label="Confirmados" value={conta(["confirmado"])} tom="ok" />
        <Kpi label="Acima do limite" value={paraAmanha} tom={paraAmanha ? "alerta" : undefined} />
        <Kpi label="Com erro" value={conta(["erro"])} tom={conta(["erro"]) ? "erro" : undefined} />
      </div>

      {paraAmanha > 0 && (
        <Aviso tom="alerta">
          {paraAmanha} reels não foram enviados porque cairiam em 24h que já têm 30 reels publicados por API, o máximo da Meta.
          Diminua os reels por dia ou mude os horários e envie a mesma pasta de novo.
        </Aviso>
      )}

      {tarefa.erro && <Aviso>Erro inesperado: {tarefa.erro}</Aviso>}

      <Cartao>
        <ul className="divide-y divide-[var(--skip-line)]">
          {tarefa.itens.map((i) => {
            const [rotulo, tom] = ROTULO[i.etapa];
            return (
              <li key={i.caminho} className="flex flex-col gap-1.5 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-24 shrink-0 tabular-nums text-neutral-500">{i.quando.slice(8, 10)}/{i.quando.slice(5, 7)} {horaMin(i.quando)}</span>
                  <span className="min-w-0 flex-1 truncate" title={i.arquivo}>{i.arquivo}</span>
                  <Pilula tom={tom}>{rotulo}</Pilula>
                </div>
                {i.etapa === "enviando" && (
                  <div className="ml-27 h-1.5 overflow-hidden rounded-full bg-[var(--skip-line)]">
                    <div className="skip-gradient-accent h-full transition-all" style={{ width: `${i.progresso}%` }} />
                  </div>
                )}
                {i.detalhe && i.etapa !== "confirmado" && <span className="ml-27 text-xs text-neutral-500">{i.detalhe}</span>}
              </li>
            );
          })}
        </ul>
      </Cartao>
    </div>
  );
}
