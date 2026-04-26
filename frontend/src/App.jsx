import { useState } from "react";

import { useMerchantDashboard } from "./hooks/useMerchantDashboard";

function formatPaise(amountPaise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(amountPaise / 100);
}

function maskAccountNumber(accountNumber) {
  return `**** ${accountNumber.slice(-4)}`;
}

export default function App() {
  const {
    merchantId,
    setMerchantId,
    dashboard,
    error,
    loading,
    submitting,
    refreshDashboard,
    submitPayout,
  } = useMerchantDashboard();
  const [amountPaise, setAmountPaise] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");

  const selectedBankAccountId =
    bankAccountId || dashboard?.bank_accounts?.[0]?.id || "";

  async function handleSubmit(event) {
    event.preventDefault();
    await submitPayout({
      bankAccountId: selectedBankAccountId,
      amountPaise: Number(amountPaise),
    });
    setAmountPaise("");
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="relative overflow-hidden rounded-[32px] bg-gradient-to-br from-cream via-[#f4e6d4] to-[#ead8c0] p-8 shadow-card animate-floatIn">
          <div className="absolute -right-16 top-0 h-40 w-40 rounded-full bg-coral/20 blur-3xl" />
          <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-moss/20 blur-3xl" />
          <div className="relative grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.3em] text-moss">
                Playto Pay
              </p>
              <h1 className="mt-3 font-display text-4xl leading-tight text-ink sm:text-5xl">
                Merchant payout cockpit for money that cannot be wrong.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate">
                Track available balance, held funds, payout attempts, and recent
                ledger movement from one place. This dashboard polls every five
                seconds so payout status changes show up without a refresh.
              </p>
            </div>

            <div className="rounded-[28px] border border-white/60 bg-white/70 p-5 backdrop-blur">
              <label className="block text-sm font-semibold text-ink">
                Merchant ID
              </label>
              <input
                className="mt-2 w-full rounded-2xl border border-[#d6c1a4] bg-white px-4 py-3 text-sm outline-none transition focus:border-coral"
                placeholder="Paste merchant UUID"
                value={merchantId}
                onChange={(event) => setMerchantId(event.target.value)}
              />
              <button
                className="mt-4 w-full rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#111827]"
                onClick={() => refreshDashboard()}
                type="button"
              >
                Load dashboard
              </button>
              {error ? (
                <p className="mt-3 rounded-2xl bg-[#fff1ec] px-4 py-3 text-sm text-[#9f3a22]">
                  {error}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-3">
          <article className="rounded-[28px] bg-white p-6 shadow-card animate-floatIn">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
              Available
            </p>
            <p className="mt-3 font-display text-4xl text-ink">
              {dashboard
                ? formatPaise(dashboard.balance.available_balance_paise)
                : "--"}
            </p>
            <p className="mt-2 text-sm text-slate">
              Money that can be withdrawn right now.
            </p>
          </article>

          <article className="rounded-[28px] bg-[#fff8ef] p-6 shadow-card animate-floatIn">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
              Held
            </p>
            <p className="mt-3 font-display text-4xl text-coral">
              {dashboard ? formatPaise(dashboard.balance.held_balance_paise) : "--"}
            </p>
            <p className="mt-2 text-sm text-slate">
              Funds reserved for payouts that are still settling.
            </p>
          </article>

          <article className="rounded-[28px] bg-[#eff5f0] p-6 shadow-card animate-floatIn">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
              Merchant
            </p>
            <p className="mt-3 font-display text-3xl text-moss">
              {dashboard?.merchant_name ?? "Load a merchant"}
            </p>
            <p className="mt-2 text-sm text-slate">
              Use the seeded merchant UUID from the backend to test the flow.
            </p>
          </article>
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <article className="rounded-[30px] bg-white p-6 shadow-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
                  Request payout
                </p>
                <h2 className="mt-2 font-display text-3xl text-ink">
                  Move funds to bank
                </h2>
              </div>
              {loading ? (
                <span className="rounded-full bg-[#efe7da] px-3 py-1 text-xs font-semibold text-moss">
                  Refreshing
                </span>
              ) : null}
            </div>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="block text-sm font-semibold text-ink">
                  Bank account
                </label>
                <select
                  className="mt-2 w-full rounded-2xl border border-[#d6c1a4] bg-white px-4 py-3 text-sm outline-none focus:border-coral"
                  value={selectedBankAccountId}
                  onChange={(event) => setBankAccountId(event.target.value)}
                >
                  {dashboard?.bank_accounts?.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_holder_name} -{" "}
                      {maskAccountNumber(account.account_number)}
                    </option>
                  )) ?? <option value="">Load merchant first</option>}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-ink">
                  Amount in paise
                </label>
                <input
                  className="mt-2 w-full rounded-2xl border border-[#d6c1a4] bg-white px-4 py-3 text-sm outline-none focus:border-coral"
                  min="1"
                  placeholder="2500"
                  type="number"
                  value={amountPaise}
                  onChange={(event) => setAmountPaise(event.target.value)}
                />
              </div>

              <button
                className="w-full rounded-2xl bg-coral px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#c56243] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!selectedBankAccountId || !amountPaise || submitting}
                type="submit"
              >
                {submitting ? "Submitting..." : "Create payout request"}
              </button>
            </form>
          </article>

          <article className="rounded-[30px] bg-white p-6 shadow-card">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
              Recent ledger
            </p>
            <h2 className="mt-2 font-display text-3xl text-ink">
              Credits, holds, releases, debits
            </h2>
            <div className="mt-6 space-y-3">
              {dashboard?.recent_ledger_entries?.length ? (
                dashboard.recent_ledger_entries.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between rounded-2xl bg-[#faf6ef] px-4 py-4"
                  >
                    <div>
                      <p className="text-sm font-semibold capitalize text-ink">
                        {entry.entry_type}
                      </p>
                      <p className="text-sm text-slate">{entry.description}</p>
                    </div>
                    <p className="text-sm font-semibold text-moss">
                      {formatPaise(entry.amount_paise)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="rounded-2xl bg-[#faf6ef] px-4 py-6 text-sm text-slate">
                  Load a merchant to see ledger entries.
                </p>
              )}
            </div>
          </article>
        </section>

        <section className="mt-8 rounded-[30px] bg-white p-6 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate">
                Payout history
              </p>
              <h2 className="mt-2 font-display text-3xl text-ink">
                Live status feed
              </h2>
            </div>
            <p className="rounded-full bg-[#eff5f0] px-4 py-2 text-xs font-semibold text-moss">
              Polling every 5 seconds
            </p>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-y-3">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.2em] text-slate">
                  <th className="pb-2">Payout</th>
                  <th className="pb-2">Bank</th>
                  <th className="pb-2">Amount</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Attempts</th>
                </tr>
              </thead>
              <tbody>
                {dashboard?.payouts?.length ? (
                  dashboard.payouts.map((payout) => (
                    <tr key={payout.id} className="rounded-2xl bg-[#faf6ef]">
                      <td className="rounded-l-2xl px-4 py-4 text-sm text-ink">
                        <div className="font-semibold">{payout.id.slice(0, 8)}...</div>
                        <div className="text-slate">{payout.created_at}</div>
                      </td>
                      <td className="px-4 py-4 text-sm text-ink">
                        {payout.bank_account.account_holder_name}
                      </td>
                      <td className="px-4 py-4 text-sm font-semibold text-ink">
                        {formatPaise(payout.amount_paise)}
                      </td>
                      <td className="px-4 py-4 text-sm">
                        <span className="rounded-full bg-[#efe7da] px-3 py-1 font-semibold capitalize text-moss">
                          {payout.status}
                        </span>
                      </td>
                      <td className="rounded-r-2xl px-4 py-4 text-sm text-ink">
                        {payout.attempt_count}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      className="rounded-2xl bg-[#faf6ef] px-4 py-6 text-sm text-slate"
                      colSpan="5"
                    >
                      Load a merchant and create a payout to watch statuses move.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
