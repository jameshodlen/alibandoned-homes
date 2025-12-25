/**
 * End-to-end tests with Cypress
 * 
 * =============================================================================
 * END-TO-END TESTING
 * =============================================================================
 * 
 * E2E tests verify complete user workflows:
 * - Real browser environment
 * - Real API communication
 * - Full application stack
 * 
 * Trade-offs:
 * + Catch integration issues
 * + Test real user experience
 * - Slow (seconds to minutes)
 * - More brittle (many failure points)
 * - Expensive to maintain
 * 
 * Best practices:
 * - Test critical user journeys
 * - Use data-testid for reliable selectors
 * - Setup clean test data
 * - Handle async with cy.wait or assertions
 * 
 * =============================================================================
 * CYPRESS COMMANDS
 * =============================================================================
 * 
 * Navigation:
 *   cy.visit(url)          - Visit a page
 *   cy.go('back')          - Navigate back
 * 
 * Querying:
 *   cy.get(selector)       - Get element by CSS selector
 *   cy.contains(text)      - Find by text content
 *   cy.find(selector)      - Find within element
 * 
 * Actions:
 *   .click()               - Click element
 *   .type(text)            - Type into input
 *   .select(value)         - Select dropdown option
 *   .check() / .uncheck()  - Toggle checkbox
 *   .trigger(event)        - Trigger DOM event
 * 
 * Assertions:
 *   .should('exist')       - Element exists
 *   .should('be.visible')  - Element is visible
 *   .should('have.length', n) - Number of elements
 *   .should('contain', text)  - Contains text
 * 
 * Waiting:
 *   cy.wait(ms)            - Wait fixed time (avoid!)
 *   cy.wait('@alias')      - Wait for network request
 *   .should()              - Implicit retry/wait
 * 
 * =============================================================================
 */

// =============================================================================
// TEST SETUP
// =============================================================================

describe('Complete User Workflow', () => {
  beforeEach(() => {
    // Setup: Clear database, seed test data
    // cy.task() runs code in Node.js context
    cy.task('db:seed');
    
    // Intercept API calls for monitoring
    cy.intercept('GET', '/api/v1/locations*').as('getLocations');
    cy.intercept('POST', '/api/v1/locations').as('createLocation');
    cy.intercept('POST', '/api/v1/predictions*').as('createPrediction');
    
    // Visit the app
    cy.visit('/');
    
    // Wait for initial data load
    cy.wait('@getLocations');
  });


  // ===========================================================================
  // MAP INTERACTION TESTS
  // ===========================================================================

  describe('Map Interaction', () => {
    it('displays the map on page load', () => {
      // Verify map container exists
      cy.get('[data-testid="map"]')
        .should('exist')
        .and('be.visible');
    });

    it('shows existing locations as markers', () => {
      // Should have markers from seeded data
      cy.get('.leaflet-marker-icon')
        .should('have.length.gt', 0);
    });

    it('shows location details when marker clicked', () => {
      // Click first marker
      cy.get('.leaflet-marker-icon').first().click();
      
      // Popup should appear with details
      cy.get('.leaflet-popup')
        .should('be.visible')
        .and('contain', 'Status');
    });

    it('changes map layer when selector clicked', () => {
      // Click satellite layer button
      cy.get('[data-testid="layer-selector"]')
        .contains('Satellite')
        .click();
      
      // Tile layer should change
      cy.get('.leaflet-tile-container img')
        .should('have.attr', 'src')
        .and('include', 'arcgisonline');
    });
  });


  // ===========================================================================
  // LOCATION CREATION WORKFLOW
  // ===========================================================================

  describe('Add Location Workflow', () => {
    it('allows user to add location from map click', () => {
      // Click on map to add location
      cy.get('[data-testid="map"]')
        .click(500, 300);
      
      // Modal should open
      cy.get('[role="dialog"]')
        .should('be.visible')
        .and('contain', 'Add Location');
      
      // Fill out form
      cy.get('select[name="condition"]')
        .select('partial_collapse');
      
      cy.get('select[name="accessibility"]')
        .select('moderate');
      
      cy.get('textarea[name="notes"]')
        .type('E2E test location - visible structural damage');
      
      // Submit form
      cy.get('button[type="submit"]')
        .click();
      
      // Wait for API response
      cy.wait('@createLocation')
        .its('response.statusCode')
        .should('eq', 201);
      
      // Success feedback
      cy.contains('Location created')
        .should('be.visible');
      
      // Modal should close
      cy.get('[role="dialog"]')
        .should('not.exist');
      
      // New marker should appear
      cy.get('.leaflet-marker-icon')
        .should('have.length.gt', 0);
    });

    it('validates required fields', () => {
      // Try to submit empty form
      cy.get('[data-testid="map"]').click(500, 300);
      
      cy.get('button[type="submit"]').click();
      
      // Validation error should appear
      cy.contains('required', { matchCase: false })
        .should('be.visible');
    });
  });


  // ===========================================================================
  // PHOTO UPLOAD WORKFLOW
  // ===========================================================================

  describe('Photo Upload Workflow', () => {
    it('allows photo upload via drag and drop', () => {
      // Open location detail modal
      cy.get('.leaflet-marker-icon').first().click();
      cy.contains('View Details').click();
      
      // Find dropzone
      cy.get('[data-testid="photo-dropzone"]')
        .should('be.visible');
      
      // Upload file via selectFile command
      cy.get('input[type="file"]')
        .selectFile('cypress/fixtures/test-house.jpg', { force: true });
      
      // Upload progress should show
      cy.contains('Uploading')
        .should('be.visible');
      
      // Success message
      cy.contains('Upload complete', { timeout: 10000 })
        .should('be.visible');
    });

    it('shows preview before upload', () => {
      cy.get('.leaflet-marker-icon').first().click();
      cy.contains('View Details').click();
      
      cy.get('input[type="file"]')
        .selectFile('cypress/fixtures/test-house.jpg', { force: true });
      
      // Preview should appear
      cy.get('[data-testid="photo-preview"]')
        .should('be.visible');
    });
  });


  // ===========================================================================
  // PREDICTION WORKFLOW
  // ===========================================================================

  describe('Area Prediction Workflow', () => {
    it('generates area predictions using drawing tools', () => {
      // Enable draw mode
      cy.get('[title="Draw a rectangle"]')
        .click();
      
      // Draw rectangle on map
      cy.get('[data-testid="map"]')
        .trigger('mousedown', 300, 300)
        .trigger('mousemove', 500, 500)
        .trigger('mouseup');
      
      // Drawn area should appear
      cy.get('.leaflet-interactive')
        .should('exist');
      
      // Click predict button
      cy.contains('Predict Area')
        .click();
      
      // Wait for prediction job
      cy.wait('@createPrediction');
      
      // Progress indicator
      cy.contains('Processing', { timeout: 5000 })
        .should('be.visible');
      
      // Wait for completion (long timeout for ML inference)
      cy.contains('Prediction complete', { timeout: 60000 })
        .should('be.visible');
      
      // Heatmap should be visible
      cy.get('.leaflet-heatmap-layer')
        .should('exist');
    });
  });


  // ===========================================================================
  // ADMIN DASHBOARD
  // ===========================================================================

  describe('Admin Dashboard', () => {
    beforeEach(() => {
      cy.visit('/admin');
    });

    it('displays system statistics', () => {
      // Stats cards should be visible
      cy.contains('Total Locations')
        .should('be.visible');
      
      cy.contains('Confirmed')
        .should('be.visible');
      
      // Values should be loaded
      cy.get('[data-testid="stat-total"]')
        .should('not.contain', 'Loading');
    });

    it('shows model management table', () => {
      // Model table should exist
      cy.get('table')
        .should('be.visible')
        .and('contain', 'Version');
    });

    it('can trigger model retraining', () => {
      // Intercept training API
      cy.intercept('POST', '/api/v1/admin/models/train').as('triggerTraining');
      
      // Click retrain button
      cy.contains('Trigger Retraining')
        .click();
      
      // Confirm dialog if present
      cy.get('[role="dialog"]').then($dialog => {
        if ($dialog.is(':visible')) {
          cy.contains('Confirm').click();
        }
      });
      
      // Wait for API
      cy.wait('@triggerTraining');
      
      // Success message
      cy.contains('Training', { matchCase: false })
        .should('be.visible');
    });

    it('can activate a model version', () => {
      cy.intercept('POST', '/api/v1/admin/models/*/activate').as('activateModel');
      
      // Find inactive model and activate
      cy.get('table tbody tr')
        .contains('Inactive')
        .parent('tr')
        .within(() => {
          cy.contains('Activate').click();
        });
      
      cy.wait('@activateModel');
      
      // Row should now show Active
      cy.contains('Active')
        .should('be.visible');
    });
  });


  // ===========================================================================
  // NAVIGATION AND ROUTING
  // ===========================================================================

  describe('Navigation', () => {
    it('navigates between map and admin pages', () => {
      // Start on map
      cy.url().should('eq', Cypress.config().baseUrl + '/');
      
      // Go to admin
      cy.contains('Admin').click();
      cy.url().should('include', '/admin');
      
      // Back to map
      cy.contains('Map').click();
      cy.url().should('eq', Cypress.config().baseUrl + '/');
    });
  });
});


// =============================================================================
// CUSTOM COMMANDS (cypress/support/commands.js)
// =============================================================================

/**
 * Example custom commands:
 * 
 * // Login command
 * Cypress.Commands.add('login', (username, password) => {
 *   cy.visit('/login');
 *   cy.get('[name="username"]').type(username);
 *   cy.get('[name="password"]').type(password);
 *   cy.get('button[type="submit"]').click();
 * });
 * 
 * // API auth command
 * Cypress.Commands.add('apiLogin', () => {
 *   return cy.request({
 *     method: 'POST',
 *     url: '/api/auth/login',
 *     body: { username: 'test', password: 'test' }
 *   }).then((response) => {
 *     window.localStorage.setItem('token', response.body.token);
 *   });
 * });
 */


// =============================================================================
// E2E TESTING BEST PRACTICES
// =============================================================================

/**
 * E2E TESTING BEST PRACTICES:
 * 
 * 1. USE DATA-TESTID FOR STABLE SELECTORS
 *    - CSS selectors are brittle
 *    - data-testid won't change with styling
 * 
 * 2. WAIT FOR API, NOT TIME
 *    Bad:  cy.wait(5000)
 *    Good: cy.wait('@apiAlias')
 * 
 * 3. ISOLATE TESTS
 *    - Each test should seed its own data
 *    - Don't depend on prior tests
 * 
 * 4. TEST CRITICAL PATHS
 *    - Don't test every permutation
 *    - Focus on main user journeys
 * 
 * 5. HANDLE FLAKINESS
 *    - Use retries for network issues
 *    - Increase timeouts for slow operations
 *    - Use { force: true } for hidden elements
 * 
 * 6. USE PAGE OBJECTS FOR COMPLEX FLOWS
 *    - Encapsulate selectors and actions
 *    - Reuse across tests
 */
