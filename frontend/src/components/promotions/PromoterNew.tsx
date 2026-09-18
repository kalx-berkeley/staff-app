import { useNavigate } from 'react-router-dom';
import PromoterForm from './PromoterForm';
import { usePageTitle } from '../../hooks/usePageTitle';

const PromoterNew = () => {
  usePageTitle('New Promoter · Promotions');
  const navigate = useNavigate();
  const handleDone = () => navigate('/promotions/promoters');

  return (
    <PromoterForm
      promoter={null}
      asPage={true}
      onClose={handleDone}
      onSuccess={handleDone}
    />
  );
};

export default PromoterNew;
