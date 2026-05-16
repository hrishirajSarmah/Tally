import { ApiStatus } from "./_components/api-status";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-8 font-sans">
      <h1 className="text-3xl font-semibold">Tally Portal</h1>
      <p className="text-sm text-neutral-500">Goal Setting & Tracking — bootstrap</p>
      <ApiStatus />
    </main>
  );
}
