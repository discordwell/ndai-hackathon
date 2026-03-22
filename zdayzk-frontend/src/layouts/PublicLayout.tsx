import React from "react";

export function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-950 flex flex-col">
      <header className="px-6 py-4">
        <a
          href="#/"
          className="text-xl font-mono font-bold tracking-wider text-accent-400 hover:text-accent-300 transition-colors"
        >
          zdayzk
        </a>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        {children}
      </main>
    </div>
  );
}
