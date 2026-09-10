import { isStagingEnvironment } from '../../utils';

const REPO_URL = 'https://github.com/kalx-berkeley/staff-app';

// Shows what's actually deployed: the commit hash on staging, the release
// version on production. Populated at CI build time via VITE_COMMIT_SHA /
// VITE_RELEASE_VERSION (see .github/workflows/deploy.yml) — both are unset
// in local dev, so this renders nothing outside a deployed build.
const BuildInfo = () => {
  const commitSha = import.meta.env.VITE_COMMIT_SHA as string | undefined;
  const releaseVersion = import.meta.env.VITE_RELEASE_VERSION as string | undefined;

  if (isStagingEnvironment()) {
    if (!commitSha) return null;
    return (
      <a
        href={`${REPO_URL}/commit/${commitSha}`}
        target="_blank"
        rel="noopener noreferrer"
        title={`Staging is running commit ${commitSha}`}
      >
        {commitSha.slice(0, 7)}
      </a>
    );
  }

  if (!releaseVersion) return null;
  return (
    <a
      href={`${REPO_URL}/releases/tag/${releaseVersion}`}
      target="_blank"
      rel="noopener noreferrer"
      title={`Production is running release ${releaseVersion}`}
    >
      {releaseVersion}
    </a>
  );
};

export default BuildInfo;
