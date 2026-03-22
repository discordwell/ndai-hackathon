import React from "react";

const SCRIPT_TYPES = ["bash", "python3", "html", "powershell"] as const;
type ScriptType = (typeof SCRIPT_TYPES)[number];

const MAX_SIZE_BYTES = 256 * 1024; // 256 KB

interface Props {
  value: string;
  scriptType: ScriptType;
  onValueChange: (value: string) => void;
  onScriptTypeChange: (type: ScriptType) => void;
}

export function PoCEditor({ value, scriptType, onValueChange, onScriptTypeChange }: Props) {
  const lineCount = value.split("\n").length;
  const byteCount = new TextEncoder().encode(value).length;
  const overLimit = byteCount > MAX_SIZE_BYTES;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-[11px] text-gray-500">PoC Script</label>
        <select
          value={scriptType}
          onChange={(e) => onScriptTypeChange(e.target.value as ScriptType)}
          className="px-2 py-1 bg-surface-800 border border-surface-700 rounded text-[11px] text-white outline-none focus:border-accent-500/50"
        >
          {SCRIPT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="relative bg-surface-900 border border-surface-700 rounded-lg overflow-hidden">
        {/* Line numbers */}
        <div className="absolute left-0 top-0 bottom-0 w-10 bg-surface-900 border-r border-surface-700/50 pointer-events-none overflow-hidden">
          <div className="pt-3 px-1 text-right">
            {Array.from({ length: lineCount }, (_, i) => (
              <div
                key={i}
                className="text-[11px] leading-[1.625rem] text-gray-600 font-mono select-none"
              >
                {i + 1}
              </div>
            ))}
          </div>
        </div>

        <textarea
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          spellCheck={false}
          className="w-full min-h-[240px] pl-12 pr-3 py-3 bg-transparent text-sm text-white font-mono outline-none resize-y leading-[1.625rem]"
          placeholder="#!/bin/bash&#10;# Your PoC script here..."
        />
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <span className="text-gray-600">{lineCount} lines</span>
        <span className={overLimit ? "text-danger-400 font-medium" : "text-gray-600"}>
          {(byteCount / 1024).toFixed(1)} KB / 256 KB
        </span>
      </div>
    </div>
  );
}
