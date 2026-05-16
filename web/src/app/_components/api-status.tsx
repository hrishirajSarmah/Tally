"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "ok" | "down";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/health`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => !cancelled && setStatus(d.status === "ok" ? "ok" : "down"))
      .catch(() => !cancelled && setStatus("down"));
    return () => {
      cancelled = true;
    };
  }, []);

  const color =
    status === "ok"
      ? "bg-green-100 text-green-800 border-green-300"
      : status === "down"
        ? "bg-red-100 text-red-800 border-red-300"
        : "bg-neutral-100 text-neutral-700 border-neutral-300";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-mono ${color}`}
    >
      <span className="inline-block h-2 w-2 rounded-full bg-current opacity-70" />
      API: {status}
      <span className="opacity-60">({API_URL})</span>
    </div>
  );
}
