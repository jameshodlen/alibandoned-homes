# Makefile for Abandoned Homes Prediction System

.PHONY: setup up down logs update test clean

# Run the interactive setup wizard
setup:
	@echo "Running Setup Wizard..."
	@python scripts/setup_wizard.py

# Start the application in detached mode
up:
	@echo "Starting services..."
	@docker-compose up -d

# Stop all services
down:
	@echo "Stopping services..."
	@docker-compose down

# Tail logs
logs:
	@docker-compose logs -f

# Update code and rebuild
update:
	@echo "Pulling latest changes..."
	@git pull
	@echo "Rebuilding containers..."
	@docker-compose build
	@echo "Restarting services..."
	@docker-compose up -d

# Run tests (Backend)
test:
	@echo "Running backend tests..."
	@docker-compose exec backend pytest

# Clean up docker artifacts (use with caution)
clean:
	@echo "Cleaning up docker system..."
	@docker system prune -f
