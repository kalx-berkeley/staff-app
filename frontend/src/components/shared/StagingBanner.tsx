import { useEffect } from 'react';
import { isStagingEnvironment } from '../../utils';

// Fixed bar shown on every page when running on a stage.* hostname, so staff
// can't mistake the staging site for production. Toggles a body class (rather
// than pushing content via its own layout) so fixed-position nav elements in
// the mobile layouts can be offset below it too — see .staging-active in
// index.css.
const StagingBanner = () => {
  const staging = isStagingEnvironment();

  useEffect(() => {
    if (!staging) return;
    document.body.classList.add('staging-active');
    return () => document.body.classList.remove('staging-active');
  }, [staging]);

  if (!staging) return null;

  return (
    <div className="staging-banner" role="status">
      STAGING — this is a test environment, not the live production site
    </div>
  );
};

export default StagingBanner;
