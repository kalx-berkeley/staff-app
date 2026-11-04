/** What the "Wait for me to send close notifications" option does, and its risk. */
const HoldCloseNotificationsHint = () => (
  <>
    <span className="field-hint">
      When checked, closing a show doesn't tell staff with a +1 or alternates the outcome. A
      promotions rep sends those emails with a button on the closed show's page. If nobody
      clicks it before the show date has passed, they're never sent.
    </span>
    <span className="field-warning hold-close-warning">
      <strong>Risk:</strong> Staff can choose to give up their pass if their +1 doesn't have one
      when the show closes. They lose it when the show closes, but aren't told until these emails
      are sent. If nobody sends them, those staff could turn up expecting to be on the guest list.
    </span>
  </>
);

export default HoldCloseNotificationsHint;
