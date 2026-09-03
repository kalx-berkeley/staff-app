export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return '—';
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return phone;
}

// Matches "stage" as a full hostname label (e.g. staff.stage.example.org or
// stage.example.org) without matching unrelated labels like "backstage".
export function isStagingEnvironment(hostname: string = window.location.hostname): boolean {
  return /(^|\.)stage\./.test(hostname);
}
