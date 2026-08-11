import "./globals.css";
import Link from "next/link";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <Link className="brand" href="/dashboard">
              MCE<small>MARKET DIFF / 0.1</small>
            </Link>
            <nav className="nav">
              <Link className="active" href="/dashboard">Dashboard</Link>
              <Link href="/watchlist">Watchlist</Link>
              <Link href="/calendar">Calendar</Link>
              <Link href="/settings">System</Link>
            </nav>
          </aside>
          {children}
        </div>
      </body>
    </html>
  );
}
