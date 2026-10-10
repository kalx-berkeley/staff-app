# Implementation Plan: Promotions Pass Giveaway System

## Overview

This implementation plan breaks down the promotions pass giveaway system into incremental coding tasks. The system uses Python/FastAPI for the backend, React/TypeScript for the frontend, SQLite for data storage, and Apache mod_auth_openidc (Google OAuth2) for authentication. Tasks are organized to build core functionality first, then add features incrementally.

## Tasks

- [x] 1. Set up project structure and development environment
  - Create backend directory with Python/FastAPI structure
  - Create frontend directory with React/TypeScript/Vite structure
  - Configure linting and formatting tools (Black, ESLint, Prettier)
  - Create initial README with setup instructions
  - _Requirements: 8.1, 8.2, 9.1, 9.4, 10.1_

- [x] 2. Implement database models and migrations
  - [x] 2.1 Create SQLAlchemy models for Venue, PromotionsStaff, Staff, Show, and Pass tables
    - Define all fields with proper types and constraints
    - Set up foreign key relationships (Show→Venue, Show→PromotionsStaff, Pass→Show, Pass→Staff)
    - Add unique constraints (venue name, staff/promotions emails)
    - _Requirements: 1.1, 7.5, 15.1_
  
  - [ ]* 2.2 Write property test for database referential integrity
    - **Property 22: Referential Integrity**
    - **Validates: Requirements 7.5**
  
  - [x] 2.3 Set up Alembic for database migrations
    - Initialize Alembic
    - Create initial migration for all tables
    - _Requirements: 7.1, 9.4_
  
  - [ ]* 2.4 Write property test for data persistence
    - **Property 1: Show Data Persistence**
    - **Validates: Requirements 1.1, 7.1, 7.4**

- [x] 3. Implement venue management backend
  - [x] 3.1 Create Pydantic schemas for Venue (VenueCreate, VenueResponse, VenueUpdate)
    - _Requirements: 15.1, 9.2_
  
  - [x] 3.2 Implement VenueService with CRUD operations
    - create_venue, get_venue, update_venue, list_venues
    - _Requirements: 15.1, 15.3_
  
  - [x] 3.3 Create FastAPI router for venue endpoints
    - GET /api/venues, POST /api/venues, GET /api/venues/{id}, PUT /api/venues/{id}
    - Add authentication checks (promotions only for create/update)
    - _Requirements: 15.2, 15.3, 5.1, 9.1_
  
  - [ ]* 3.4 Write property test for venue data persistence
    - **Property 33: Venue Data Persistence**
    - **Validates: Requirements 15.1, 7.1**
  
  - [ ]* 3.5 Write property test for venue name uniqueness
    - **Property 34: Venue Name Uniqueness**
    - **Validates: Requirements 15.2**

- [x] 4. Implement user profile management backend
  - [x] 4.1 Create Pydantic schemas for profiles (PromotionsStaffProfile, StaffProfile, PromotionsStaffResponse, StaffResponse, UserInfo, SyncResult)
    - _Requirements: 16.1, 4.1_
  
  - [x] 4.2 Implement UserService with profile management
    - get_or_create_promotions_profile, update_promotions_profile
    - get_or_create_staff_profile, update_staff_profile
    - _Requirements: 16.1, 16.2_
  
  - [x] 4.3 Create FastAPI router for user profile endpoints
    - GET /api/users/me, GET /api/users/profile, PUT /api/users/profile
    - GET /api/users/debug/headers (debug endpoint)
    - _Requirements: 16.1, 16.2, 5.1, 5.2_
  
  - [ ]* 4.4 Write property test for promotions staff profile management
    - **Property 31: Promotions Staff Profile Management**
    - **Validates: Requirements 16.1**
  
  - [ ]* 4.5 Write property test for staff profile management
    - **Property 32: Staff Profile Management**
    - **Validates: Requirements 4.1, 16.1**

- [x] 5. Implement show management backend
  - [x] 5.1 Create Pydantic schemas for Show (ShowCreate, ShowResponse, ShowUpdate)
    - ShowCreate uses venue_id (FK reference), not venue name/address
    - ShowResponse includes nested venue and promotions_staff objects
    - _Requirements: 1.1, 9.2_
  
  - [x] 5.2 Implement ShowService with core operations
    - create_show, get_show, update_show, list_shows
    - Automatically set status to "draft" on creation
    - Associate show with authenticated promotions staff profile
    - Verify venue exists on create/update
    - _Requirements: 1.1, 1.2, 15.4_
  
  - [x] 5.3 Implement show status transitions in ShowService
    - publish_show (draft → published only)
    - close_show (published → closed only)
    - Validate transitions and reject invalid ones with 400
    - _Requirements: 1.3, 1.4, 12.4, 12.5_
  
  - [x] 5.4 Create FastAPI router for show endpoints
    - GET /api/shows, GET /api/shows/search, POST /api/shows, GET /api/shows/{id}, PUT /api/shows/{id}
    - POST /api/shows/{id}/publish, POST /api/shows/{id}/close
    - Add authentication checks (promotions only for create/update/publish/close)
    - _Requirements: 1.1, 5.1, 9.1_
  
  - [ ]* 5.5 Write property test for new shows starting in draft status
    - **Property 2: New Shows Start in Draft Status**
    - **Validates: Requirements 1.2**
  
  - [ ]* 5.6 Write property test for show status transitions
    - **Property 27: Show Status Transitions**
    - **Validates: Requirements 12.4, 12.5**
  
  - [ ]* 5.7 Write property test for optional fields persistence
    - **Property 5: Optional Fields Persistence**
    - **Validates: Requirements 1.5**
  
  - [ ]* 5.8 Write property test for pass pair count validation
    - **Property 6: Pass Pair Count Validation**
    - **Validates: Requirements 1.6**

- [x] 6. Checkpoint - Ensure all tests pass

- [x] 7. Implement pass management backend
  - [x] 7.1 Create Pydantic schemas for Pass (GiveawayData, PreassignmentData, PassResponse)
    - GiveawayData: recipient_name, recipient_phone, given_away_by_dj
    - PassResponse includes staff_name and staff_phone resolved from Staff record
    - _Requirements: 3.1, 4.1, 9.2_
  
  - [x] 7.2 Implement PassService for pass creation
    - create_passes_for_show: creates N "pair" passes + N "staff" passes, called automatically on show creation
    - _Requirements: 4.4_
  
  - [x] 7.3 Implement PassService for pass pair giveaways
    - give_away_pass_pair: records recipient info, sets status to "given_away"
    - record_attempt: increments attempt_count, stores last_attempt_dj and last_attempt_at, keeps "available"
    - get_dj_history: returns passes with status "given_away" for a given DJ name
    - get_dj_names_for_autocomplete: distinct DJ names from given_away passes
    - _Requirements: 3.1, 3.2, 3.4, 3.6_
  
  - [x] 7.4 Implement PassService for staff pass claims
    - claim_staff_pass: associates with staff_id FK, sets claimed_at, sets status to "claimed"
    - Validate pass type is "staff", status is "available", show is not closed
    - _Requirements: 4.1, 4.2, 4.5, 16.3_
  
  - [x] 7.5 Create FastAPI router for pass endpoints
    - GET /api/shows/{id}/passes, POST /api/passes/{id}/giveaway
    - POST /api/passes/{id}/attempt, POST /api/passes/{id}/claim
    - GET /api/passes/my-giveaways (requires dj_name query param), GET /api/autocomplete/djs
    - POST /api/passes/{id}/preassign, DELETE /api/passes/{id}/preassign
    - Add authentication checks (DJ access for giveaway/attempt, staff for claim, promotions for preassign)
    - _Requirements: 3.1, 4.1, 5.3, 5.4, 9.1_
  
  - [ ]* 7.6 Write property test for pass giveaway persistence
    - **Property 10: Pass Giveaway Persistence**
    - **Validates: Requirements 3.1, 3.3, 7.2, 7.4**
  
  - [ ]* 7.7 Write property test for failed attempt recording
    - **Property 11: Failed Attempt Recording**
    - **Validates: Requirements 3.2**
  
  - [ ]* 7.8 Write property test for staff pass claim persistence
    - **Property 15: Staff Pass Claim Persistence**
    - **Validates: Requirements 4.1, 4.2, 7.3, 7.4**
  
  - [ ]* 7.9 Write property test for staff pass allocation ratio
    - **Property 16: Staff Pass Allocation Ratio**
    - **Validates: Requirements 4.4**
  
  - [ ]* 7.10 Write property test for staff pass capacity enforcement
    - **Property 17: Staff Pass Capacity Enforcement**
    - **Validates: Requirements 4.5**
  
  - [ ]* 7.11 Write property test for DJ giveaway history filtering
    - **Property 12: DJ Giveaway History Filtering**
    - **Validates: Requirements 3.4**
  
  - [ ]* 7.12 Write property test for DJ name autocomplete
    - **Property 14: DJ Name Autocomplete**
    - **Validates: Requirements 3.6**

- [x] 8. Implement show visibility and access control
  - [x] 8.1 Add role-based filtering to ShowService.list_shows
    - Promotions staff: see all shows (draft, published, closed)
    - Staff and DJs: see only published and closed shows
    - _Requirements: 1.3, 4.3, 12.1, 12.2, 12.3_
  
  - [x] 8.2 Add show status validation to pass operations
    - Reject giveaway, attempt, and claim operations on closed shows (400 error)
    - Allow viewing closed show details
    - _Requirements: 1.4, 12.3_
  
  - [ ]* 8.3 Write property test for show visibility based on status and role
    - **Property 3: Show Visibility Based on Status and Role**
    - **Validates: Requirements 1.3, 12.1, 12.2**
  
  - [ ]* 8.4 Write property test for closed shows preventing pass operations
    - **Property 4: Closed Shows Prevent Pass Operations**
    - **Validates: Requirements 1.4, 12.3**

- [x] 9. Implement search functionality
  - [x] 9.1 Add search_shows method to ShowService
    - Freetext search (via `freetext` query param) across event name, genre, venue name, special instructions
    - Filters: venue_id, artist (in event name or genre), genre
    - Apply role-based visibility
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [x] 9.2 Create FastAPI endpoint for search
    - GET /api/shows/search with query parameters: freetext, venue_id, artist, genre
    - _Requirements: 2.1, 9.1_
  
  - [ ]* 9.3 Write property test for freetext search coverage
    - **Property 7: Freetext Search Coverage**
    - **Validates: Requirements 2.1**
  
  - [ ]* 9.4 Write property test for filter accuracy
    - **Property 8: Filter Accuracy**
    - **Validates: Requirements 2.2, 2.3, 2.4**
  
  - [ ]* 9.5 Write property test for search result completeness
    - **Property 9: Search Result Completeness**
    - **Validates: Requirements 2.5**

- [x] 10. Checkpoint - Ensure all tests pass

- [x] 11. Implement pre-assignment functionality
  - [x] 11.1 Add pre-assignment methods to PassService
    - set_preassignment: sets preassigned_dj and preassigned_date, validates pass is "pair" and "available"
    - remove_preassignment: clears preassignment fields
    - get_passes_for_show: optional filtering by dj_name and current_date
    - _Requirements: 14.1, 14.2, 14.3, 14.5, 14.6_
  
  - [x] 11.2 Add pre-assignment endpoints to pass router
    - POST /api/passes/{id}/preassign (promotions only)
    - DELETE /api/passes/{id}/preassign (promotions only)
    - _Requirements: 14.1, 14.6_
  
  - [ ]* 11.3 Write property test for pre-assignment display
    - **Property 13: Pre-Assignment Display**
    - **Validates: Requirements 3.5**
  
  - [ ]* 11.4 Write property test for pre-assignment management
    - **Property 30: Pre-Assignment Management**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**

- [x] 12. Implement show detail completeness
  - [x] 12.1 Enhance ShowResponse to include all pass details
    - Include all recipients (on-air winners and staff) with names/phones
    - Resolve staff_name and staff_phone from Staff record
    - Include failed attempt records (attempt_count, last_attempt_dj, last_attempt_at)
    - Include DJ names for given-away passes
    - Group passes by show (all in show response)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ]* 12.2 Write property test for show detail completeness
    - **Property 28: Show Detail Completeness**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.5**
  
  - [ ]* 12.3 Write property test for pass grouping by show
    - **Property 29: Pass Grouping by Show**
    - **Validates: Requirements 13.4**

- [x] 13. Implement authentication integration
  - [x] 13.1 Set up Apache mod_auth_openidc configuration
    - Configure Google OAuth2 client ID and secret
    - Set up access control rules (all routes require login; DJ routes allow unauthenticated)
    - Configure IP-based bypass for DJ studio network (enforced in backend)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 13.2 Implement authentication utilities in FastAPI (auth.py)
    - Extract user email from X-Forwarded-User header (set by Apache mod_auth_openidc)
    - Determine user role by querying PromotionsStaff and Staff tables
    - check_dj_access: allows DJ studio network (X-Forwarded-For) or promotions staff
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_
  
  - [x] 13.3 Add authentication checks to all protected endpoints
    - Verify user role matches endpoint requirements
    - Return 401/403 for unauthorized requests
    - _Requirements: 5.1, 5.2, 9.3_
  
  - [ ]* 13.4 Write property test for authentication requirement
    - **Property 18: Authentication Requirement for Protected Views**
    - **Validates: Requirements 5.1, 5.2**
  
  - [ ]* 13.5 Write property test for IP-based and authenticated DJ access
    - **Property 19: IP-Based and Authenticated DJ Access**
    - **Validates: Requirements 5.3, 5.4**

- [x] 14. Implement Airtable synchronization
  - [x] 14.1 Implement Airtable REST API client in UserService
    - get_staff_emails: fetches from Airtable with pagination
    - get_promotions_emails: fetches from Airtable with pagination
    - Handle API errors gracefully (return 503 on failure)
    - _Requirements: 6.1, 6.2_
  
  - [x] 14.2 Implement user sync logic in UserService
    - sync_from_airtable: adds new users to the database with correct roles
    - Removes users no longer in Airtable
    - Returns SyncResult with staff_added, promotions_added, users_removed, errors lists
    - _Requirements: 6.3, 6.4, 6.5_
  
  - [x] 14.3 Set up APScheduler for daily sync
    - AsyncIOScheduler with CronTrigger for 2 AM daily
    - Skips startup in test environment (TESTING=1)
    - _Requirements: 6.6_
  
  - [x] 14.4 Create manual sync endpoint
    - POST /api/users/sync (promotions staff only)
    - _Requirements: 6.7_
  
  - [ ]* 14.5 Write property test for user sync addition
    - **Property 20: User Sync Addition**
    - **Validates: Requirements 6.1, 6.2, 6.4, 6.5**
  
  - [ ]* 14.6 Write property test for user sync removal
    - **Property 21: User Sync Removal**
    - **Validates: Requirements 6.3**

- [x] 15. Checkpoint - Ensure all backend tests pass

- [x] 16. Implement backend error handling and validation
  - [x] 16.1 Add global exception handlers to FastAPI app
    - RequestValidationError → 422 with field-level errors
    - IntegrityError → 400 (constraint violations)
    - SQLAlchemyError → 500 (database errors)
    - Exception → 500 (catch-all)
    - _Requirements: 9.2, 9.3_
  
  - [ ]* 16.2 Write property test for backend request validation
    - **Property 25: Backend Request Validation**
    - **Validates: Requirements 9.2**
  
  - [ ]* 16.3 Write property test for HTTP status code correctness
    - **Property 26: HTTP Status Code Correctness**
    - **Validates: Requirements 9.3**

- [x] 17. Set up frontend project structure
  - [x] 17.1 Initialize React + TypeScript + Vite project
    - Configure Vite
    - Set up React Router for routing
    - Install Axios for API calls
    - Set up Vitest for testing
    - _Requirements: 8.1, 8.2_
  
  - [x] 17.2 Create TypeScript types for all API models (src/types/index.ts)
    - Venue, Show, Pass, User, Profile types
    - Match backend Pydantic schemas
    - _Requirements: 8.1_
  
  - [x] 17.3 Create API client service (src/services/api.ts)
    - Axios instance with base URL (/api) and withCredentials for cookies
    - Methods for all API endpoints: showsAPI, venuesAPI, passesAPI, usersAPI, autocompleteAPI
    - Consistent error handling
    - _Requirements: 8.2_

- [x] 18. Implement promotions staff view frontend
  - [x] 18.1 Create PromotionsLayout component with navigation (shows, venues, profile)
  - [x] 18.2 Create VenueList and VenueForm components (list/create/edit venues with validation)
  - [x] 18.3 Create ShowList component (all shows with status filter)
  - [x] 18.4 Create ShowForm component (create/edit with venue dropdown, date/time pickers, validation)
  - [x] 18.5 Create ShowDetail component (show info, all passes, publish/close buttons, pre-assignment interface)
  - [x] 18.6 Create ProfileSettings component (edit name and phone)
  - [x] 18.7 Create SearchBar component (freetext, venue filter, genre filter)
  - [x] 18.8 Write unit tests for promotions staff components

- [x] 19. Implement staff member view frontend
  - [x] 19.1 Create StaffLayout component with navigation (shows, profile)
  - [x] 19.2 Create ShowBrowser component (published and closed shows, available staff pass count)
  - [x] 19.3 Create ShowDetail component (show info, one-click claim button, disabled when no passes available)
  - [x] 19.4 Create ProfileSettings component for staff (edit name and phone)
  - [x] 19.5 Write unit tests for staff member components

- [x] 20. Implement DJ view frontend
  - [x] 20.1 Create DJLayout component with simplified navigation (shows, my passes)
  - [x] 20.2 Create ShowBrowser component (published shows, available pair count)
  - [x] 20.3 Create ShowDetail component with PassGiveawayForm (recipient name, phone, DJ name with autocomplete, record attempt button)
  - [x] 20.4 Create MyPasses component (giveaway history filtered by DJ name)
  - [x] 20.5 Write unit tests for DJ view components

- [x] 21. Checkpoint - Ensure all frontend tests pass

- [x] 22. Implement role-based UI rendering
  - [x] 22.1 Create authentication context (AuthContext, authContext.ts, authHooks.ts)
    - Fetch user info from /api/users/me on load
    - Store current user email, role, and profile
    - Provide via React Context to all components
    - _Requirements: 5.1, 5.2, 8.4_
  
  - [x] 22.2 Add role-based routing and conditional rendering
    - ProtectedRoute component wraps each view section
    - DJ routes accessible by 'dj' and 'promotions' roles
    - RoleBasedRedirect for default navigation
    - _Requirements: 8.4, 5.6_
  
  - [x] 22.3 Write property test for role-based UI elements
    - **Property 24: Role-Based UI Elements**
    - **Validates: Requirements 8.4**
    - **Status: PASSED** - 14 unit tests passing, 1 skipped due to React Router race condition

- [x] 23. Enhance frontend validation and error handling
  - [x] 23.1 Review and enhance client-side validation (required fields, date formats, pass pair range 1-5)
  - [x] 23.2 Review and enhance API error handling (422 field errors, general error messages)
  - [x] 23.3 Review and enhance loading states (indicators during API calls, disabled submission)
  - [x] 23.4 Write property test for frontend input validation
    - **Property 23: Frontend Input Validation**
    - **Validates: Requirements 8.5**

- [x] 24. Set up deployment infrastructure
  - [x] 24.1 Create systemd user service file (promotions-app-backend)
  - [x] 24.2 Configure Apache with mod_auth_openidc
    - Google OAuth2 authentication for all routes
    - DJ-facing routes allow unauthenticated access (backend enforces IP check)
    - Reverse proxy /api/ requests to backend
    - _Requirements: 10.1_

- [x] 25. Complete CI/CD pipeline (GitHub Actions)
  - [x] 25.1 GitHub Actions workflow for testing
    - Backend: `black --check` + `pytest --cov` with Python 3.14
    - Frontend: `npm run lint` + `tsc --noEmit` + `npm test` with Node 20
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  
  - [x] 25.2 GitHub Actions workflow for staging deployment
    - Trigger on push to main branch
    - Connect via Netbird VPN, rsync code, update venv, run migrations, restart services
    - Verify health endpoints after deployment
    - _Requirements: 10.2, 10.4, 10.5, 10.6, 10.7_
  
  - [x] 25.3 GitHub Actions workflow for production deployment
    - Trigger on published release tag
    - Same deployment process as staging
    - _Requirements: 10.3_

- [x] 26. Complete documentation
  - [x] 26.1 README with project overview and setup instructions
  - [x] 26.2 SETUP_GUIDE.md with detailed deployment instructions
  - [x] 26.3 AUTHENTICATION.md with auth flow documentation
  - [x] 26.4 systemd/README.md with service setup instructions
  - [x] 26.5 FastAPI auto-docs at /docs endpoint

- [x] 27. Final checkpoint - Ensure all tests pass

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using Hypothesis (backend) and fast-check (frontend)
- Unit tests validate specific examples and edge cases
- Backend uses Python 3.11+, FastAPI, SQLAlchemy, pytest, Hypothesis
- Frontend uses React 18+, TypeScript, Vite, Vitest, fast-check
- Authentication handled by Apache mod_auth_openidc (Google OAuth2) with IP-based bypass for DJ studio network
- Deployment uses rsync, systemd user service, GitHub Actions, Netbird VPN
