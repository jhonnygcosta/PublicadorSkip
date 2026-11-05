import type { ReactNode } from "react";

// Peças visuais do dashboard da Skip (PageHero, KpiCard), sem as dependências de CMS e dados de lá.

export function PageHero({
  eyebrow,
  title,
  lede,
  asset,
  children,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
  asset?: string;
  children?: ReactNode;
}) {
  return (
    <header className="skip-hero">
      <div className="skip-hero__checker" />
      <div className="skip-hero__grid" />
      {asset && <img className="skip-hero__asset" src={asset} alt="" />}
      <div className="relative z-[2] flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-[62%]">
          <span className="skip-eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          {lede && <p className="skip-hero__lede">{lede}</p>}
        </div>
        {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
      </div>
    </header>
  );
}

export function Kpi({ label, value, tom }: { label: string; value: string | number; tom?: "ok" | "alerta" | "erro" }) {
  const cor =
    tom === "ok" ? "text-emerald-600 dark:text-emerald-400"
    : tom === "alerta" ? "text-amber-600 dark:text-amber-400"
    : tom === "erro" ? "text-red-600 dark:text-red-400"
    : "";
  return (
    <div className="skip-shadow rounded-2xl border border-black/5 bg-white p-4 dark:border-white/10 dark:bg-neutral-900">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</div>
      <div className={`mt-1.5 font-[family-name:var(--font-impact)] text-2xl tabular-nums ${cor}`}>{value}</div>
    </div>
  );
}

export function Cartao({ titulo, children, acao }: { titulo?: string; children: ReactNode; acao?: ReactNode }) {
  return (
    <section className="skip-shadow rounded-2xl border border-black/5 bg-white p-5 dark:border-white/10 dark:bg-neutral-900">
      {(titulo || acao) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {titulo && <h2 className="font-[family-name:var(--font-ui)] text-lg font-bold">{titulo}</h2>}
          {acao}
        </div>
      )}
      {children}
    </section>
  );
}

export function Campo({ label, ajuda, children }: { label: string; ajuda?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-[family-name:var(--font-ui)] text-[11px] font-bold uppercase tracking-[.08em] text-neutral-500">
        {label}
      </span>
      {children}
      {ajuda && <span className="text-xs text-neutral-500">{ajuda}</span>}
    </label>
  );
}

export const inputCls =
  "rounded-xl border border-[var(--skip-line)] bg-[var(--skip-surface)] px-3 py-2 text-sm outline-none transition focus:border-[var(--color-skip-violet)] focus:ring-2 focus:ring-[var(--color-skip-violet)]/20";

export const btnSecundario =
  "rounded-full border border-[var(--skip-line)] bg-[var(--skip-surface)] px-4 py-2 font-[family-name:var(--font-ui)] text-sm font-semibold transition hover:border-[var(--color-skip-violet)] disabled:opacity-50";

const CORES_PILULA = {
  ok: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
  info: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  alerta: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
  erro: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  neutro: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

export function Pilula({ tom, children }: { tom: keyof typeof CORES_PILULA; children: ReactNode }) {
  return <span className={`skip-pill ${CORES_PILULA[tom]}`}>{children}</span>;
}

export function Aviso({ tom = "erro", children }: { tom?: "erro" | "alerta" | "ok"; children: ReactNode }) {
  const cls =
    tom === "erro" ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300"
    : tom === "alerta" ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300"
    : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300";
  return <div className={`rounded-xl border px-4 py-3 text-sm ${cls}`}>{children}</div>;
}
