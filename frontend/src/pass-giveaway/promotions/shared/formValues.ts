/** The values behind the form fields that venues and promoters share. */
import type { EmailAddressRequirement } from '../../types';

/** The guest list settings that venues and promoters both have. */
export interface GuestListRequirements {
  requires_phone_number: boolean;
  email_address_requirement: EmailAddressRequirement;
  staff_guest_requires_name: boolean;
  hold_close_notifications: boolean;
  track_pass_call_in: boolean;
}

export const DEFAULT_GUEST_LIST_REQUIREMENTS: GuestListRequirements = {
  requires_phone_number: false,
  email_address_requirement: 'none',
  staff_guest_requires_name: false,
  hold_close_notifications: false,
  track_pass_call_in: false,
};

/** Reads the guest list settings from a saved venue or promoter. */
export const guestListRequirementsFrom = (
  saved: Partial<GuestListRequirements>
): GuestListRequirements => ({
  requires_phone_number: saved.requires_phone_number ?? false,
  email_address_requirement: saved.email_address_requirement ?? 'none',
  staff_guest_requires_name: saved.staff_guest_requires_name ?? false,
  hold_close_notifications: saved.hold_close_notifications ?? false,
  track_pass_call_in: saved.track_pass_call_in ?? false,
});

/** A contact person at a venue or promoter. */
export interface ContactInput {
  name?: string | null;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
}

export const emptyContact = (): ContactInput => ({ name: null, title: null, email: null, phone: null });

export const contactHasText = (c: ContactInput) =>
  [c.name, c.title, c.email, c.phone].some((v) => (v ?? '').trim() !== '');

/** The rows to show for saved contacts: always at least one, for typing in. */
export const contactRowsFrom = (saved: ContactInput[]): ContactInput[] =>
  saved.length > 0
    ? saved.map((c) => ({
        name: c.name ?? null,
        title: c.title ?? null,
        email: c.email ?? null,
        phone: c.phone ?? null,
      }))
    : [emptyContact()];

/** The contacts to save: every row with something typed in it. */
export const contactsToSave = (rows: ContactInput[]): ContactInput[] => rows.filter(contactHasText);

export const NEW_CONTACT_ROWS: ContactInput[] = [emptyContact()];
