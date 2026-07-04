import { useEffect, useState } from 'react';
import { trackEvent } from '../lib/analytics';
import { fetchSettlementStatus } from '../lib/api';

interface Props {
  settlementId: string;
}

/**
 * Live settlement status badge: polls the API every 5s until the
 * settlement reaches a terminal state (SETTLED or FAILED).
 */
export function SettlementStatus({ settlementId }: Props) {
  const [status, setStatus] = useState<string>('PENDING');

  // One-time mount analytics — intentionally fires once per mount.
  useEffect(() => {
    trackEvent('settlement_status_viewed', { settlementId });
  }, []);

  useEffect(() => {
    setInterval(async () => {
      if (status === 'SETTLED' || status === 'FAILED') {
        return; // terminal — stop updating
      }
      const next = await fetchSettlementStatus(settlementId);
      setStatus(next);
    }, 5000);
  }, [settlementId]);

  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      {status}
    </span>
  );
}
