import { useState } from 'react';
import {
  ShoppingBag,
  CreditCard,
  Zap,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Lock,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Clock,
} from 'lucide-react';

interface Transaction {
  id: string;
  time: string;
  amount: number;
  status: 'CHARGED' | 'BLOCKED_DUPLICATE';
  idempotencyKey: string;
}

interface AcmeShopSimulatorProps {
  onSendToNeverTwice: (crashLog: string) => void;
  activeRulesCount?: number;
}

export default function AcmeShopSimulator({ onSendToNeverTwice, activeRulesCount = 0 }: AcmeShopSimulatorProps) {
  const [bankBalance, setBankBalance] = useState<number>(500.0);
  const [patchMode, setPatchMode] = useState<'naive' | 'protected'>('naive');
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [alertState, setAlertState] = useState<{
    type: 'success' | 'danger' | 'info' | null;
    message: string;
  }>({
    type: 'info',
    message: 'Storefront loaded. Customer account balance: $500.00. Ready for checkout testing.',
  });

  // Simulated server idempotency cache for protected mode
  const [, setServerProcessedKeys] = useState<Set<string>>(new Set());

  const resetStore = () => {
    setBankBalance(500.0);
    setTransactions([]);
    setServerProcessedKeys(new Set());
    setAlertState({
      type: 'info',
      message: 'Store and customer balance reset to $500.00.',
    });
  };

  // Single nominal checkout
  const handleSinglePayment = async () => {
    setIsProcessing(true);
    const key = `key_${Date.now()}`;
    const now = new Date().toLocaleTimeString();

    if (patchMode === 'naive') {
      setBankBalance((prev) => prev - 50.0);
      setTransactions((prev) => [
        { id: `TX-${Date.now()}`, time: now, amount: 50.0, status: 'CHARGED', idempotencyKey: key },
        ...prev,
      ]);
      setAlertState({
        type: 'success',
        message: 'Nominal checkout successful. Charged $50.00.',
      });
    } else {
      setBankBalance((prev) => prev - 50.0);
      setServerProcessedKeys((prev) => new Set(prev).add(key));
      setTransactions((prev) => [
        { id: `TX-${Date.now()}`, time: now, amount: 50.0, status: 'CHARGED', idempotencyKey: key },
        ...prev,
      ]);
      setAlertState({
        type: 'success',
        message: 'Protected checkout successful. Charged $50.00.',
      });
    }
    setIsProcessing(false);
  };

  // Adversarial Rapid Double-Click Attack (simulating concurrent user retry within 15ms)
  const handleRapidDoubleClick = async () => {
    setIsProcessing(true);
    const sharedKey = `idemp_dup_${Date.now()}`;
    const now = new Date().toLocaleTimeString();

    if (patchMode === 'naive') {
      // NAIVE AGENT CODE: No token check -> Both requests charge customer account!
      setBankBalance((prev) => prev - 100.0);
      setTransactions((prev) => [
        {
          id: `TX-${Date.now()}-A`,
          time: now,
          amount: 50.0,
          status: 'CHARGED',
          idempotencyKey: sharedKey,
        },
        {
          id: `TX-${Date.now()}-B`,
          time: now,
          amount: 50.0,
          status: 'CHARGED',
          idempotencyKey: sharedKey,
        },
        ...prev,
      ]);

      setAlertState({
        type: 'danger',
        message: 'CRITICAL FAILURE: Customer was charged twice ($100.00 total) for a single $50.00 cart!',
      });
    } else {
      // NEVERTWICE PROTECTED CODE: First charge succeeds, second request recognized and rejected!
      setBankBalance((prev) => prev - 50.0);
      setServerProcessedKeys((prev) => new Set(prev).add(sharedKey));
      setTransactions((prev) => [
        {
          id: `TX-${Date.now()}-A`,
          time: now,
          amount: 50.0,
          status: 'CHARGED',
          idempotencyKey: sharedKey,
        },
        {
          id: `TX-${Date.now()}-B`,
          time: now,
          amount: 0.0,
          status: 'BLOCKED_DUPLICATE',
          idempotencyKey: sharedKey,
        },
        ...prev,
      ]);

      setAlertState({
        type: 'success',
        message: 'PROTECTION ACTIVE: Concurrent duplicate click was intercepted and blocked by RULE-PAY-042! Only $50.00 charged.',
      });
    }

    setIsProcessing(false);
  };

  const handleEscalateToNeverTwice = () => {
    const rawCrash = `Traceback (most recent call last):
  File "/app/services/checkout.py", line 42, in process_cart_payment
    raise DuplicateChargeException("Cart charge already in flight for token ${transactions[0]?.idempotencyKey || 'idemp_key_01'}")
DuplicateChargeException: CRITICAL: Rapid duplicate checkout dispatched without idempotency lock. Customer debited $100 instead of $50.`;
    onSendToNeverTwice(rawCrash);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
      {/* Target App Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <ShoppingBag className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-white">AcmeShop Production App</span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 font-mono border border-cyan-500/20">
                Target Under Test
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Live e-commerce checkout simulating the race condition bug
            </p>
            <a
              href="https://acmeshop-358476980823.us-west1.run.app"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-cyan-400 hover:text-cyan-300 underline"
            >
              Open AcmeShop
            </a>
          </div>
        </div>

        {/* Patch Mode Selector */}
        <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setPatchMode('naive')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              patchMode === 'naive'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
            Mode A: Naive Agent Fix (Unprotected)
          </button>
          <button
            onClick={() => setPatchMode('protected')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              patchMode === 'protected'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            Mode B: NeverTwice Patch (Protected)
            {activeRulesCount > 0 && (
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 rounded font-mono ml-1">
                {activeRulesCount} rule active
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Main Store Workspace */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Product & Checkout Card */}
        <div className="col-span-12 md:col-span-6 bg-slate-950 rounded-xl p-5 border border-slate-800 flex flex-col justify-between gap-5">
          <div>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <span className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider">
                  Electronics • In Stock
                </span>
                <h3 className="text-base font-bold text-white mt-0.5">
                  Sony WH-1000XM5 Wireless Headphones
                </h3>
              </div>
              <div className="text-right">
                <div className="text-xl font-extrabold text-white font-mono">$50.00</div>
                <div className="text-[10px] text-slate-500 line-through">$399.00 (Demo Promo)</div>
              </div>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Industry-leading noise canceling headphones with dual processors and 8 microphones.
            </p>
          </div>

          {/* Customer Bank Card Balance Status */}
          <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <CreditCard className="h-4 w-4 text-indigo-400" />
              <div>
                <div className="text-[11px] text-slate-400">Customer Checking Account</div>
                <div className="text-xs font-mono font-bold text-slate-200">
                  Account ending in •••• 8492
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[11px] text-slate-400">Live Balance</div>
              <div
                className={`text-base font-mono font-extrabold ${
                  bankBalance < 450 ? 'text-rose-400' : 'text-emerald-400'
                }`}
              >
                ${bankBalance.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Interactive Trigger Buttons */}
          <div className="flex flex-col gap-2 pt-2">
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={handleSinglePayment}
                disabled={isProcessing || bankBalance < 50}
                className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center justify-center gap-1.5"
              >
                Pay $50.00 (Single Click)
              </button>

              <button
                onClick={handleRapidDoubleClick}
                disabled={isProcessing || bankBalance < 100}
                className={`px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-md ${
                  patchMode === 'naive'
                    ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/30'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/30'
                }`}
              >
                <Zap className="h-3.5 w-3.5" />
                ⚡ Rapid Double-Click
              </button>
            </div>

            <button
              onClick={resetStore}
              className="py-1 text-[11px] text-slate-500 hover:text-slate-300 flex items-center justify-center gap-1 transition-all"
            >
              <RefreshCw className="h-3 w-3" /> Reset Customer Balance to $500.00
            </button>
          </div>
        </div>

        {/* Right: Live Telemetry Ledger & Status Alert */}
        <div className="col-span-12 md:col-span-6 flex flex-col gap-4">
          {/* Status Alert Banner */}
          <div
            className={`p-3.5 rounded-xl border text-xs leading-relaxed flex items-start gap-2.5 ${
              alertState.type === 'danger'
                ? 'bg-rose-950/40 border-rose-800/60 text-rose-200'
                : alertState.type === 'success'
                ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200'
                : 'bg-slate-950 border-slate-800 text-slate-300'
            }`}
          >
            {alertState.type === 'danger' ? (
              <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            ) : alertState.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <Lock className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
            )}
            <div>
              <div className="font-semibold mb-0.5">
                {alertState.type === 'danger'
                  ? 'Race Condition Re-Entrancy Triggered'
                  : alertState.type === 'success'
                  ? 'Invariant Verification Succeeded'
                  : 'Ready'}
              </div>
              <div>{alertState.message}</div>

              {/* Action button when bug triggers */}
              {alertState.type === 'danger' && (
                <button
                  onClick={handleEscalateToNeverTwice}
                  className="mt-2.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-500 hover:bg-rose-400 text-white flex items-center gap-1.5 transition-all shadow-sm"
                >
                  Inspect Crash in NeverTwice Referee <ArrowRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Transaction Ledger Table */}
          <div className="bg-slate-950 rounded-xl p-4 border border-slate-800 flex-1 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-slate-500" />
                Live Payment Ledger (Acme Bank)
              </span>
              <span className="text-[10px] font-mono text-slate-500">
                {transactions.length} record{transactions.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="flex-1 overflow-auto max-h-44 space-y-1.5 font-mono text-[11px]">
              {transactions.length > 0 ? (
                transactions.map((tx) => (
                  <div
                    key={tx.id}
                    className={`p-2 rounded-lg border flex items-center justify-between ${
                      tx.status === 'CHARGED'
                        ? 'bg-slate-900 border-slate-800 text-slate-200'
                        : 'bg-emerald-950/20 border-emerald-800/40 text-emerald-300'
                    }`}
                  >
                    <div>
                      <div className="font-semibold flex items-center gap-1">
                        <span>{tx.id}</span>
                        {tx.status === 'BLOCKED_DUPLICATE' && (
                          <span className="text-[9px] px-1.5 py-0.2 bg-emerald-500/20 text-emerald-400 rounded">
                            BLOCKED
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {tx.time} • key: {tx.idempotencyKey.slice(0, 14)}...
                      </div>
                    </div>
                    <div
                      className={`font-bold ${
                        tx.status === 'CHARGED' ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {tx.status === 'CHARGED' ? `-$${tx.amount.toFixed(2)}` : '$0.00 (Protected)'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-slate-600 text-xs italic py-6 text-center">
                  No payment attempts yet. Click Single Click or Double-Click above.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

