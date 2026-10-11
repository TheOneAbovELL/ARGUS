import type { Metadata, Viewport } from 'next';
import './globals.css';
import AppShell from '@/components/AppShell';
import { AuthProvider } from '@/lib/auth';
import { MetricDefinitionsProvider } from '@/lib/metrics';
import { SystemProvider } from '@/lib/system';

export const metadata: Metadata = {
  title: 'ARGUS — Quantitative Research Terminal',
  description: 'Evidence-grounded quantitative research: market data, risk analytics, portfolios and cited research reports.',
};

export const viewport: Viewport = {
  themeColor: '#090b0e',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">
        <SystemProvider>
          <AuthProvider>
            <MetricDefinitionsProvider>
              <AppShell>{children}</AppShell>
            </MetricDefinitionsProvider>
          </AuthProvider>
        </SystemProvider>
      </body>
    </html>
  );
}
