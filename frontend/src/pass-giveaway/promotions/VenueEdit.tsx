import { venuesAPI } from '../api';
import VenueForm from './VenueForm';
import EntityEditPage from './shared/EntityEditPage';

const VenueEdit = () => (
  <EntityEditPage
    noun="Venue"
    listPath="/promotions/venues"
    load={venuesAPI.get}
    renderForm={(venue, done) => (
      <VenueForm venue={venue} onClose={done} onSuccess={done} onDelete={done} />
    )}
  />
);

export default VenueEdit;
