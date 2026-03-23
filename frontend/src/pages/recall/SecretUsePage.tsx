import React, { useEffect, useRef, useState } from "react";
import { getSecret, useSecret, SecretResponse, SecretUseResponse } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import { PolicyDisplay } from "../../components/shared/PolicyDisplay";
import { EgressLogDisplay } from "../../components/shared/EgressLogDisplay";

interface Props {
  id: string;
}

const TEE_STAGES = [
  "Validating action against policy",
  "Generating policy constraints via LLM",
  "Executing action inside TEE",
  "Enforcing policy deterministically",
  "Building verification chain",
  "Clearing sensitive data",
];

function TeeProgressStepper({ activeStep }: { activeStep: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <h2 className="font-semibold text-gray-900 mb-4">TEE Session in Progress</h2>
      <div className="space-y-3">
        {TEE_STAGES.map((stage, i) => {
          const isActive = i === activeStep;
          const isDone = i < activeStep;
          return (
            <div key={i} className="flex items-center gap-3">
              <div className="shrink-0 w-6 h-6 flex items-center justify-center">
                {isDone ? (
                  <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                ) : isActive ? (
                  <div className="w-5 h-5 rounded-full bg-ndai-500 animate-pulse" />
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-gray-200" />
                )}
              </div>
              <span
                className={`text-sm ${
                  isDone ? "text-green-700 font-medium" :
                  isActive ? "text-ndai-700 font-medium" :
                  "text-gray-400"
                }`}
              >
                {stage}{isActive ? "..." : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SecretUsePage({ id }: Props) {
  const [secret, setSecret] = useState<SecretResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SecretUseResponse | null>(null);
  const [useError, setUseError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [stepperStep, setStepperStep] = useState(0);
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getSecret(id)
      .then(setSecret)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load secret"))
      .finally(() => setLoading(false));
  }, [id]);

  // Cleanup step timer on unmount
  useEffect(() => {
    return () => {
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    };
  }, []);

  function startStepper() {
    setStepperStep(0);
    let step = 0;
    stepTimerRef.current = setInterval(() => {
      step++;
      if (step < TEE_STAGES.length) {
        setStepperStep(step);
      } else {
        if (stepTimerRef.current) clearInterval(stepTimerRef.current);
      }
    }, 1200);
  }

  function stopStepper() {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    setStepperStep(TEE_STAGES.length);
  }

  async function handleConfirmedUse() {
    setSubmitting(true);
    setConfirming(false);
    setUseError("");
    setResult(null);
    startStepper();
    try {
      const res = await useSecret(id, action);
      stopStepper();
      setResult(res);
      // Refresh secret to get updated uses_remaining
      const updated = await getSecret(id);
      setSecret(updated);
    } catch (err: any) {
      stopStepper();
      setUseError(err.detail || err.message || "Failed to use secret");
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setConfirming(true);
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!secret) return null;

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <a href="#/recall/browse" className="text-sm text-ndai-600 hover:underline">
          &larr; Back to Browse
        </a>
        <h1 className="text-2xl font-bold mt-2">{secret.name}</h1>
        {secret.description && (
          <p className="text-gray-500 mt-1">{secret.description}</p>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Policy</h2>
        <div className="space-y-2 text-sm text-gray-700">
          <div className="flex justify-between">
            <span className="text-gray-500">Status</span>
            <span
              className={`font-medium ${secret.status === "active" ? "text-green-600" : "text-gray-600"}`}
            >
              {secret.status}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Uses remaining</span>
            <span className="font-medium">{secret.uses_remaining}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Allowed actions</span>
            <span className="font-medium">
              {secret.policy.allowed_actions.length > 0
                ? secret.policy.allowed_actions.join(", ")
                : "any"}
            </span>
          </div>
        </div>
      </div>

      {submitting ? (
        <TeeProgressStepper activeStep={stepperStep} />
      ) : result ? (
        <>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Result</h2>
            <div
              className={`p-3 rounded-lg text-sm mb-3 ${
                result.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"
              }`}
            >
              {result.success ? "Action executed successfully inside TEE" : "Action failed"}
            </div>
            <div className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 font-mono">
              {result.result}
            </div>
            {result.attestation_available && (
              <p className="mt-3 text-xs text-gray-500">
                This result was produced inside a Trusted Execution Environment with full cryptographic verification.
              </p>
            )}
            <button
              onClick={() => { setResult(null); setAction(""); }}
              className="mt-4 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
            >
              Use Again
            </button>
          </div>
          <div className="mt-6 space-y-4">
            <PolicyDisplay report={result.policy_report} constraints={result.policy_constraints} />
            <VerificationPanel verification={result.verification} />
            <EgressLogDisplay entries={result.egress_log} />
          </div>
        </>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Request Access</h2>
          {useError && (
            <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">{useError}</div>
          )}

          {confirming ? (
            <div className="space-y-4">
              <div className="bg-ndai-50 border border-ndai-200 rounded-lg p-4">
                <p className="text-sm text-ndai-800 font-medium mb-1">Confirm TEE Execution</p>
                <p className="text-sm text-ndai-700">
                  This will consume <strong>1 of {secret.uses_remaining}</strong> remaining uses.
                  The action will run inside a Trusted Execution Environment and produce a
                  cryptographic verification chain.
                </p>
                <p className="text-xs text-ndai-600 mt-2">
                  Action: <span className="font-medium">{action}</span>
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleConfirmedUse}
                  className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm"
                >
                  Confirm &amp; Execute
                </button>
                <button
                  onClick={() => setConfirming(false)}
                  className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Action</label>
                {secret.policy.allowed_actions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {secret.policy.allowed_actions.map((a) => (
                      <button
                        key={a}
                        type="button"
                        onClick={() => setAction(a)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                          action === a
                            ? "bg-ndai-600 text-white border-ndai-600"
                            : "bg-white text-gray-700 border-gray-300 hover:border-ndai-400 hover:text-ndai-700"
                        }`}
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  required
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  rows={3}
                  placeholder={
                    secret.policy.allowed_actions.length > 0
                      ? "Select an action above or type a custom one"
                      : "Describe what you want to do with this secret"
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm resize-none"
                />
              </div>
              <button
                type="submit"
                disabled={!action.trim()}
                className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm"
              >
                Request Access
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
