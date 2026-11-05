// Chamadas à API Python (backend/app.py). Em dev o Vite repassa /api para a porta 8765.

export type ContaResumo = { pagina_id: string; nome: string };

export type Conta = {
  configurado: boolean;
  pagina_id?: string;
  nome?: string;
  contas: ContaResumo[];
  salvas?: ContaResumo[];
  sem_permissao?: string[];
};

export type AgendaForm = {
  pasta: string;
  data: string; // AAAA-MM-DD
  hora: string; // HH:MM
  intervalo: number;
  por_dia: number;
  legenda: string;
  limite: number | null;
};

export type ItemPrevia = {
  caminho: string;
  arquivo: string;
  quando: string;
  situacao: string;
  entra: boolean;
  retomar: string | null;
  tamanho: number;
};

export type Previa = { itens: ItemPrevia[]; na_fila: number; limite_24h: number };

export type EtapaEnvio =
  | "na fila" | "enviando" | "programando" | "processando"
  | "confirmado" | "erro" | "cancelado" | "limite";

export type ItemTarefa = ItemPrevia & {
  etapa: EtapaEnvio;
  progresso: number;
  detalhe: string;
  video_id: string | null;
};

export type Tarefa = {
  id: string;
  inicio: string;
  fim: string | null;
  parar: boolean;
  atual: number | null;
  conferindo: boolean;
  erro?: string;
  itens: ItemTarefa[];
};

export type Agendado = {
  video_id: string;
  arquivo: string;
  quando: string;
  etapa: "agendado" | "falhou" | "cancelado";
  detalhe: string;
  meta?: string;
};

async function pedir<T>(caminho: string, corpo?: unknown): Promise<T> {
  const resposta = await fetch(caminho, {
    method: corpo === undefined ? "GET" : "POST",
    headers: corpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = dados?.detail;
    throw new Error(typeof detalhe === "string" ? detalhe : `Erro ${resposta.status}`);
  }
  return dados as T;
}

export const api = {
  conta: () => pedir<Conta>("/api/conta"),
  salvarConta: (page_id: string, token: string) => pedir<Conta>("/api/conta", { page_id, token }),
  escolherConta: (pagina_id: string) => pedir<Conta>("/api/conta/ativa", { pagina_id }),
  removerConta: (pagina_id: string) => pedir<Conta>("/api/conta/remover", { pagina_id }),
  gerarToken: (app_id: string, app_secret: string, user_token: string) =>
    pedir<Conta>("/api/gerar-token", { app_id, app_secret, user_token }),
  previa: (f: AgendaForm) => pedir<Previa>("/api/previa", f),
  agendar: (f: AgendaForm) => pedir<Tarefa>("/api/agendar", f),
  tarefa: () => pedir<Tarefa | null>("/api/tarefa"),
  parar: () => pedir<Tarefa | null>("/api/tarefa/parar", {}),
  agendados: (conferir: boolean, todos: boolean) =>
    pedir<Agendado[]>(`/api/agendados?conferir_meta=${conferir}&todos=${todos}`),
  cancelar: (id: string) => pedir<{ ok: boolean }>(`/api/cancelar/${id}`, {}),
  escolherPasta: () => pedir<{ pasta: string | null }>("/api/escolher-pasta", {}),
};

export const dataHora = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export const diaSemana = (iso: string) =>
  new Date(iso).toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit" });

export const horaMin = (iso: string) => iso.slice(11, 16);

export const megas = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(0)} MB`;
