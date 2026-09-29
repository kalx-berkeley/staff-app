import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  columnFilteringFeature,
  createColumnHelper,
  createFilteredRowModel,
  createSortedRowModel,
  globalFilteringFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
} from '@tanstack/react-table';
import type { ColumnFiltersState, FilterFn, SortFn, SortingState } from '@tanstack/react-table';
import { useAuth } from '../../contexts/authHooks';
import { usePageTitle } from '../../hooks/usePageTitle';
import { directoryAPI } from '../../services/api';
import { HOME_TITLE, SUBSITES, subsiteForPath } from '../../subsites';
import type { DirectoryEntry } from '../../types';
import DirectoryDetail from './DirectoryDetail';
import FilterMenu from './FilterMenu';
import StaffPhoto from './StaffPhoto';
import { matchesSearch, spinitronUrl } from './directorySearch';
import {
  DEFAULT_SORT,
  parseViewState,
  viewStateParams,
  type DirectoryViewState,
  type SortableColumn,
} from './directoryUrlState';

export const DIRECTORY_TITLE = 'KALX Staff Directory';

const features = tableFeatures({
  columnFilteringFeature,
  globalFilteringFeature,
  filteredRowModel: createFilteredRowModel(),
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
});
type Features = typeof features;

const EMPTY_ENTRIES: DirectoryEntry[] = [];

// Rows whose list column (departments or statuses) has any of the selected values.
const includesAny: FilterFn<Features, DirectoryEntry> = (row, columnId, selected: string[]) =>
  selected.length === 0 || (row.getValue(columnId) as string[]).some((v) => selected.includes(v));

// Case-insensitive text order, with blank values last.
const textSort: SortFn<Features, DirectoryEntry> = (rowA, rowB, columnId) => {
  const a = (rowA.getValue(columnId) as string | null) ?? '';
  const b = (rowB.getValue(columnId) as string | null) ?? '';
  if (!a || !b) return (a ? 0 : 1) - (b ? 0 : 1);
  return a.localeCompare(b, undefined, { sensitivity: 'base' });
};

// A row's departments or statuses, each linking to the table filtered on just
// that value (keeping the current search, sort, and other filter).
const Tags = ({ values, filter }: { values: string[]; filter: 'departments' | 'statuses' }) => {
  const view = parseViewState(new URLSearchParams(window.location.search));
  return (
    <span className="directory-tags">
      {values.map((value) => (
        <Link
          key={value}
          className="directory-tag"
          to={`/?${viewStateParams({ ...view, [filter]: [value] })}`}
          title={`Show only ${value}`}
        >
          {value}
        </Link>
      ))}
    </span>
  );
};

const helper = createColumnHelper<Features, DirectoryEntry>();

const columns = helper.columns([
  helper.display({
    id: 'photo',
    header: () => <span className="visually-hidden">Photo</span>,
    cell: ({ row }) => <StaffPhoto entry={row.original} size="thumb" />,
  }),
  helper.accessor('name', {
    header: 'Name',
    sortFn: textSort,
    cell: ({ row }) => (
      <>
        <Link className="directory-name" to={`/${row.original.id}${window.location.search}`}>
          {row.original.name}
        </Link>
        {row.original.pronouns && (
          <div className="directory-pronouns">{row.original.pronouns}</div>
        )}
      </>
    ),
  }),
  helper.accessor('dj_name', {
    header: 'DJ name',
    sortFn: textSort,
    cell: ({ row }) => {
      const { dj_name: djName, spinitron_ids: personaIds } = row.original;
      if (!djName) return null;
      return personaIds.length > 0 ? (
        <a href={spinitronUrl(personaIds[0])} target="_blank" rel="noreferrer">{djName}</a>
      ) : (
        djName
      );
    },
  }),
  helper.accessor('email', {
    header: 'Email',
    sortFn: textSort,
    cell: ({ row }) => <a href={`mailto:${row.original.email}`}>{row.original.email}</a>,
  }),
  helper.accessor('phone', {
    header: 'Phone',
    enableSorting: false,
    cell: ({ row }) =>
      row.original.phone ? <a href={`tel:${row.original.phone}`}>{row.original.phone}</a> : null,
  }),
  helper.accessor('departments', {
    header: 'Departments',
    enableSorting: false,
    filterFn: includesAny,
    cell: ({ row }) => <Tags values={row.original.departments} filter="departments" />,
  }),
  helper.accessor('statuses', {
    header: 'Status',
    enableSorting: false,
    filterFn: includesAny,
    cell: ({ row }) => <Tags values={row.original.statuses} filter="statuses" />,
  }),
]);

const uniqueSorted = (lists: string[][]) =>
  [...new Set(lists.flat())].sort((a, b) => a.localeCompare(b));

// Resolve a TanStack state updater, which is either a new value or a function
// of the current one.
function resolve<T>(updater: T | ((old: T) => T), current: T): T {
  return typeof updater === 'function' ? (updater as (old: T) => T)(current) : updater;
}

// The staff directory: a searchable, sortable, filterable table of every active
// staff member's contact details. /directory/:staffId opens one person's details.
export default function DirectoryPage() {
  const { user } = useAuth();
  const { staffId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [entries, setEntries] = useState<DirectoryEntry[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    directoryAPI
      .list()
      .then(setEntries)
      .catch((error) => setLoadError(error?.detail ?? 'Could not load the staff directory.'));
  }, []);

  const view = useMemo(() => parseViewState(searchParams), [searchParams]);
  const updateView = useCallback(
    (changes: Partial<DirectoryViewState>) => {
      // Replace rather than push, so typing a search doesn't fill the history.
      setSearchParams(viewStateParams({ ...view, ...changes }), { replace: true });
    },
    [view, setSearchParams],
  );

  const sorting: SortingState = useMemo(() => [view.sort], [view.sort]);
  const columnFilters: ColumnFiltersState = useMemo(
    () => [
      ...(view.departments.length ? [{ id: 'departments', value: view.departments }] : []),
      ...(view.statuses.length ? [{ id: 'statuses', value: view.statuses }] : []),
    ],
    [view.departments, view.statuses],
  );

  const table = useTable({
    features,
    columns,
    data: entries ?? EMPTY_ENTRIES,
    state: { sorting, columnFilters, globalFilter: view.query },
    onSortingChange: (updater) => {
      const [first] = resolve(updater, sorting);
      updateView({ sort: first ? { id: first.id as SortableColumn, desc: first.desc } : DEFAULT_SORT });
    },
    onColumnFiltersChange: (updater) => {
      const next = resolve(updater, columnFilters);
      const valuesFor = (id: string) => (next.find((f) => f.id === id)?.value as string[]) ?? [];
      updateView({ departments: valuesFor('departments'), statuses: valuesFor('statuses') });
    },
    onGlobalFilterChange: (updater) => updateView({ query: resolve(updater, view.query) ?? '' }),
    // Search covers fields that aren't columns (e.g. Titles and Roles), so it
    // runs once per row, via the name column, against the whole entry.
    getColumnCanGlobalFilter: (column) => column.id === 'name',
    globalFilterFn: (row, _columnId, query: string) => matchesSearch(row.original, query),
    enableSortingRemoval: false,
  });

  const departmentOptions = useMemo(
    () => uniqueSorted((entries ?? []).map((e) => e.departments)),
    [entries],
  );
  const statusOptions = useMemo(
    () => uniqueSorted((entries ?? []).map((e) => e.statuses)),
    [entries],
  );

  const myId = user?.profile?.id ?? null;
  const detailEntry =
    staffId && entries ? (entries.find((e) => String(e.id) === staffId) ?? null) : undefined;
  usePageTitle(detailEntry?.name ?? null, DIRECTORY_TITLE);

  const search = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const closeDetail = useCallback(() => navigate(`/${search}`), [navigate, search]);

  const otherSubsites = SUBSITES.filter(
    (subsite) => subsite !== subsiteForPath(window.location.pathname) && subsite.isAvailable(user),
  );
  const rows = table.getRowModel().rows;
  const isFiltered = !!view.query || view.departments.length > 0 || view.statuses.length > 0;

  return (
    <div className="directory-page">
      <header className="directory-header">
        <nav className="directory-subsites" aria-label="Staff sites">
          <a href="/">{HOME_TITLE}</a>
          {otherSubsites.map((subsite) => (
            <a key={subsite.basePath} href={`${subsite.basePath}/`}>{subsite.name}</a>
          ))}
        </nav>
        <div className="directory-title-row">
          <h1>{DIRECTORY_TITLE}</h1>
          {myId !== null && (
            <Link className="btn-secondary btn-small" to={`/${myId}${search}`}>My record</Link>
          )}
        </div>
        {user?.impersonating_email && (
          <p className="directory-impersonating">Viewing as {user.impersonating_email}</p>
        )}
      </header>

      <div className="directory-toolbar">
        <input
          type="search"
          className="directory-search"
          placeholder="Search names, emails, phone numbers, titles…"
          aria-label="Search the staff directory"
          value={view.query}
          onChange={(event) => table.setGlobalFilter(event.target.value)}
        />
        <FilterMenu
          label="Department"
          options={departmentOptions}
          selected={view.departments}
          onChange={(departments) => updateView({ departments })}
        />
        <FilterMenu
          label="Status"
          options={statusOptions}
          selected={view.statuses}
          onChange={(statuses) => updateView({ statuses })}
        />
        {isFiltered && (
          <button
            type="button"
            className="btn-secondary btn-small"
            onClick={() => updateView({ query: '', departments: [], statuses: [] })}
          >
            Clear all
          </button>
        )}
        {entries && (
          <span className="directory-count" role="status">
            {isFiltered ? `${rows.length} of ${entries.length}` : entries.length} staff
          </span>
        )}
      </div>

      {loadError ? (
        <div className="error-message">{loadError}</div>
      ) : !entries ? (
        <p>Loading…</p>
      ) : (
        <table className="directory-table">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={`directory-col-${header.column.id}`}
                      aria-sort={sorted ? (sorted === 'asc' ? 'ascending' : 'descending') : undefined}
                    >
                      {header.column.getCanSort() ? (
                        <button
                          type="button"
                          className="directory-sort-button"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          <table.FlexRender header={header} />
                          <span className="directory-sort-indicator" aria-hidden="true">
                            {sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}
                          </span>
                        </button>
                      ) : (
                        <table.FlexRender header={header} />
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={row.original.id === myId ? 'directory-row-me' : undefined}
                onClick={(event) => {
                  // Let links (email, phone, DJ, tags) do their own thing.
                  if ((event.target as HTMLElement).closest('a')) return;
                  navigate(`/${row.original.id}${search}`);
                }}
              >
                {row.getAllCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`directory-col-${cell.column.id}`}
                    data-label={typeof cell.column.columnDef.header === 'string' ? cell.column.columnDef.header : undefined}
                  >
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="directory-empty">
                  No staff match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {detailEntry !== undefined && (
        <DirectoryDetail entry={detailEntry} isMe={detailEntry?.id === myId} onClose={closeDetail} />
      )}
    </div>
  );
}
