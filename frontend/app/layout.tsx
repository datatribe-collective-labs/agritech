import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import "./globals.css";

const display = localFont({
  src: "./fonts/bricolage-grotesque-latin-wght-normal.woff2",
  variable: "--font-display",
  weight: "200 800",
  display: "swap",
});
const body = localFont({
  src: "./fonts/figtree-latin-wght-normal.woff2",
  variable: "--font-body",
  weight: "300 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Planting Intelligence", template: "%s · Planting Intelligence" },
  description: "Choose your city and see which crops suit its soil and climate, and which ones grow well together.",
};
export const viewport: Viewport = { themeColor: "#2c7a4b", width: "device-width", initialScale: 1 };

function Logo() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <path d="M16 26V14" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M16 15c0-5 3-8 8-8 0 5-3 8-8 8Zm0 4c0-4-2.5-6.5-7-6.5 0 4 2.5 6.5 7 6.5Z" fill="#f6c453" />
    </svg>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <header className="topbar">
          <Link className="brand" href="/" aria-label="Planting Intelligence, home">
            <Logo />
            <span>Planting Intelligence</span>
          </Link>
          <Link className="about-link" href="/about">About the data</Link>
        </header>
        <main id="main" tabIndex={-1}>{children}</main>
        <footer className="foot">
          <p>Planting Intelligence helps smallholder farmers choose what to plant. Scores are guides, not yield forecasts.</p>
          <p><Link href="/">Cities</Link> · <Link href="/about">About the data</Link></p>
        </footer>
      </body>
    </html>
  );
}
