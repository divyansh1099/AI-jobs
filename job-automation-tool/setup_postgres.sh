#!/bin/bash

# PostgreSQL Setup Script for Job Automation Tool
echo "🐘 Setting up PostgreSQL for Job Automation Tool..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found. Installing PostgreSQL..."
    
    # Install PostgreSQL using Homebrew (macOS)
    if command -v brew &> /dev/null; then
        brew install postgresql@15
        brew services start postgresql@15
    else
        echo "❌ Homebrew not found. Please install PostgreSQL manually:"
        echo "   macOS: brew install postgresql@15"
        echo "   Ubuntu: sudo apt-get install postgresql postgresql-contrib"
        echo "   CentOS: sudo yum install postgresql postgresql-server"
        exit 1
    fi
else
    echo "✅ PostgreSQL found"
fi

# Start PostgreSQL service
echo "🚀 Starting PostgreSQL service..."
if command -v brew &> /dev/null; then
    brew services start postgresql@15
fi

# Wait a moment for service to start
sleep 2

# Create database and user
echo "📊 Creating database and user..."
psql postgres << EOF
-- Create database
CREATE DATABASE job_automation;

-- Create user (if not exists)
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
      CREATE USER postgres WITH PASSWORD 'password';
   END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE job_automation TO postgres;

-- Connect to the database and grant schema privileges
\c job_automation
GRANT ALL ON SCHEMA public TO postgres;

EOF

if [ $? -eq 0 ]; then
    echo "✅ Database setup completed successfully!"
    echo ""
    echo "Database Details:"
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  Database: job_automation"
    echo "  User: postgres"
    echo "  Password: password"
    echo ""
    echo "You can now start the application with: cd backend && python main.py"
else
    echo "❌ Database setup failed. Please check PostgreSQL installation."
    exit 1
fi