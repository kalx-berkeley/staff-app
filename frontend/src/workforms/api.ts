import apiClient, { handleAPIError } from '../common/api';
import type {
  Decision,
  DepartmentPeople,
  Departments,
  Entry,
  EntryInput,
  MyWorkforms,
  PendingCounts,
  Preferences,
  ReviewItem,
  ReviewOverview,
  ReviewQueue,
  Workform,
} from './types';

const call = async <T>(request: Promise<{ data: T }>): Promise<T> => {
  try {
    return (await request).data;
  } catch (error) {
    return handleAPIError(error);
  }
};

const seg = encodeURIComponent;

/** KALX Workforms API for staff: their own workforms. */
export const workformsAPI = {
  departments: () => call(apiClient.get<Departments>('/workforms/departments')),
  mine: () => call(apiClient.get<MyWorkforms>('/workforms/me')),
  get: (month: string) => call(apiClient.get<Workform>(`/workforms/me/${seg(month)}`)),
  addEntry: (month: string, entry: EntryInput) =>
    call(apiClient.post<Entry>(`/workforms/me/${seg(month)}/entries`, entry)),
  updateEntry: (month: string, id: number, entry: EntryInput) =>
    call(apiClient.put<Entry>(`/workforms/me/${seg(month)}/entries/${id}`, entry)),
  deleteEntry: (month: string, id: number) =>
    call(apiClient.delete<void>(`/workforms/me/${seg(month)}/entries/${id}`)),
  submit: (month: string) => call(apiClient.post<Workform>(`/workforms/me/${seg(month)}/submit`)),
  preferences: () => call(apiClient.get<Preferences>('/workforms/preferences')),
  updatePreferences: (prefs: Omit<Preferences, 'is_department_head'>) =>
    call(apiClient.put<Preferences>('/workforms/preferences', prefs)),
};

/** KALX Workforms API for department heads reviewing submitted hours. */
export const reviewAPI = {
  overview: () => call(apiClient.get<ReviewOverview>('/workforms/review')),
  pending: (month: string) =>
    call(apiClient.get<PendingCounts>(`/workforms/review/${seg(month)}/pending`)),
  queue: (month: string, department: string) =>
    call(apiClient.get<ReviewQueue>(`/workforms/review/${seg(month)}/${seg(department)}`)),
  decide: (recordId: string, department: string, decision: Decision | null) =>
    call(
      apiClient.put<ReviewItem>(`/workforms/review/decisions/${seg(recordId)}/${seg(department)}`, {
        decision,
      })
    ),
  people: (department: string, months: number, minMonths: number) =>
    call(
      apiClient.get<DepartmentPeople>(`/workforms/review/people/${seg(department)}`, {
        params: { months, min_months: minMonths },
      })
    ),
};
