import { useCallback, useEffect, useState } from "react";
import { api, dataHora, type Agendado } from "../api";
import { Aviso, btnSecundario, Cartao, Kpi, PageHero, Pilula } from "../components/ui";

export default function Agendados() {
  const [lista, setLista] = useState<Agendado[] | null>(null);
  const [todos, setTodos] = useState(false);
  const [conferindo, setConferindo] = useState(false);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async (conferir = false) => {
    setErro("");
    setConferindo(conferir);
    try {
      setLista(await api.agendados(conferir, todos));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setConferindo(false);
    }
  }, [todos]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const cancelar = async (a: Agendado) => {
    if (!confirm(`Apagar o reel "${a.arquivo}" programado para ${dataHora(a.quando)}?`)) return;
    try {
      await api.cancelar(a.video_id);
      await carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const ativos = lista?.filter((a) => a.etapa === "agendado") ?? [];
  const proximo = ativos[0];

  return (
    <div className="flex flex-col gap-6">
      <PageHero
        eyebrow="Fila"
        title="Agendados"
        lede="Tudo o que este PC já mandou para a Meta. Para ver o que está mesmo no Facebook, use Conferir na Meta."
        asset="/brand/3d/camera.png"
      >
        <button type="button" className="pf-hbtn primary" disabled={conferindo} onClick={() => carregar(true)}>
          {conferindo ? "Conferindo…" : "Conferir na Meta"}
        </button>
      </PageHero>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Kpi label="Programados" value={ativos.length} tom="ok" />
        <Kpi label="Próximo" value={proximo ? dataHora(proximo.quando) : "—"} />
        <Kpi label="Com problema" value={lista?.filter((a) => a.etapa === "falhou" || a.meta === "erro").length ?? 0} />
      </div>

      {erro && <Aviso>{erro}</Aviso>}

      <Cartao
        acao={
          <label className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
            <input type="checkbox" checked={todos} onChange={(e) => setTodos(e.target.checked)} />
            Mostrar os que já passaram
          </label>
        }
      >
        {!lista ? (
          <p className="text-sm text-neutral-500">Carregando…</p>
        ) : !lista.length ? (
          <p className="text-sm text-neutral-500">Nenhum reel programado.</p>
        ) : (
          <ul className="divide-y divide-[var(--skip-line)]">
            {lista.map((a) => (
              <li key={a.video_id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                <span className="w-32 shrink-0 whitespace-nowrap font-[family-name:var(--font-impact)] tabular-nums text-[var(--color-skip-indigo)] dark:text-violet-300">{dataHora(a.quando)}</span>
                <span className="min-w-0 flex-1 truncate" title={a.arquivo}>{a.arquivo}</span>
                {a.etapa === "cancelado" ? <Pilula tom="neutro">Cancelado</Pilula>
                  : a.etapa === "falhou" || a.meta === "erro" ? <Pilula tom="erro" >{a.detalhe || "Falhou"}</Pilula>
                  : a.meta === "processando" ? <Pilula tom="info">Processando</Pilula>
                  : a.meta === "ok" ? <Pilula tom="ok">Confirmado na Meta</Pilula>
                  : <Pilula tom="ok">Programado</Pilula>}
                {a.etapa === "agendado" && (
                  <button type="button" className={`${btnSecundario} !px-3 !py-1 text-xs`} onClick={() => cancelar(a)}>Cancelar</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
