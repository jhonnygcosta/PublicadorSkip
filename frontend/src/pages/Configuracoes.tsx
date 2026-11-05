import { useState } from "react";
import { api, type Conta } from "../api";
import { Aviso, btnSecundario, Campo, Cartao, inputCls, PageHero, Pilula } from "../components/ui";

export default function Configuracoes({ conta, aoSalvar }: { conta: Conta | null; aoSalvar: (c: Conta) => void }) {
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");

  // Gerar token permanente
  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [userToken, setUserToken] = useState("");
  const [gerando, setGerando] = useState(false);

  // Colar token de página pronto
  const [pageId, setPageId] = useState("");
  const [token, setToken] = useState("");
  const [salvando, setSalvando] = useState(false);

  const limpar = () => { setErro(""); setOk(""); };

  const gerar = async () => {
    limpar();
    setGerando(true);
    try {
      const r = await api.gerarToken(appId, appSecret, userToken);
      setAppSecret("");
      setUserToken("");
      const nomes = (r.salvas ?? []).map((s) => s.nome).join(", ");
      const sem = r.sem_permissao?.length ? ` Sem permissão de postar em: ${r.sem_permissao.join(", ")}.` : "";
      setOk(`Token permanente salvo para: ${nomes}. Escolha o influenciador no topo da tela.${sem}`);
      aoSalvar(r);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setGerando(false);
    }
  };

  const salvar = async () => {
    limpar();
    setSalvando(true);
    try {
      const nova = await api.salvarConta(pageId, token);
      setToken("");
      setPageId("");
      setOk(`Conectado à página ${nova.nome}.`);
      aoSalvar(nova);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  };

  const acao = async (fn: () => Promise<Conta>) => {
    limpar();
    try { aoSalvar(await fn()); } catch (e) { setErro((e as Error).message); }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHero eyebrow="Contas" title="Configurações" lede="As páginas do Facebook (uma por influenciador) onde os reels são publicados." asset="/brand/3d/bolt.png" />

      <Cartao titulo="Influenciadores conectados">
        {conta?.contas?.length ? (
          <ul className="divide-y divide-[var(--skip-line)]">
            {conta.contas.map((c) => {
              const ativa = c.pagina_id === conta.pagina_id;
              return (
                <li key={c.pagina_id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                  <b>{c.nome}</b>
                  <span className="text-neutral-500">· id {c.pagina_id}</span>
                  {ativa && <Pilula tom="ok">Postando agora</Pilula>}
                  <div className="ml-auto flex gap-2">
                    {!ativa && (
                      <button type="button" className={btnSecundario} onClick={() => acao(() => api.escolherConta(c.pagina_id))}>
                        Usar esta
                      </button>
                    )}
                    <button
                      type="button"
                      className={btnSecundario}
                      onClick={() => confirm(`Remover ${c.nome} do Publicador? (o histórico não é apagado)`) && acao(() => api.removerConta(c.pagina_id))}
                    >
                      Remover
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-neutral-500">Nenhuma página conectada.</p>
        )}
      </Cartao>

      <Cartao titulo="Gerar token permanente (novo influenciador)">
        <ol className="mb-5 list-decimal space-y-1 pl-5 text-sm text-neutral-600 dark:text-neutral-400">
          <li>Abra o <b>Graph API Explorer</b> (developers.facebook.com/tools/explorer) e escolha o app da Skip.</li>
          <li>Em "Usuário ou página", escolha <b>Obter token de acesso do usuário</b>.</li>
          <li>Marque <b>pages_show_list, pages_read_engagement, pages_manage_posts</b> e <b>business_management</b>.</li>
          <li>Clique em <b>Generate Access Token</b> e, na janela da Meta, marque a página do influenciador.</li>
          <li>Copie o token gerado e cole abaixo, junto com o ID e a Chave secreta do app (Configurações → Básico).</li>
        </ol>
        <div className="grid gap-4 md:grid-cols-2">
          <Campo label="ID do app">
            <input className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)} placeholder="2248…" />
          </Campo>
          <Campo label="Chave secreta do app" ajuda="Usada só nesta troca; não fica gravada.">
            <input type="password" autoComplete="off" className={inputCls} value={appSecret} onChange={(e) => setAppSecret(e.target.value)} />
          </Campo>
          <div className="md:col-span-2">
            <Campo label="Token do usuário (Graph API Explorer)">
              <input type="password" autoComplete="off" className={inputCls} value={userToken} onChange={(e) => setUserToken(e.target.value)} placeholder="EAA…" />
            </Campo>
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="button" className="skip-btn-primary disabled:opacity-50" disabled={!appId || !appSecret || !userToken || gerando} onClick={gerar}>
            {gerando ? "Falando com a Meta…" : "Gerar e salvar"}
          </button>
        </div>
      </Cartao>

      <Cartao titulo="Já tenho o token da página">
        <div className="grid gap-4">
          <Campo label="ID da página">
            <input className={inputCls} value={pageId} onChange={(e) => setPageId(e.target.value)} placeholder="1530960383833039" />
          </Campo>
          <Campo label="Token da página" ajuda="Fica gravado só no arquivo backend/contas.json deste PC. Nunca é mostrado de volta aqui.">
            <input type="password" autoComplete="off" className={inputCls} value={token} onChange={(e) => setToken(e.target.value)} placeholder="EAA…" />
          </Campo>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="button" className={btnSecundario} disabled={!pageId || !token || salvando} onClick={salvar}>
            {salvando ? "Testando na Meta…" : "Testar e salvar"}
          </button>
        </div>
      </Cartao>

      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
    </div>
  );
}
