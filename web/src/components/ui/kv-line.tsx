type KvLineProps = {
  k: string;
  v: string;
  /** Light/dark surface adapts label/value contrast. */
  dark?: boolean;
};

export function KvLine({ k, v, dark = false }: KvLineProps) {
  return (
    <div className="flex items-baseline gap-3 font-mono text-xs leading-relaxed">
      <span className={dark ? "text-paper/55" : "text-graphite"}>{k}</span>
      <span className={dark ? "text-paper" : "text-ink"}>{v}</span>
    </div>
  );
}
