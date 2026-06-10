import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/groups", label: "Groups" },
  { href: "/bracket", label: "Bracket" },
  { href: "/predicted", label: "Predicted" },
  { href: "/results", label: "Results" },
  { href: "/calibration", label: "Calibration" },
  { href: "/methodology", label: "Methodology" },
];

export function NavBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-mute/20 bg-paper/90 backdrop-blur">
      <nav className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-4 py-3">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 font-extrabold tracking-tight"
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-tomato text-paper">
            ⚽
          </span>
          <span className="text-ink">
            WC<span className="text-tomato">2026</span>
          </span>
        </Link>
        {/* Scrolls within the bar on small screens instead of widening the page */}
        <div className="flex min-w-0 items-center gap-1 overflow-x-auto whitespace-nowrap text-sm font-semibold [scrollbar-width:none]">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="shrink-0 rounded-md px-2.5 py-1.5 text-ink transition hover:bg-tomato-50 hover:text-tomato"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
