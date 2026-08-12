import "./globals.css";
import Link from "next/link";
import Navigation from "./Navigation";
import LanguageToggle from "./LanguageToggle";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="sidebar-inner"><Link className="brand" href="/dashboard">MCE<small>市場變化 / 0.1</small></Link><LanguageToggle /></div>
            <Navigation />
          </aside>
          {children}
        </div>
      </body>
    </html>
  );
}
