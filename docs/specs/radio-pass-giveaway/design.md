# Design Document: Promotions Pass Giveaway System

## Overview

The Promotions Pass Giveaway System is a web-based application that coordinates pass distribution between music venues, radio DJs, promotions staff, and radio station staff. The system consists of a React-based frontend (served as static files), a Python FastAPI backend, SQLite database, and Apache `mod_auth_openidc` for Google OAuth2 authentication, all deployed on a single server.

The system supports three distinct user workflows:
1. Promotions staff manage shows, venues, and pass allocation
2. DJs record pass winners and giveaway attempts during live broadcasts
3. Staff members browse and claim staff passes to events

Key design principles:
- Simplicity and maintainability for junior developers
- Minimal authentication friction for DJs during live broadcasts
- Single-server deployment with automated updates via CI/CD
- Clear separation between frontend, backend, and authentication layers

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Promotions   │  │    Staff     │  │     DJ       │      │
│  │    View      │  │    View      │  │    View      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                    React Frontend                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS  (staff.kalx.berkeley.edu)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│   Apache staff.kalx.berkeley.edu + mod_auth_openidc          │
│   (Static files, Reverse Proxy, Auth enforcement)            │
│         ↕ OAuth2 login/callback via session cookie           │
│   Apache auth.kalx.berkeley.edu + mod_auth_openidc          │
│   (Google OAuth2 callback endpoint only)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            FastAPI Backend (systemd user service)            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Shows     │  │   Passes     │  │    Users     │      │
│  │   Service    │  │   Service    │  │   Service    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │   Venues     │  │  Scheduler   │                        │
│  │   Service    │  │ (APScheduler)│                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
└─────────────────────────────────────────────────────────────┘

External:
┌──────────────┐
│   Airtable   │ ──(nightly sync via REST API)──> User Service
└──────────────┘
```

### Technology Stack

**Frontend:**
- React 18+ with TypeScript for type safety
- React Router for view routing
- Axios for API communication
- Vite for build tooling (fast, simple configuration)
- Vitest for unit testing
- Static file deployment (no container)

**Backend:**
- Python 3.11+
- FastAPI for REST API (async, automatic OpenAPI docs, type hints)
- SQLAlchemy for database ORM
- Pydantic for request/response validation
- pytest for unit and integration testing
- APScheduler for scheduled tasks (Airtable sync)
- Gunicorn + Uvicorn workers
- Deployed as a systemd user service

**Authentication:**
- Two Apache VirtualHosts handle authentication:
  - `auth.kalx.berkeley.edu`: `mod_auth_openidc` OAuth2 callback endpoint; sets session cookie on `.kalx.berkeley.edu`
  - `staff.kalx.berkeley.edu`: enforces auth using the shared session cookie; serves the app
- IP-based bypass for DJ studio network (enforced in the backend)
- Email-based user identification passed via `X-Forwarded-User` header (set by Apache on the staff site after Google login)
- User roles (promotions staff / staff) determined from the database

**Database:**
- SQLite for data persistence
- Alembic for database migrations

**Deployment:**
- rsync for code deployment
- systemd user service for backend
- GitHub Actions for CI/CD
- Netbird VPN for secure server connectivity during deployments

## Components and Interfaces

### Frontend Components

#### 1. Promotions Staff View (`/pass-giveaway/promotions/...`)

**Components:**
- `PromotionsLayout`: Main layout with navigation
- `ShowList`: Searchable/filterable list of all shows (draft, published, closed)
- `ShowForm`: Create/edit show details (uses venue dropdown)
- `ShowDetail`: View show with pass assignments and winner list; publish/close controls; pre-assignment interface
- `VenueList`: Browse and manage venues
- `VenueForm`: Create/edit venue
- `ProfileSettings`: Edit promotions staff name and phone
- `SearchBar`: Freetext and filter-based search

**Key Features:**
- Create shows in draft status referencing an existing venue
- Publish shows to make visible to DJs and staff
- Close shows to prevent further pass activity
- View all pass winners and staff claims per show
- Pre-assign pass pairs to specific DJs and dates
- Remove pre-assignments from pass pairs
- Manage venues (create, view, edit)
- Edit personal profile (name and phone)

#### 2. Staff Member View (`/pass-giveaway/staff/...`)

**Components:**
- `StaffLayout`: Main layout with navigation
- `ShowBrowser`: Browse published shows (staff sees published and closed)
- `ShowDetail`: View show details and claim staff passes (one-click claim)
- `ProfileSettings`: Edit staff name and phone

**Key Features:**
- Browse published and closed shows
- Claim available staff passes with one click (uses stored profile name/phone)
- View show details including accessibility and age restrictions
- Edit personal profile (name and phone)

#### 3. DJ View (`/pass-giveaway/dj/...`)

**Components:**
- `DJLayout`: Simplified layout for quick access
- `ShowBrowser`: Browse published shows
- `ShowDetail`: View show details and record giveaways
- `PassGiveawayForm`: Quick form to record winners or attempts
- `MyPasses`: View giveaway history by DJ name

**Key Features:**
- Accessible by DJs (IP-based) and promotions staff (authenticated)
- Quick pass winner recording with minimal fields (recipient name, phone, DJ name)
- Record failed giveaway attempts
- DJ name autocomplete based on historical data
- View giveaway history filtered by DJ name

### Backend API Endpoints

#### Venues API

```
GET    /api/venues                  # List all venues
POST   /api/venues                  # Create venue (promotions only)
GET    /api/venues/{id}             # Get venue details
PUT    /api/venues/{id}             # Update venue (promotions only)
```

#### Shows API

```
GET    /api/shows                    # List shows (filtered by role)
POST   /api/shows                    # Create show (promotions only)
GET    /api/shows/search             # Search shows (freetext and filters)
GET    /api/shows/{id}               # Get show details
PUT    /api/shows/{id}               # Update show (promotions only)
POST   /api/shows/{id}/publish       # Publish show (promotions only)
POST   /api/shows/{id}/close         # Close show (promotions only)
```

#### Passes API

```
GET    /api/shows/{id}/passes        # Get all passes for show (authenticated)
POST   /api/passes/{id}/giveaway     # Record pass giveaway (DJ access)
POST   /api/passes/{id}/attempt      # Record failed attempt (DJ access)
POST   /api/passes/{id}/claim        # Claim staff pass (staff only)
GET    /api/passes/my-giveaways      # Get DJ's giveaway history (DJ access, requires dj_name param)
POST   /api/passes/{id}/preassign    # Set pre-assignment (promotions only)
DELETE /api/passes/{id}/preassign    # Remove pre-assignment (promotions only)
```

#### Autocomplete API

```
GET    /api/autocomplete/djs         # Get DJ names for autocomplete (DJ access)
```

#### Users API

```
GET    /api/users/me                 # Get current user info (authenticated)
GET    /api/users/profile            # Get current user's profile (authenticated)
PUT    /api/users/profile            # Update current user's profile (authenticated)
POST   /api/users/sync               # Trigger Airtable sync (promotions only)
GET    /api/users/debug/headers      # Debug: inspect incoming request headers
```

#### Health API

```
GET    /health                       # Backend health check
```

### Backend Services

#### ShowService

**Responsibilities:**
- Create, read, update shows
- Manage show status transitions (draft → published → closed)
- Validate show data (verify venue exists, promotions staff exists)
- Filter shows by user role
- Search shows by various criteria (freetext, venue, artist, genre)
- Automatically create passes when a show is created

**Key Methods:**
```python
create_show(db, show_data: ShowCreate, promotions_staff_id: int) -> Show
get_show(db, show_id: int) -> Show
update_show(db, show_id: int, show_data: ShowUpdate) -> Show
list_shows(db, user_role: str | None) -> List[Show]
publish_show(db, show_id: int) -> Show
close_show(db, show_id: int) -> Show
search_shows(db, user_role, freetext, venue_id, artist, genre) -> List[Show]
```

#### PassService

**Responsibilities:**
- Create pass pairs and staff passes when show is created (N pairs + N staff passes)
- Record pass giveaways (winner name, phone, DJ name, timestamp)
- Record failed giveaway attempts (DJ name, timestamp, increment count)
- Handle staff pass claims (associate with staff profile, timestamp)
- Validate pass availability and show status
- Manage pre-assignments (set and remove)
- Filter passes for DJ view

**Key Methods:**
```python
create_passes_for_show(db, show_id, num_pairs) -> List[Pass]
give_away_pass_pair(db, pass_id, giveaway_data: GiveawayData) -> Pass
record_attempt(db, pass_id, dj_name) -> Pass
claim_staff_pass(db, pass_id, staff_id) -> Pass
get_dj_history(db, dj_name) -> List[Pass]
get_dj_names_for_autocomplete(db) -> List[str]
set_preassignment(db, pass_id, dj_name, assignment_date) -> Pass
remove_preassignment(db, pass_id) -> Pass
get_passes_for_show(db, show_id, dj_name, current_date) -> List[Pass]
```

#### VenueService

**Responsibilities:**
- Manage venue records (create, read, update, list)
- Enforce venue name uniqueness

**Key Methods:**
```python
create_venue(db, venue_data: VenueCreate) -> Venue
get_venue(db, venue_id) -> Venue
update_venue(db, venue_id, venue_data: VenueUpdate) -> Venue
list_venues(db) -> List[Venue]
```

#### UserService

**Responsibilities:**
- Sync users from Airtable REST API to the SQLite database
- Add new users (promotions staff or staff) to the database
- Remove users no longer in Airtable
- Manage promotions staff and staff member profile records in the database

**Key Methods:**
```python
async get_staff_emails() -> List[str]
async get_promotions_emails() -> List[str]
async sync_from_airtable() -> Dict[str, Any]
get_or_create_promotions_profile(db, email) -> PromotionsStaff
update_promotions_profile(db, email, profile_data) -> PromotionsStaff
get_or_create_staff_profile(db, email) -> Staff
update_staff_profile(db, email, profile_data) -> Staff
```

## Data Models

### Database Schema

#### Venue Table

```python
class Venue(Base):
    __tablename__ = "venues"

    id: int                          # Primary key
    name: str                        # Required, unique, indexed
    address: str                     # Required (postal address)
    created_at: datetime
    updated_at: datetime

    # Relationships
    shows: List[Show]
```

#### PromotionsStaff Table

```python
class PromotionsStaff(Base):
    __tablename__ = "promotions_staff"

    id: int                          # Primary key
    email: str                       # Required, unique, indexed
    name: str                        # Required (display name)
    phone: str                       # Required (contact phone)
    created_at: datetime
    updated_at: datetime

    # Relationships
    shows: List[Show]
```

#### Staff Table

```python
class Staff(Base):
    __tablename__ = "staff"

    id: int                          # Primary key
    email: str                       # Required, unique, indexed
    name: str                        # Required (display name)
    phone: str                       # Required (contact phone)
    created_at: datetime
    updated_at: datetime

    # Relationships
    claimed_passes: List[Pass]
```

#### Show Table

```python
class Show(Base):
    __tablename__ = "shows"

    id: int                          # Primary key
    event_name: str                  # Required
    genre: str | None                # Optional
    venue_id: int                    # FK to venues.id, required
    show_date: date                  # Required
    show_time: time                  # Required
    special_instructions: str | None # Optional
    age_restriction: str             # "all_ages", "18+", "21+"
    wheelchair_accessible: bool      # Required
    num_pass_pairs: int              # 1-5, required
    promotions_staff_id: int         # FK to promotions_staff.id
    status: str                      # "draft", "published", "closed"
    created_at: datetime
    updated_at: datetime

    # Relationships
    venue: Venue
    promotions_staff: PromotionsStaff
    passes: List[Pass]
```

#### Pass Table

```python
class Pass(Base):
    __tablename__ = "passes"

    id: int                          # Primary key
    show_id: int                     # FK to shows.id
    pass_type: str                   # "pair" or "staff"
    status: str                      # "available", "given_away", "claimed"

    # For pass pairs given away on-air
    recipient_name: str | None
    recipient_phone: str | None
    given_away_by_dj: str | None
    given_away_at: datetime | None

    # For staff passes claimed (FK to staff.id)
    staff_id: int | None
    claimed_at: datetime | None

    # For pre-assigned pairs (promotions assignment)
    preassigned_dj: str | None
    preassigned_date: date | None

    # For failed attempts
    attempt_count: int               # Number of failed attempts (default 0)
    last_attempt_dj: str | None
    last_attempt_at: datetime | None

    created_at: datetime
    updated_at: datetime

    # Relationships
    show: Show
    staff: Staff
```

### API Request/Response Models

#### VenueCreate / VenueUpdate / VenueResponse

```python
class VenueCreate(BaseModel):
    name: str        # max 200 chars, unique
    address: str     # max 500 chars

class VenueResponse(BaseModel):
    id: int
    name: str
    address: str
```

#### ShowCreate

```python
class ShowCreate(BaseModel):
    event_name: str                              # max 200 chars
    genre: str | None = None                     # optional, max 100 chars
    venue_id: int                                # reference to existing venue
    show_date: date
    show_time: time
    special_instructions: str | None = None      # max 1000 chars
    age_restriction: Literal["all_ages", "18+", "21+"]
    wheelchair_accessible: bool
    num_pass_pairs: int                          # 1-5 inclusive
```

#### GiveawayData

```python
class GiveawayData(BaseModel):
    recipient_name: str          # max 100 chars
    recipient_phone: str         # max 20 chars
    given_away_by_dj: str        # max 100 chars
```

#### PreassignmentData

```python
class PreassignmentData(BaseModel):
    dj_name: str           # max 100 chars
    assignment_date: date
```

#### ShowResponse

```python
class ShowResponse(BaseModel):
    id: int
    event_name: str
    genre: str | None
    venue: VenueResponse              # nested venue object
    show_date: date
    show_time: time
    special_instructions: str | None
    age_restriction: str
    wheelchair_accessible: bool
    num_pass_pairs: int
    promotions_staff: PromotionsStaffResponse  # nested staff object
    status: str
    passes: List[PassResponse]        # all passes for this show
    available_pair_count: int
    available_staff_count: int
```

#### PassResponse

```python
class PassResponse(BaseModel):
    id: int
    show_id: int
    pass_type: str       # "pair" or "staff"
    status: str          # "available", "given_away", "claimed"

    # For pass pairs given away on-air
    recipient_name: str | None
    recipient_phone: str | None
    given_away_by_dj: str | None
    given_away_at: datetime | None

    # For staff passes claimed
    staff_id: int | None
    staff_name: str | None    # resolved from Staff record
    staff_phone: str | None   # resolved from Staff record
    claimed_at: datetime | None

    # For pre-assigned pairs
    preassigned_dj: str | None
    preassigned_date: date | None

    # For failed attempts
    attempt_count: int
    last_attempt_dj: str | None
    last_attempt_at: datetime | None

    created_at: datetime
    updated_at: datetime
```

#### UserInfo

```python
class UserInfo(BaseModel):
    email: str
    role: str    # "promotions", "staff", or "dj"
    profile: PromotionsStaffResponse | StaffResponse | None
```

#### SyncResult

```python
class SyncResult(BaseModel):
    staff_added: List[str]
    promotions_added: List[str]
    users_removed: List[str]
    errors: List[str]
```

## Correctness Properties

### Property 1: Show Data Persistence

*For any* valid show with all required fields, creating the show and then retrieving it should return a show with all the same field values.

**Validates: Requirements 1.1, 7.1, 7.4**

### Property 2: New Shows Start in Draft Status

*For any* newly created show, the initial status should be "draft".

**Validates: Requirements 1.2**

### Property 3: Show Visibility Based on Status and Role

*For any* show, its visibility to different user roles should depend on its status: draft shows are visible only to promotions staff; published and closed shows are visible to all authenticated users (promotions, staff, DJs).

**Validates: Requirements 1.3, 12.1, 12.2**

### Property 4: Closed Shows Prevent Pass Operations

*For any* show in closed status, attempting to give away a pass pair, record an attempt, or claim a staff pass should be rejected with a 400 status.

**Validates: Requirements 1.4, 12.3**

### Property 5: Optional Fields Persistence

*For any* show with special instructions provided, storing and retrieving the show should preserve the special instructions; for any show without special instructions, the field should be null.

**Validates: Requirements 1.5**

### Property 6: Pass Pair Count Validation

*For any* show creation request, if the number of pass pairs is less than 1 or greater than 5, the request should be rejected; if the number is between 1 and 5 inclusive, the request should be accepted.

**Validates: Requirements 1.6**

### Property 7: Freetext Search Coverage

*For any* show and any search term that appears in the show's event name, genre, venue name, or special instructions, searching with that term (using the `freetext` query parameter) should return the show in the results.

**Validates: Requirements 2.1**

### Property 8: Filter Accuracy

*For any* collection of shows and any filter criteria (venue_id, artist, or genre), all returned results should match the filter criteria, and all shows matching the criteria should be in the results.

**Validates: Requirements 2.2, 2.3, 2.4**

### Property 9: Search Result Completeness

*For any* search result, the response should include event name, venue, date, time, and available pass status for each show.

**Validates: Requirements 2.5**

### Property 10: Pass Giveaway Persistence

*For any* pass pair and valid giveaway data (recipient name, recipient phone, DJ name), recording the giveaway should store all information, mark the pass as `given_away`, and retrieving the pass should return all the stored information.

**Validates: Requirements 3.1, 3.3, 7.2, 7.4**

### Property 11: Failed Attempt Recording

*For any* pass pair and DJ name, recording a failed giveaway attempt should increment the attempt count, store the DJ name and timestamp, and keep the pass status as `available`.

**Validates: Requirements 3.2**

### Property 12: DJ Giveaway History Filtering

*For any* DJ name, querying that DJ's giveaway history should return only passes assigned by that DJ with status `given_away`, and should include all passes assigned by that DJ.

**Validates: Requirements 3.4**

### Property 13: Pre-Assignment Display

*For any* pass pair pre-assigned to a specific DJ for a specific date, that DJ should see the pre-assignment data (preassigned_dj and preassigned_date) when viewing available passes.

**Validates: Requirements 3.5**

### Property 14: DJ Name Autocomplete

*For any* set of historical pass giveaways, the autocomplete endpoint should return the distinct set of DJ names who have given away passes, and should not return names of DJs who have not given away passes.

**Validates: Requirements 3.6**

### Property 15: Staff Pass Claim Persistence

*For any* staff pass and authenticated staff member, claiming the pass should associate the staff member's ID, store the timestamp, mark the pass as `claimed`, and retrieving the pass should return the staff name and phone via the resolved Staff record.

**Validates: Requirements 4.1, 4.2, 7.3, 7.4**

### Property 16: Staff Pass Allocation Ratio

*For any* show with N pass pairs, the system should create exactly N staff passes when the show is created.

**Validates: Requirements 4.4**

### Property 17: Staff Pass Capacity Enforcement

*For any* show where all staff passes are claimed, attempting to claim another staff pass should be rejected with a 400 status.

**Validates: Requirements 4.5**

### Property 18: Authentication Requirement for Protected Views

*For any* request to promotions staff or staff member API endpoints without valid authentication, the request should be rejected with a 401 or 403 status code.

**Validates: Requirements 5.1, 5.2**

### Property 19: IP-Based DJ Access

*For any* request to DJ view endpoints from the configured DJ studio IP network (CIDR range), the request should be allowed without username/password authentication; requests from other IP addresses require authentication.

**Validates: Requirements 5.3, 5.4**

### Property 20: User Sync Addition

*For any* email address in the Airtable export that is not currently in the database, running the sync should add that user to the database with the appropriate role (staff or promotions staff).

**Validates: Requirements 6.1, 6.2, 6.4, 6.5**

### Property 21: User Sync Removal

*For any* user currently in the database whose email is not in the Airtable export, running the sync should remove that user from the database.

**Validates: Requirements 6.3**

### Property 22: Referential Integrity

*For any* pass, the associated show_id must reference an existing show; for any show, the venue_id must reference an existing venue.

**Validates: Requirements 7.5**

### Property 23: Frontend Input Validation

*For any* form in the frontend with required fields, attempting to submit with missing or invalid data should display validation errors and prevent the API call.

**Validates: Requirements 8.5**

### Property 24: Role-Based UI Elements

*For any* authenticated user, the frontend should display only the UI elements and navigation options appropriate for that user's role (promotions, staff, or DJ).

**Validates: Requirements 8.4**

**Status: PASSED** - 14 unit tests passing, 1 skipped due to React Router race condition.

### Property 25: Backend Request Validation

*For any* API endpoint, sending a request with invalid data (wrong types, missing required fields, out-of-range values) should return a 400 or 422 status code with error details.

**Validates: Requirements 9.2**

### Property 26: HTTP Status Code Correctness

*For any* API operation, the response should use appropriate HTTP status codes: 200 for success, 201 for creation, 400/422 for client errors, 401/403 for authentication/authorization errors, 404 for not found, 500 for server errors.

**Validates: Requirements 9.3**

### Property 27: Show Status Transitions

*For any* show in draft status, promotions staff should be able to transition it to published; for any show in published status, promotions staff should be able to transition it to closed; invalid transitions (e.g., closing a draft show) should be rejected with a 400 status.

**Validates: Requirements 12.4, 12.5**

### Property 28: Show Detail Completeness

*For any* show, the response should include all passes with recipient names and phones, all staff claims with names and phones (resolved from Staff records), all failed attempt records, and the DJ name for each given-away pass pair.

**Validates: Requirements 13.1, 13.2, 13.3, 13.5**

### Property 29: Pass Grouping by Show

*For any* show, all passes (pairs and staff passes) should be associated with that show's ID and returned as a group in the show response and the passes endpoint.

**Validates: Requirements 13.4**

### Property 30: Pre-Assignment Management

*For any* pass pair, promotions staff should be able to set a pre-assignment (DJ name and date), and should be able to remove the pre-assignment; when not pre-assigned, the pass should be available to any DJ; when pre-assigned and the assignment date has passed, the pass should still be visible to that DJ.

**Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**

### Property 31: Promotions Staff Profile Management

*For any* authenticated promotions staff user, the system should be able to create or retrieve their profile and update their name and phone number.

**Validates: Requirements 1.1**

### Property 32: Staff Profile Management

*For any* authenticated staff member, the system should be able to create or retrieve their profile and update their name and phone number.

**Validates: Requirements 4.1**

### Property 33: Venue Data Persistence

*For any* venue with a valid name and address, creating the venue and retrieving it should return a venue with the same field values.

**Validates: Requirements 1.1, 7.1**

### Property 34: Venue Name Uniqueness

*For any* two venues, they must have distinct names; attempting to create a venue with a name already in use should be rejected.

**Validates: Requirements 1.1**

## Error Handling

### Backend Error Handling

**Validation Errors:**
- All API endpoints validate input using Pydantic models
- Return 422 Unprocessable Entity with detailed field-level errors
- Example: Missing required field, invalid date format, out-of-range values

**Authentication/Authorization Errors:**
- Return 401 Unauthorized for missing/invalid authentication
- Return 403 Forbidden for insufficient permissions
- Example: Staff member attempting to create a show

**Not Found Errors:**
- Return 404 Not Found for non-existent resources
- Include helpful error message indicating what was not found
- Example: Requesting show with non-existent ID, referencing non-existent venue

**Business Logic Errors:**
- Return 400 Bad Request for invalid operations
- Include descriptive error message explaining why operation failed
- Examples:
  - Attempting to give away or claim a pass for a closed show
  - Attempting to give away an already given-away pass
  - Attempting to claim when all staff passes are taken
  - Invalid show status transitions (e.g., publishing an already-published show)

**Database Errors:**
- Integrity errors (constraint violations): 400 Bad Request
- Other SQLAlchemy errors: 500 Internal Server Error
- All database errors are logged with full details
- Generic error message returned to client

**External Service Errors:**
- Airtable sync failures are logged and returned in the `errors` field of SyncResult

### Frontend Error Handling

**Form Validation:**
- Client-side validation before API calls
- Display inline error messages for invalid fields
- Prevent submission until all validation passes

**API Error Display:**
- Parse error responses from backend
- Display user-friendly error messages
- For 422 errors, show field-specific validation errors
- For other errors, show general error message

**Loading States:**
- Show loading indicators during API calls
- Disable form submission during processing
- Prevent duplicate submissions

## Testing Strategy

### Backend Testing

**Unit Tests (pytest):**
- Test individual service methods
- Test API endpoints via FastAPI TestClient
- Use in-memory SQLite for tests
- Test-specific fixtures in `conftest.py`
- Current test files: `test_shows.py`, `test_passes.py`, `test_users.py`, `test_venues.py`, `test_cidr_network.py`

**Property-Based Tests (Hypothesis):**
- Use Hypothesis library for property-based testing
- Configure each test to run minimum 100 iterations
- Tag each test with comment: `# Feature: radio-pass-giveaway, Property N: [property text]`

**CI/CD Testing (GitHub Actions):**
- Run backend tests on every push: `black --check` + `pytest --cov`
- Run frontend tests on every push: `npm run lint` + `tsc --noEmit` + `npm test`
- Fail build if any tests fail
- Block deployment if tests fail

### Frontend Testing

**Unit Tests (Vitest):**
- Test individual React components in isolation
- Mock API calls and authentication context
- Current test files: `App.test.tsx`, `MyPasses.test.tsx`, `PassGiveawayForm.test.tsx`, `ShowBrowser.test.tsx`, `ProfileSettings.test.tsx`, `SearchBar.test.tsx`, `ShowForm.test.tsx`, `VenueForm.test.tsx`, `ShowDetail.test.tsx`

**Property-Based Tests (fast-check):**
- Use fast-check library for property-based testing
- Tag each test with comment: `// Feature: radio-pass-giveaway, Property N: [property text]`

## Deployment Architecture

### Server Structure

The application runs on a single server:

**`promotions` user:**
- Runs the FastAPI backend as a systemd user service (`promotions-app-backend`)
- Stores the SQLite database in `~/promotions-app/backend/data/promotions.db`
- Frontend static files served from `~/promotions-app/frontend/dist/`

**Apache (system service, managed by root/sudo):**
- Two VirtualHost configs in `/etc/apache2/sites-available/`:
  - `auth.kalx.berkeley.edu`: `mod_auth_openidc` handles Google OAuth2 callbacks; session cookies scoped to `.kalx.berkeley.edu`
  - `staff.kalx.berkeley.edu`: enforces auth via shared session cookie, serves frontend static files, reverse proxies `/api/`
- DJ-facing routes on the staff site allow unauthenticated access; backend enforces IP-based check

### Deployment Workflow (GitHub Actions)

**Triggered by:**
- Push to `main` branch → deploys to staging environment
- Published release tag → deploys to production environment

**Steps:**
1. Run all backend tests (`black --check`, `pytest`)
2. Run all frontend tests (`lint`, `tsc`, `npm test`)
3. Connect to server via Netbird VPN
4. Back up SQLite database
5. rsync backend code to server (excluding venv, caches)
6. rsync built frontend to server
7. Install/update Python dependencies (venv)
8. Run Alembic database migrations
9. Restart backend systemd service
10. Verify backend health check (`/health`)

### Configuration Management

**Backend environment variables (`.env`):**
- `DATABASE_URL`: SQLite path
- `DJ_STUDIO_NETWORK`: CIDR range for DJ studio IP bypass
- `AIRTABLE_API_KEY`: Airtable API key
- `AIRTABLE_BASE_ID`: Airtable base ID
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins

**Apache configuration (`/etc/apache2/sites-available/auth.kalx.conf` and `staff.kalx.conf`):**
- `OIDCClientID`: Google OAuth2 client ID (same in both VirtualHosts)
- `OIDCClientSecret`: Google OAuth2 client secret (same in both VirtualHosts)
- `OIDCCryptoPassphrase`: Random passphrase for session encryption (same in both VirtualHosts — required for cross-vhost session sharing)
- `OIDCCookieDomain`: Set to `.kalx.berkeley.edu` in both VirtualHosts to share session cookies across subdomains

### Airtable Sync Scheduling

**APScheduler Configuration:**
- Cron job runs daily at 2 AM
- Fetches staff and promotions lists from Airtable REST API (with pagination)
- Updates the SQLite database
- Logs sync results
- Can also be triggered manually via `POST /api/users/sync`

## Development Workflow

### Local Development Setup

**Prerequisites:**
- Python 3.11+
- Node.js 20+

**Backend Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
pytest          # Run tests
uvicorn app.main:app --reload  # Start dev server on port 8000
```

**Frontend Setup:**
```bash
cd frontend
npm install
npm test        # Run tests
npm run dev     # Start dev server on port 3000 (proxies /api to backend)
```

### Code Organization

**Backend Structure:**
```
backend/
├── app/
│   ├── main.py             # FastAPI app entry point, global exception handlers
│   ├── auth.py             # Authentication/authorization utilities
│   ├── config.py           # Configuration via pydantic-settings
│   ├── database.py         # Database connection and session
│   ├── scheduler.py        # APScheduler for daily Airtable sync
│   ├── models/             # SQLAlchemy models
│   │   ├── venue.py
│   │   ├── promotions_staff.py
│   │   ├── staff.py
│   │   ├── show.py
│   │   └── pass_model.py
│   ├── schemas/            # Pydantic schemas
│   │   ├── venue.py
│   │   ├── user.py
│   │   ├── show.py
│   │   └── pass_schema.py
│   ├── services/           # Business logic
│   │   ├── venue_service.py
│   │   ├── show_service.py
│   │   ├── pass_service.py
│   │   └── user_service.py
│   └── routers/            # API endpoint handlers
│       ├── venues.py
│       ├── users.py
│       ├── shows.py
│       └── passes.py
├── alembic/                # Database migrations
├── tests/                  # Test files
│   ├── conftest.py
│   ├── test_shows.py
│   ├── test_passes.py
│   ├── test_users.py
│   ├── test_venues.py
│   └── test_cidr_network.py
└── requirements.txt
```

**Frontend Structure:**
```
frontend/
├── src/
│   ├── App.tsx             # Main app component with routing
│   ├── main.tsx            # Entry point
│   ├── components/
│   │   ├── promotions/     # Promotions staff view components
│   │   │   ├── PromotionsLayout.tsx
│   │   │   ├── ShowList.tsx
│   │   │   ├── ShowForm.tsx
│   │   │   ├── ShowDetail.tsx
│   │   │   ├── VenueList.tsx
│   │   │   ├── VenueForm.tsx
│   │   │   ├── ProfileSettings.tsx
│   │   │   └── SearchBar.tsx
│   │   ├── staff/          # Staff member view components
│   │   │   ├── StaffLayout.tsx
│   │   │   ├── ShowBrowser.tsx
│   │   │   ├── ShowDetail.tsx
│   │   │   └── ProfileSettings.tsx
│   │   └── dj/             # DJ view components
│   │       ├── DJLayout.tsx
│   │       ├── ShowBrowser.tsx
│   │       ├── ShowDetail.tsx
│   │       ├── PassGiveawayForm.tsx
│   │       └── MyPasses.tsx
│   ├── contexts/
│   │   ├── AuthContext.tsx  # React context provider
│   │   ├── authContext.ts   # Context definition
│   │   └── authHooks.ts     # useAuth hook
│   ├── services/
│   │   └── api.ts           # Axios-based API client
│   └── types/
│       └── index.ts         # TypeScript types matching backend schemas
└── vite.config.ts
```
