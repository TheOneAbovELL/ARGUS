import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  isPercentage?: boolean;
}

export default function MetricCard({ title, value, subtitle, isPercentage }: MetricCardProps) {
  let displayValue = String(value);
  if (typeof value === 'number') {
    if (isPercentage) {
      displayValue = (value * 100).toFixed(2) + '%';
    } else {
      displayValue = value.toFixed(4);
    }
  }

  return (
    <div className="bg-argus-surface border border-argus-border rounded-lg p-4 font-mono flex flex-col justify-between h-full">
      <div className="text-argus-muted text-sm uppercase tracking-wider mb-2">{title}</div>
      <div className="text-2xl text-argus-accent font-bold mb-1">{displayValue}</div>
      {subtitle && <div className="text-xs text-argus-muted">{subtitle}</div>}
    </div>
  );
}
