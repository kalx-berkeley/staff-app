import { useState } from 'react';
import { directoryAPI } from './api';
import type { DirectoryEntry } from './types';
import { initials } from './directorySearch';

interface StaffPhotoProps {
  entry: DirectoryEntry;
  size: 'thumb' | 'medium';
}

// A staff member's photo, or their initials when they have none (or it fails
// to load).
const StaffPhoto = ({ entry, size }: StaffPhotoProps) => {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const url = directoryAPI.photoUrl(entry, size);

  if (!url || url === failedUrl) {
    return (
      <span className={`staff-photo staff-photo-${size} staff-photo-initials`} aria-hidden="true">
        {initials(entry.name)}
      </span>
    );
  }

  return (
    <img
      className={`staff-photo staff-photo-${size}`}
      src={url}
      alt=""
      loading="lazy"
      onError={() => setFailedUrl(url)}
    />
  );
};

export default StaffPhoto;
