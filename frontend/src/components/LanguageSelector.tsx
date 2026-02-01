"use client";

import { TRANSLATION_MODES } from "@/lib/constants";
import type { TranslationMode } from "@/types";

interface LanguageSelectorProps {
  value: TranslationMode;
  onChange: (mode: TranslationMode) => void;
  disabled?: boolean;
}

export function LanguageSelector({
  value,
  onChange,
  disabled = false,
}: LanguageSelectorProps) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-gray-700">번역 모드</label>
      <div className="flex gap-2">
        {TRANSLATION_MODES.map((mode) => (
          <button
            key={mode.value}
            onClick={() => onChange(mode.value as TranslationMode)}
            disabled={disabled}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium
              transition-all duration-200
              ${
                value === mode.value
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }
              ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
            `}
            title={mode.description}
          >
            {mode.label}
          </button>
        ))}
      </div>
    </div>
  );
}
