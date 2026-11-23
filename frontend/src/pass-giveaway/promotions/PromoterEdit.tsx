import { promotersAPI } from '../api';
import PromoterForm from './PromoterForm';
import EntityEditPage from './shared/EntityEditPage';

const PromoterEdit = () => (
  <EntityEditPage
    noun="Promoter"
    listPath="/promotions/promoters"
    load={promotersAPI.get}
    renderForm={(promoter, done) => (
      <PromoterForm promoter={promoter} onClose={done} onSuccess={done} onDelete={done} />
    )}
  />
);

export default PromoterEdit;
