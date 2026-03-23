import React from "react";

interface BulletListProps {
  items: string[];
  emptyText?: string;
}

export function BulletList({ items, emptyText }: BulletListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-400 italic">{emptyText || "None"}</p>;
  }
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-gray-700">
          <span className="text-ndai-600 mt-0.5">&bull;</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
