const n = (v: number, cap: number) => Math.min(v / cap, 1);
export const score = (m: any) => Math.round(100 * (
  0.25 * n(m.frequency, 20) + 0.15 * n(m.reach, 5000) + 0.20 * n(m.intensity, 5) +
  0.15 * n(m.wtp_mentions, 10) + 0.10 * n(m.recency_pct_30d, 100) + 0.15 * n(m.gap_strength, 10)));