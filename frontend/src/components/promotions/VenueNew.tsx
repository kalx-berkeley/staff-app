import { useNavigate } from 'react-router-dom';
import VenueForm from './VenueForm';
import { usePageTitle } from '../../hooks/usePageTitle';

const VenueNew = () => {
  usePageTitle('New Venue · Promotions');
  const navigate = useNavigate();
  const handleDone = () => navigate('/promotions/venues');

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
