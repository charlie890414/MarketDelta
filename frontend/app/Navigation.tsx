"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [["Dashboard", "/dashboard"], ["Watchlist", "/watchlist"], ["Calendar", "/calendar"], ["System", "/settings"]] as const;

export default function Navigation() {
  const pathname = usePathname();
  return <nav className="nav" aria-label="Primary navigation">{links.map(([label, href]) => <Link className={pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`)) ? "active" : ""} href={href} key={href}>{label}</Link>)}</nav>;
}
