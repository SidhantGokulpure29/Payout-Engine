import { useEffect, useState } from "react";

import { createPayout, fetchMerchantDashboard } from "../api/client";

const DEFAULT_MERCHANT_ID =
  import.meta.env.VITE_MERCHANT_ID ?? "";

export function useMerchantDashboard() {
  const [merchantId, setMerchantId] = useState(DEFAULT_MERCHANT_ID);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function refreshDashboard(currentMerchantId = merchantId) {
    if (!currentMerchantId) {
      setDashboard(null);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const payload = await fetchMerchantDashboard(currentMerchantId);
      setDashboard(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitPayout({ bankAccountId, amountPaise }) {
    if (!merchantId) {
      setError("Enter a merchant id first.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await createPayout({
        merchantId,
        bankAccountId,
        amountPaise,
      });
      await refreshDashboard(merchantId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!merchantId) {
      return undefined;
    }

    refreshDashboard(merchantId);
    const intervalId = window.setInterval(() => {
      refreshDashboard(merchantId);
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [merchantId]);

  return {
    merchantId,
    setMerchantId,
    dashboard,
    error,
    loading,
    submitting,
    refreshDashboard,
    submitPayout,
  };
}
