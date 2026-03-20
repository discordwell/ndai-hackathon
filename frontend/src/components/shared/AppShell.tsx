import React from "react";
import { Sidebar } from "./Sidebar";
import { FeatureNav } from "./FeatureNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col min-h-screen">
      <FeatureNav />
      <div className="flex flex-1 bg-gray-50">
        <Sidebar />
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
