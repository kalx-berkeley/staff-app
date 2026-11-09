import apiClient, { handleAPIError } from '../common/api';
import type { AnalyticsTab, TabResponse } from './types';
import type { WindowParams } from './timeWindow';

/** KALX Staff Analytics API methods. */
export const analyticsAPI = {
  /** Every metric on *tab*, for the time window and the page's other parameters. */
  getTab: async (
    tab: AnalyticsTab,
    window: WindowParams,
    params: Record<string, string> = {},
  ): Promise<TabResponse> => {
    try {
      const response = await apiClient.get<TabResponse>(`/analytics/tabs/${tab}`, {
        params: { ...window, ...params },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};
