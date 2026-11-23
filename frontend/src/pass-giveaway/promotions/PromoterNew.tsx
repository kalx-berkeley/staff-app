import { useNavigate } from 'react-router-dom';
import PromoterForm from './PromoterForm';
import { useReturnToList } from '../listUrlState';
import { usePageTitle } from '../../common/hooks/usePageTitle';

const PromoterNew = () => {
  usePageTitle('New Promoter · Promotions');
  const navigate = useNavigate();
  const returnTo = useReturnToList('/promotions/promoters');
  const handleDone = () => navigate(returnTo);

  return (
    <PromoterForm
      promoter={null}
      onClose={handleDone}
      onSuccess={handleDone}
    />
  );
};

export default PromoterNew;
