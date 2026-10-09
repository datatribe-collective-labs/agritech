import Link from "next/link";

export type TrailItem = { label: string; href?: string };

/** The "you are here" trail: every part but the last is a link, so any page is one tap away. */
export function Trail({ items }: { items: TrailItem[] }) {
  return (
    <nav className="trail" aria-label="You are here">
      <ol>
        {items.map((item, i) => (
          <li key={item.label + i}>
            {item.href && i < items.length - 1
              ? <Link href={item.href}>{item.label}</Link>
              : <span aria-current="page">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
