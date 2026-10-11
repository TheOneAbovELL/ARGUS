'use client';

// Metric definitions come from the backend (/api/meta/metrics) so the UI
// explains each number with exactly the convention the engine uses.

import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';
import type { MetricDefinition } from './types';

const MetricsContext = createContext<Record<string, MetricDefinition>>({});

export function MetricDefinitionsProvider({ children }: { children: React.ReactNode }) {
  const [definitions, setDefinitions] = useState<Record<string, MetricDefinition>>({});
  useEffect(() => {
    api
      .metricDefinitions()
      .then((list) => setDefinitions(Object.fromEntries(list.map((d) => [d.key, d]))))
      .catch(() => setDefinitions({})); // tooltips are optional; the numbers still render
  }, []);
  return <MetricsContext.Provider value={definitions}>{children}</MetricsContext.Provider>;
}

export function useMetricDefinition(key: string | undefined): MetricDefinition | undefined {
  const definitions = useContext(MetricsContext);
  return key ? definitions[key] : undefined;
}

export function useMetricDefinitions(): Record<string, MetricDefinition> {
  return useContext(MetricsContext);
}
