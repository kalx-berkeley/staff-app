import { useRef, useState } from 'react';
import { showsAPI } from '../api';
import type { DescriptionAnalysis } from '../types';

export interface DescriptionCheck {
  /** The latest analysis, or null before a check or after a failed one. */
  analysis: DescriptionAnalysis | null;
  /** True while a check is running. */
  analyzing: boolean;
  /** True once the user has closed the warning for the current text. */
  dismissed: boolean;
  dismiss: () => void;
  /** Check `text` for non-value-neutral language. Call it when the field loses focus. */
  check: (text: string) => Promise<void>;
}

/**
 * Runs the on-air description language check and keeps its result. Pair it
 * with `DescriptionCheckFeedback` to show the result under the field.
 */
export const useDescriptionCheck = (): DescriptionCheck => {
  const [analysis, setAnalysis] = useState<DescriptionAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  // The exact text last sent for analysis, so leaving the field without
  // changing anything does not re-run the check.
  const analyzedText = useRef<string | null>(null);

  const check = async (rawText: string) => {
    const text = rawText.trim();
    if (text === analyzedText.current) return;
    analyzedText.current = text;
    setDismissed(false);
    if (!text) {
      setAnalysis(null);
      return;
    }
    setAnalyzing(true);
    try {
      const result = await showsAPI.analyzeDescription(text);
      // Drop the result if the description changed while we were waiting.
      if (analyzedText.current === text) {
        setAnalysis(result);
      }
    } catch {
      // The check is advisory, so a failure must never get in the way of
      // writing or saving the form.
      setAnalysis(null);
    } finally {
      setAnalyzing(false);
    }
  };

  return { analysis, analyzing, dismissed, dismiss: () => setDismissed(true), check };
};
