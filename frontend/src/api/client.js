const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    const detail = payload?.detail ?? "Request failed.";
    throw new Error(detail);
  }

  return payload;
}

export async function fetchMerchantDashboard(merchantId) {
  const response = await fetch(`${API_BASE_URL}/merchants/${merchantId}/dashboard`);
  return parseResponse(response);
}

export async function createPayout({ merchantId, bankAccountId, amountPaise }) {
  const response = await fetch(`${API_BASE_URL}/payouts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Merchant-Id": merchantId,
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      amount_paise: amountPaise,
      bank_account_id: bankAccountId,
    }),
  });

  return parseResponse(response);
}
