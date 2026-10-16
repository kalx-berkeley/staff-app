import type { DescriptionFindingCategory } from '../types';
import type { DescriptionCheck } from './useDescriptionCheck';

/** Short label shown beside each finding in the on-air description warning. */
const FINDING_CATEGORY_LABELS: Record<DescriptionFindingCategory, string> = {
  terminology: 'Wrong term',
  call_to_action: 'Call to action',
  comparative: 'Comparative claim',
  endorsement: 'Endorsement',
  hype: 'Station hype',
  emphasis: 'Emphasis',
  subjective: 'Opinion',
};

interface DescriptionCheckFeedbackProps {
  check: DescriptionCheck;
  /** What the form saves, for the disclaimer ("show", "venue"). */
  savedItem: string;
}

/** Shows the result of `useDescriptionCheck` under an on-air description field. */
const DescriptionCheckFeedback = ({ check, savedItem }: DescriptionCheckFeedbackProps) => {
  const { analysis, analyzing, dismissed, dismiss } = check;

  // Overall enthusiasm counts as a warning on its own: the wording can read as
  // promotional even when no single phrase is quotable.
  const hasLanguageWarning =
    !!analysis && (analysis.findings.length > 0 || analysis.reads_promotional);

  // Several findings usually share one piece of advice, so only spell it out
  // the first time it comes up.
  const seenSuggestions = new Set<string>();
  const languageFindings = (analysis?.findings ?? []).map((finding) => {
    const showSuggestion = !seenSuggestions.has(finding.suggestion);
    seenSuggestions.add(finding.suggestion);
    return { finding, showSuggestion };
  });

  return (
    <>
      {analyzing && (
        <span className="field-help">
          Checking the description for non-value-neutral language...
        </span>
      )}
      {!analyzing && analysis && !hasLanguageWarning && (
        <span className="field-help">
          No non-value-neutral language detected.
        </span>
      )}
      {analysis && hasLanguageWarning && !dismissed && (
        <div className="description-warning" role="status">
          <div className="description-warning-header">
            <strong>This description may not be value neutral</strong>
            <button
              type="button"
              className="description-warning-dismiss"
              onClick={dismiss}
              aria-label="Dismiss description warning"
            >
              &times;
            </button>
          </div>
          <p className="description-warning-summary">{analysis.summary}</p>
          {languageFindings.length > 0 && (
            <ul className="description-warning-findings">
              {languageFindings.map(({ finding, showSuggestion }) => (
                <li key={`${finding.start}-${finding.category}`}>
                  <span className={`finding-tag finding-${finding.category}`}>
                    {FINDING_CATEGORY_LABELS[finding.category]}
                  </span>{' '}
                  {finding.message}
                  {showSuggestion && (
                    <>
                      {' '}
                      <span className="description-warning-suggestion">
                        {finding.suggestion}
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="description-warning-disclaimer">
            This assessment is automated and it can be wrong &mdash; band names,
            genre words and plain factual wording sometimes trip it. If the
            description reads fine as written, ignore this warning. It does not
            stop you from saving the {savedItem}.
          </p>
        </div>
      )}
    </>
  );
};

export default DescriptionCheckFeedback;
