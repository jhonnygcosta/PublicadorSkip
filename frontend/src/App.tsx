import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { api, type Conta } from "./api";
import Nav from "./components/Nav";
import { Aviso } from "./components/ui";
import Agendados from "./pages/Agendados";
import Agendar from "./pages/Agendar";
import Configuracoes from "./pages/Configuracoes";

export default function App() {
  const [conta, setConta] = useState<Conta | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.conta().then(setConta).catch((e: Error) => setErro(e.message));
  }, []);

  return (
    <BrowserRouter>
      <div className="skip-shell min-h-svh bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-50">
        <Nav conta={conta} aoTrocar={setConta} />
        <main className="mx-auto w-full max-w-6xl px-6 py-10">
          {erro && (
            <div className="mb-6">
              <Aviso>Não consegui falar com o Publicador ({erro}). A janela preta do iniciar.bat está aberta?</Aviso>
            </div>
          )}
          <Routes>
            <Route path="/" element={<Agendar key={conta?.pagina_id} pagina={conta?.pagina_id} configurado={!!conta?.configurado} />} />
            <Route path="/agendados" element={<Agendados key={conta?.pagina_id} />} />
            <Route path="/configuracoes" element={<Configuracoes conta={conta} aoSalvar={setConta} />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
