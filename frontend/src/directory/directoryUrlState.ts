// The directory's search, filters, and sort live in the URL query string, so a
// filtered view can be bookmarked or shared as a link:
//   ?q=music&dept=News&dept=Music&status=Paid+Staff&sort=-email

export type SortableColumn = 'name' | 'dj_name' | 'email';

export interface DirectorySort {
  id: SortableColumn;
  desc: boolean;
}

export interface DirectoryViewState {
  query: string;
  departments: string[];
  statuses: string[];
  sort: DirectorySort;
}

export const DEFAULT_SORT: DirectorySort = { id: 'name', desc: false };

const SORTABLE_COLUMNS: SortableColumn[] = ['name', 'dj_name', 'email'];

export function parseViewState(params: URLSearchParams): DirectoryViewState {
  const rawSort = params.get('sort') ?? '';
  const desc = rawSort.startsWith('-');
  const id = (desc ? rawSort.slice(1) : rawSort) as SortableColumn;
  return {
    query: params.get('q') ?? '',
    departments: params.getAll('dept'),
    statuses: params.getAll('status'),
    sort: SORTABLE_COLUMNS.includes(id) ? { id, desc } : DEFAULT_SORT,
  };
}

/** Query string parameters for a view, leaving out anything at its default. */
export function viewStateParams(state: DirectoryViewState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.query) params.set('q', state.query);
  state.departments.forEach((department) => params.append('dept', department));
  state.statuses.forEach((status) => params.append('status', status));
  if (state.sort.id !== DEFAULT_SORT.id || state.sort.desc !== DEFAULT_SORT.desc) {
    params.set('sort', `${state.sort.desc ? '-' : ''}${state.sort.id}`);
  }
  return params;
}
