'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { FlaskConical, LogOut, Menu, Settings, User as UserIcon, X } from 'lucide-react';
import SymbolSearch from './SymbolSearch';
import { useAuth } from '@/lib/auth';
import { useSystem } from '@/lib/system';

const NAV = [
  { href: '/', label: 'Overview' },
  { href: '/asset', label: 'Asset' },
  { href: '/portfolio', label: 'Portfolio' },
  { href: '/research', label: 'Research' },
  { href: '/documents', label: 'Documents' },
];

function isActive(pathname: string, href: string): boolean {
  const path = pathname.replace(/\/$/, '') || '/';
  return href === '/' ? path === '/' : path === href || path.startsWith(`${href}/`);
}

function StatusIndicator() {
  const { status, reachable } = useSystem();
  if (reachable === null) return <span className="text-2xs text-ink-faint">connecting…</span>;
  if (!reachable)
    return (
      <Link href="/settings" className="chip border-down/40 bg-down/10 text-down" title="The backend is not reachable">
        <span className="h-1.5 w-1.5 rounded-full bg-down" aria-hidden /> Offline
      </Link>
    );
  const fixture = status?.market_data.mode === 'fixture';
  return (
    <Link
      href="/settings"
      className={`chip whitespace-nowrap ${fixture ? 'border-synthetic/40 bg-synthetic/10 text-synthetic' : 'border-line bg-raised text-ink-muted'}`}
      title={status?.market_data.note}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${fixture ? 'bg-synthetic' : 'bg-up'}`} aria-hidden />
      {fixture ? 'Synthetic data' : 'Delayed data'}
    </Link>
  );
}

function AccountMenu() {
  const { user, status, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  if (status === 'loading') return <span className="h-7 w-16" />;
  if (!user)
    return (
      <Link href="/login" className="btn-ghost whitespace-nowrap px-2.5 py-1 text-xs">
        <UserIcon className="h-3.5 w-3.5" aria-hidden /> Sign in
      </Link>
    );
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="btn-ghost max-w-[11rem] px-2.5 py-1 text-xs"
      >
        <UserIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{user.display_name || user.email}</span>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-1 w-48 rounded border border-line bg-raised py-1 shadow-xl shadow-black/40">
          <p className="truncate px-3 py-1.5 text-2xs text-ink-faint">{user.email}</p>
          <Link role="menuitem" href="/settings" className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-bg">
            <Settings className="h-3.5 w-3.5" aria-hidden /> Settings
          </Link>
          <button
            role="menuitem"
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={async () => {
              setOpen(false);
              await logout();
              router.push('/');
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-bg"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || '/';
  const router = useRouter();
  const { status } = useSystem();
  const [mobileOpen, setMobileOpen] = useState(false);
  const fixture = status?.market_data.mode === 'fixture';

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-1 focus:text-bg">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1440px] items-center gap-4 px-4">
          <Link href="/" className="flex items-center gap-2" aria-label="ARGUS home">
            <span className="grid h-6 w-6 place-items-center rounded-sm bg-accent text-[11px] font-black text-bg">A</span>
            <span className="text-sm font-bold tracking-[0.25em] text-ink">ARGUS</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(pathname, item.href) ? 'page' : undefined}
                className={`rounded px-2.5 py-1 text-sm transition-colors ${
                  isActive(pathname, item.href) ? 'bg-raised text-ink' : 'text-ink-muted hover:text-ink'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <SymbolSearch shortcut className="ml-auto hidden w-56 md:block lg:w-72" />
          <div className="hidden items-center gap-2 md:flex">
            <StatusIndicator />
            <AccountMenu />
          </div>
          <button
            type="button"
            className="btn-ghost ml-auto px-2 py-1 md:hidden"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((o) => !o)}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
        {mobileOpen && (
          <div className="space-y-3 border-t border-line px-4 py-3 md:hidden">
            <SymbolSearch
              onSelect={(s) => {
                setMobileOpen(false);
                router.push(`/asset?symbol=${encodeURIComponent(s)}`);
              }}
            />
            <nav className="grid grid-cols-2 gap-1" aria-label="Main mobile">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} onClick={() => setMobileOpen(false)} className="rounded px-2 py-1.5 text-sm text-ink-muted hover:bg-raised hover:text-ink">
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="flex items-center gap-2">
              <StatusIndicator />
              <AccountMenu />
            </div>
          </div>
        )}
        {fixture && (
          <div className="border-t border-synthetic/30 bg-synthetic/10 px-4 py-1 text-center text-2xs text-synthetic">
            <FlaskConical className="mr-1 inline h-3 w-3" aria-hidden />
            Offline fixture mode: all prices are deterministic synthetic data for development, not market prices.
          </div>
        )}
      </header>
      <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5">
        {children}
      </main>
      <footer className="border-t border-line px-4 py-3 text-center text-2xs text-ink-faint">
        ARGUS is a research tool, not investment advice. Free market data may be delayed, incomplete or unavailable; metrics are historical.
      </footer>
    </div>
  );
}
