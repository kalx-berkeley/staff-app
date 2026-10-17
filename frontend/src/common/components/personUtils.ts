/**
 * Pulls the email out of "Name (email@example.com)" (as produced by picking a
 * suggestion), or returns the input as-is. Normalizes to lowercase so
 * differently-cased entries for the same person don't end up as duplicates.
 */
export const extractPersonEmail = (input: string): string => {
  const trimmed = input.trim();
  const match = trimmed.match(/\(([^()]+)\)\s*$/);
  return (match ? match[1] : trimmed).trim().toLowerCase();
};
