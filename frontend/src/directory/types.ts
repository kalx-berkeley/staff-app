// TypeScript types matching backend Pydantic schemas for the KALX Staff Directory sub-site.

export interface DjPersona {
  id: number;
  name: string;
}

export interface DirectoryEntry {
  id: number;
  name: string;
  pronouns: string | null;
  email: string;
  phone: string;
  // Spinitron persona names joined with commas, and each persona on its own
  dj_name: string | null;
  dj_personas: DjPersona[];
  departments: string[];
  statuses: string[];
  titles_and_roles: string | null;
  // Changes whenever the photo does; null when there's no photo
  photo_version: string | null;
  // Leave of absence that hasn't ended yet (null once past); on_leave is true during it
  on_leave: boolean;
  loa_start: string | null;
  loa_end: string | null;
}
