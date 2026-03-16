import React from "react";
import { InventionForm } from "../../components/seller/InventionForm";

export function InventionCreatePage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Submit New Invention</h1>
      <InventionForm onSuccess={() => (window.location.hash = "#/seller/inventions")} />
    </div>
  );
}
