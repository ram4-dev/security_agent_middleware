// Geometric SVG version of the Tranquera logo. Two postes + two travesaños
// per `identidad/Construcci_n.html`. ViewBox is 200×200; the mark sits in
// the inner 8u×6u frame with 1u of clear space on each side.
//
//   poste:      18×120  at x=36/146, y=40
//   travesaño:  92×18   at x=54,     y=74 and y=108
//
// `currentColor` so it inherits the surrounding text color (paper-on-ink
// or ink-on-paper, no color logic in the component).

type TranqueraMarkProps = {
  className?: string;
  title?: string;
};

export function TranqueraMark({
  className = "",
  title = "Tranquera",
}: TranqueraMarkProps) {
  return (
    <svg
      viewBox="0 0 200 200"
      role="img"
      aria-label={title}
      className={className}
      fill="currentColor"
    >
      <title>{title}</title>
      {/* postes */}
      <rect x="36" y="40" width="18" height="120" />
      <rect x="146" y="40" width="18" height="120" />
      {/* travesaños */}
      <rect x="54" y="74" width="92" height="18" />
      <rect x="54" y="108" width="92" height="18" />
    </svg>
  );
}
