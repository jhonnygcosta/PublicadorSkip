import { NavLink } from "react-router-dom";
import { useState } from "react";
import { api, type Conta } from "../api";

const LINKS = [
  { to: "/", label: "Agendar" },
  { to: "/agendados", label: "Agendados" },
  { to: "/configuracoes", label: "Configurações" },
];

export default function Nav({ conta, aoTrocar }: { conta: Conta | null; aoTrocar: (c: Conta) => void }) {
  const [trocando, setTrocando] = useState(false);

  const trocar = async (id: string) => {
    setTrocando(true);
    try {
      aoTrocar(await api.escolherConta(id));
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setTrocando(false);
    }
  };

  return (
    <nav className="skip-nav">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4">
        <NavLink to="/" className="flex items-center gap-3" aria-label="Skip · início">
          <img src="/brand/wordmark-white.png" alt="Skip" className="h-6 w-auto drop-shadow-sm" />
          <span className="hidden text-sm font-medium text-white/80 sm:inline">Publicador de Reels</span>
        </NavLink>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {conta?.configurado && (
            <label className="mr-2 flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white">
              <span aria-hidden>●</span>
              <span className="sr-only">Influenciador</span>
              <select
                className="cursor-pointer bg-transparent font-semibold text-white outline-none disabled:opacity-60"
                value={conta.pagina_id}
                disabled={trocando}
                onChange={(e) => trocar(e.target.value)}
                title="Para qual influenciador você está postando"
              >
                {conta.contas.map((c) => (
                  <option key={c.pagina_id} value={c.pagina_id} className="text-neutral-900">
                    {c.nome}
                  </option>
                ))}
              </select>
            </label>
          )}
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) => `skip-navlink${isActive ? " is-active" : ""}`}
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
