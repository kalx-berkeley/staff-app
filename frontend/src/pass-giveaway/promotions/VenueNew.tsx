import { useNavigate } from 'react-router-dom';
import VenueForm from './VenueForm';
import { useReturnToList } from '../listUrlState';
import { usePageTitle } from '../../common/hooks/usePageTitle';

const VenueNew = () => {
  usePageTitle('New Venue · Promotions');
  const navigate = useNavigate();
  const returnTo = useReturnToList('/promotions/venues');
  const handleDone = () => navigate(returnTo);

  return (
    <VenueForm
      venue={null}
      asPage={true}
      onClose={handleDone}
      onSuccess={handleDone}
    />
  );
};

export default VenueNew;
