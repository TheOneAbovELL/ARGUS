'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navbar() {
  const pathname = usePathname();
  const navLinks = [
    { name: 'Home', path: '/' },
    { name: 'Analyze', path: '/analyze' },
    { name: 'Portfolio', path: '/portfolio' },
    { name: 'Research', path: '/research' },
  ];

  return (
    <nav className="bg-argus-surface border-b border-argus-border p-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link href="/" className="flex items-center space-x-2">
          <span className="text-2xl font-bold text-argus-accent tracking-widest font-mono">ARGUS</span>
        </Link>
        <div className="flex space-x-6">
          {navLinks.map((link) => (
            <Link 
              key={link.path} 
              href={link.path}
              className={`font-mono text-sm uppercase tracking-wider hover:text-argus-accent transition-colors ${
                pathname === link.path ? 'text-argus-accent border-b border-argus-accent pb-1' : 'text-argus-muted'
              }`}
            >
              {link.name}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
