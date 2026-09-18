import { useCurrentView, VIEW_LABELS } from './currentView';

// Role-view chip for the mobile top bar, where the sidebar — and with it the
// current-view highlight in AppNav — is tucked away behind the hamburger.
const ViewBadge = () => {
  const view = useCurrentView();

  if (!view) return null;

  return (
    <span className={`view-badge view-badge-${view}`} title="The view you are currently in">
      {VIEW_LABELS[view]}
    </span>
  );
};

export default ViewBadge;
