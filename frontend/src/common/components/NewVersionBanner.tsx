import { reloadFor } from '../appVersion';
import { useNewVersionCheck } from '../hooks/useNewVersionCheck';

// Offers a reload once a newer build is deployed. Tabs reload by themselves once
// idle, but one with something typed in it waits much longer.
const NewVersionBanner = () => {
  const newVersion = useNewVersionCheck();

  if (!newVersion) return null;

  return (
    <div className="new-version-banner" role="status">
      <span>A new version of this site is available.</span>
      <button type="button" onClick={() => reloadFor(newVersion)}>
        Reload
      </button>
    </div>
  );
};

export default NewVersionBanner;
