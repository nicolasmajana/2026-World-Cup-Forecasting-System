import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/groups", label: "Groups" },
  { href: "/bracket", label: "Bracket" },
  { href: "/calibration", label: "Calibration" },
  { href: "/methodology", label: "Methodology" },
];

export function NavBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-mute/20 bg-paper/90 backdrop-blur">
      <nav className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-extrabold tracking-tight">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-tomato text-paper">
            ⚽
          </span>
          <span className="text-ink">
            WC<span className="text-tomato">2026</span>
          </span>
        </Link>
        <div className="flex items-center gap-1 text-sm font-semibold">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-md px-3 py-1.5 text-ink transition hover:bg-tomato-50 hover:text-tomato"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
