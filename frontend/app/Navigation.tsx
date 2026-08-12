"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [["儀表板", "/dashboard"], ["自選清單", "/watchlist"], ["行事曆", "/calendar"], ["系統", "/settings"]] as const;

export default function Navigation() {
  const pathname = usePathname();
  return <nav className="nav" aria-label="主要導覽">{links.map(([label, href]) => <Link className={pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`)) ? "active" : ""} href={href} key={href}>{label}</Link>)}</nav>;
}
