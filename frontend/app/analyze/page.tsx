'use client';

// Legacy route: single-asset analysis now lives on the asset page.
// Kept so existing links and bookmarks keep working.

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Spinner } from '@/components/ui';

function Redirect() {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => {
    const symbol = params.get('symbol') ?? params.get('ticker');
    router.replace(symbol ? `/asset?symbol=${encodeURIComponent(symbol)}&tab=analytics` : '/asset');
  }, [params, router]);
  return <Spinner label="Opening asset analytics" />;
}

export default function AnalyzeRedirect() {
  return (
    <Suspense fallback={null}>
      <Redirect />
    </Suspense>
  );
}
