import "./globals.css";
import Link from "next/link";
import Navigation from "./Navigation";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="sidebar-inner"><Link className="brand" href="/dashboard">MCE<small>MARKET DIFF / 0.1</small></Link></div>
            <Navigation />
          </aside>
          {children}
        </div>
      </body>
    </html>
  );
}
