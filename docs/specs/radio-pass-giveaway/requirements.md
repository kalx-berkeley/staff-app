# Requirements Document

## Introduction

This document specifies the requirements for a web-based pass giveaway management system for a community radio station. The system coordinates on-air pass giveaways between music venues, radio DJs, promotions staff, and radio station staff members. The system manages pass allocation, winner tracking, and staff pass claims across approximately 50 venues and 100 staff members.

## Glossary

- **System**: The promotions pass giveaway management web application
- **Promotions_Staff**: Radio station employees who manage venue relationships and pass giveaways
- **DJ**: Radio station on-air personality who gives away passes during broadcasts
- **Staff_Member**: Any employee of the radio station eligible to claim staff passes
- **Show**: A music event at a venue with allocated passes for giveaway
- **Pass_Pair**: Two passes allocated for on-air giveaway by a DJ
- **Staff_Pass**: Single pass allocated for claim by a staff member
- **Venue**: Music venue that provides passes for radio giveaways; stored as a separate entity in the database
- **Frontend**: Browser-based user interface application
- **Backend**: Python-based API server
- **mod_auth_openidc**: Apache module that implements Google OAuth2/OIDC authentication
- **Airtable**: External data source for staff and promotions staff lists (accessed via REST API)
- **Data_Store**: SQLite database for system data persistence

## Requirements

### Requirement 1: Show Management

**User Story:** As a promotions staff member, I want to create and manage show records, so that I can coordinate pass giveaways with venues.

#### Acceptance Criteria

1. WHEN a promotions staff member creates a new show, THE System SHALL store the event name, venue (by reference to an existing venue record), date, time, age restriction, wheelchair accessibility status, and number of pass pairs; genre and special instructions are optional
2. WHEN a promotions staff member creates a show, THE System SHALL set the show status to draft
3. WHEN a promotions staff member publishes a draft show, THE System SHALL make the show visible to DJs and staff members
4. WHEN a promotions staff member closes a show, THE System SHALL prevent any further pass giveaways, attempts, or claims for that show
5. THE System SHALL validate that the number of pass pairs is between 1 and 5 inclusive

### Requirement 2: Show Search and Discovery

**User Story:** As any system user, I want to search for shows by various criteria, so that I can quickly find relevant events.

#### Acceptance Criteria

1. WHEN a user searches by freetext (using the `freetext` query parameter), THE System SHALL return shows matching the search term in event name, genre, venue name, or special instructions
2. WHEN a user filters by venue, THE System SHALL return only shows at that venue
3. WHEN a user filters by artist, THE System SHALL return shows matching that artist in the event name or genre
4. WHEN a user filters by genre, THE System SHALL return shows matching that genre
5. THE System SHALL display search results with event name, venue, date, time, and available pass status

### Requirement 3: DJ Pass Giveaway

**User Story:** As a DJ, I want to record pass winners and giveaway attempts, so that promotions staff can track pass distribution.

#### Acceptance Criteria

1. WHEN a DJ gives away a pass pair, THE System SHALL record the recipient's name, recipient's phone number, the DJ who gave away the passes, and the date/time of the giveaway; the pass status SHALL be set to `given_away`
2. WHEN a DJ attempts but fails to give away passes, THE System SHALL record the attempt with the DJ name and date/time, increment the attempt count, and keep the pass pair `available`
3. WHEN a DJ views their assigned passes, THE System SHALL display all pass pairs that a promotions staff member has pre-assigned to them where the assigned DJ matches and the date is today's date or in the past
4. WHEN a DJ enters a DJ name for pass giveaway, THE System SHALL provide autocomplete suggestions based on DJs who have previously given away passes

### Requirement 4: Staff Pass Claims

**User Story:** As a radio station staff member, I want to claim staff passes to shows, so that I can attend events.

#### Acceptance Criteria

1. WHEN a staff member claims a staff pass, THE System SHALL associate the pass with the staff member's profile and record the claim timestamp
2. WHEN a staff member claims a staff pass, THE System SHALL mark that staff pass as `claimed`
3. WHEN a staff member views available shows, THE System SHALL display published and closed shows (both are visible to staff)
4. THE System SHALL allocate one staff pass for each pass pair allocated to a show (automatically when the show is created)
5. WHEN all staff passes for a show are claimed, THE System SHALL prevent further staff pass claims for that show

### Requirement 5: Authentication and Authorization

**User Story:** As a system administrator, I want role-based access control, so that users can only access appropriate functionality.

#### Acceptance Criteria

1. WHEN a user accesses the promotions staff view, THE System SHALL verify the user's email is present in the `promotions_staff` database table
2. WHEN a user accesses the staff member view, THE System SHALL verify the user's email is present in the `staff` database table
3. WHEN a user accesses the DJ view endpoints from the DJ studio IP network (CIDR range), THE System SHALL grant access without Google authentication (Apache `OIDCUnAuthAction pass` policy)
4. WHEN a user accesses the DJ view endpoints from outside the DJ studio IP network without authentication, THE System SHALL deny access
5. THE System SHALL use Apache `mod_auth_openidc` for Google OAuth authentication, passing the authenticated user's email to the backend via the `X-Forwarded-User` header
6. Promotions staff members SHALL also be able to access DJ view routes (for testing and support purposes)

### Requirement 6: User Synchronization

**User Story:** As a system administrator, I want automatic user list updates from Airtable, so that access permissions stay current with staffing changes.

#### Acceptance Criteria

1. WHEN the daily synchronization runs, THE System SHALL retrieve all records from the "KALX Active Staff Directory" Airtable table (configurable via `AIRTABLE_TABLE_NAME`)
2. WHEN the daily synchronization runs, THE System SHALL read each record's "Email address" field and "Department" multi-select field
3. WHEN a record's Department includes "Promotions", THE System SHALL upsert that email into the `promotions_staff` database table
4. WHEN a record's Department does not include "Promotions", THE System SHALL upsert that email into the `staff` database table
5. THE System SHALL run the synchronization process once per day at 2 AM via APScheduler
6. THE System SHALL allow manual triggering of the sync via `POST /api/users/sync` (promotions staff only)

### Requirement 7: Data Persistence

**User Story:** As a system administrator, I want reliable data storage, so that pass and show information is preserved.

#### Acceptance Criteria

1. WHEN the System stores show data, THE System SHALL persist it to the SQLite database
2. WHEN the System stores pass giveaway data, THE System SHALL persist it to the SQLite database
3. WHEN the System stores staff pass claims, THE System SHALL persist it to the SQLite database
4. WHEN the Backend restarts, THE System SHALL restore all data from the SQLite database
5. THE System SHALL maintain referential integrity between shows, passes, venues, promotions_staff, and staff records

### Requirement 8: Frontend Architecture

**User Story:** As a developer, I want a maintainable frontend codebase, so that junior developers can easily understand and extend the application.

#### Acceptance Criteria

1. THE Frontend SHALL use React with TypeScript and Vite, deployed as static files
2. THE Frontend SHALL communicate with the Backend via RESTful API endpoints using Axios
3. THE Frontend SHALL provide three distinct views: promotions staff view (`/promotions`), staff member view (`/staff`), and DJ view (`/dj`)
4. THE Frontend SHALL display appropriate UI elements and protect routes based on the authenticated user's role
5. THE Frontend SHALL validate user input before submitting to the Backend

### Requirement 9: Backend Architecture

**User Story:** As a developer, I want a well-structured Python backend, so that the API is maintainable and testable.

#### Acceptance Criteria

1. THE Backend SHALL expose RESTful API endpoints for all frontend operations
2. THE Backend SHALL validate all incoming requests using Pydantic before processing
3. THE Backend SHALL return appropriate HTTP status codes and error messages (200, 201, 400, 401, 403, 404, 422, 500)
4. THE Backend SHALL use SQLite for data persistence via SQLAlchemy ORM
5. THE Backend SHALL implement business logic for pass allocation and show management in service classes

### Requirement 10: Deployment and Infrastructure

**User Story:** As a system administrator, I want automated deployment, so that I can update the application without manual server access.

#### Acceptance Criteria

1. THE System SHALL run on a single server with the backend as a systemd user service and Apache handling authentication and reverse proxying
2. WHEN code is pushed to the main branch, THE System SHALL automatically deploy to the staging environment via GitHub Actions
3. WHEN a release is tagged, THE System SHALL deploy to the production environment via GitHub Actions
4. THE System SHALL use Netbird VPN for secure server connectivity during deployments
5. THE System SHALL use rsync to deploy backend code and built frontend static files
6. WHEN deploying, THE System SHALL back up the existing database, run Alembic migrations, and restart services
7. WHEN deploying, THE System SHALL verify that the backend health endpoint responds successfully

### Requirement 11: Testing

**User Story:** As a developer, I want thorough test coverage, so that I can confidently make changes to the codebase.

#### Acceptance Criteria

1. THE Backend SHALL include pytest tests for API endpoints and business logic
2. THE Backend SHALL run `black` formatting checks in CI
3. THE Frontend SHALL include Vitest unit tests for components and business logic
4. THE Frontend SHALL run ESLint and TypeScript type checking in CI
5. WHEN tests are run in CI/CD pipeline, THE System SHALL report test results and coverage
6. THE System SHALL prevent deployment if any tests, linting, or type checks fail

### Requirement 12: Show Status Workflow

**User Story:** As a promotions staff member, I want to control show visibility and pass availability, so that I can manage the giveaway lifecycle.

#### Acceptance Criteria

1. WHEN a show is in draft status, THE System SHALL only display it to promotions staff
2. WHEN a show is in published status, THE System SHALL display it to all authenticated users (promotions, staff, and DJs)
3. WHEN a show is in closed status, THE System SHALL prevent new pass giveaways, attempts, and claims; the show SHALL still be visible to all authenticated users
4. THE System SHALL allow promotions staff to transition shows from draft to published (and reject other transitions from draft)
5. THE System SHALL allow promotions staff to transition shows from published to closed (and reject other transitions from published)

### Requirement 13: Pass Winner Information

**User Story:** As a promotions staff member, I want to view pass winner and staff claim information, so that I can notify the venue.

#### Acceptance Criteria

1. WHEN a promotions staff member views a show, THE System SHALL display all pass pair recipients with names and phone numbers
2. WHEN a promotions staff member views a show, THE System SHALL display all staff members who claimed passes with names and phone numbers
3. WHEN a promotions staff member views a show, THE System SHALL display which pass pairs were attempted but not given away (including attempt count and DJ name)
4. THE System SHALL group pass information by show in the show response
5. THE System SHALL display the DJ who gave away each pass pair

### Requirement 14: Pass Pair Pre-Assignment

**User Story:** As a promotions staff member, I want to optionally pre-assign pass pairs to specific DJs and dates, so that I can coordinate special giveaway schedules.

#### Acceptance Criteria

1. WHEN a promotions staff member pre-assigns a pass pair, THE System SHALL record the assigned DJ name and date
2. WHEN a pass pair is pre-assigned, THE System SHALL display the pre-assignment (DJ name and date) in the pass response
3. WHEN a pass pair is not pre-assigned, it SHALL be available to any DJ
4. WHEN a pre-assigned pass pair is given away, THE System SHALL record the giveaway normally (pre-assignment is informational only)
5. WHEN a pre-assigned pass pair's assignment date has passed, the pass SHALL remain visible to that DJ (expired assignments are not automatically cleared)
6. THE System SHALL allow promotions staff to remove pre-assignments from pass pairs

### Requirement 15: Venue Management

**User Story:** As a promotions staff member, I want to manage venue records, so that shows can reference venues by ID.

#### Acceptance Criteria

1. THE System SHALL store venues in a dedicated table with name and address fields
2. WHEN a promotions staff member creates a venue, THE System SHALL enforce uniqueness of venue names
3. THE System SHALL allow listing, viewing, creating, and updating venues
4. WHEN creating a show, THE System SHALL require a valid venue_id referencing an existing venue

### Requirement 16: User Profile Management

**User Story:** As an authenticated user, I want to manage my profile, so that my name and phone number are stored for pass claims and show contacts.

#### Acceptance Criteria

1. WHEN a promotions staff member or staff member authenticates, THE System SHALL maintain a profile record with their email, name, and phone
2. THE System SHALL allow authenticated users (promotions and staff) to view and update their name and phone via `GET /api/users/profile` and `PUT /api/users/profile`
3. WHEN a staff member claims a pass, THE System SHALL associate the pass with their staff profile record
4. WHEN a promotions staff member creates a show, THE System SHALL associate the show with their promotions staff profile record
