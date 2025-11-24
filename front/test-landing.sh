#!/bin/bash

# Landing Page Test Script
# This script helps test the landing page by managing authentication tokens

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Landing Page Test Helper Script     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Function to show menu
show_menu() {
    echo -e "${GREEN}Choose an option:${NC}"
    echo ""
    echo "1) 🚀 Start dev server"
    echo "2) 🧹 Clear tokens (prepare for landing page test)"
    echo "3) 📊 Check authentication status"
    echo "4) 🏗️  Build for production"
    echo "5) ✅ Run typecheck"
    echo "6) 📖 Show documentation"
    echo "7) 🌐 Open test helper in browser"
    echo "8) ❌ Exit"
    echo ""
    echo -n "Enter your choice [1-8]: "
}

# Function to start dev server
start_dev() {
    echo -e "${YELLOW}Starting development server...${NC}"
    echo -e "${BLUE}The app will be available at: http://localhost:5173${NC}"
    echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"
    echo ""
    npm run dev
}

# Function to clear tokens
clear_tokens() {
    echo -e "${YELLOW}This will help you test the landing page by clearing auth tokens.${NC}"
    echo ""
    echo -e "${GREEN}Steps to clear tokens:${NC}"
    echo "1. Open your browser to http://localhost:5173"
    echo "2. Open Developer Console (F12)"
    echo "3. Run these commands:"
    echo ""
    echo -e "${BLUE}   localStorage.removeItem('auth_token');${NC}"
    echo -e "${BLUE}   localStorage.removeItem('token_timestamp');${NC}"
    echo -e "${BLUE}   location.reload();${NC}"
    echo ""
    echo -e "${GREEN}OR${NC}"
    echo ""
    echo "Open test-landing.html in your browser and click 'Clear Tokens'"
    echo ""
    echo -e "${GREEN}After clearing, you should see:${NC}"
    echo "  ✓ Landing page with hero section"
    echo "  ✓ Features carousel"
    echo "  ✓ 'Get Started' and 'Sign In' buttons"
    echo ""
    read -p "Press Enter to continue..."
}

# Function to check authentication status
check_auth() {
    echo -e "${YELLOW}Checking authentication setup...${NC}"
    echo ""

    if [ -f "src/services/authService.ts" ]; then
        echo -e "${GREEN}✓ Auth service found${NC}"
    else
        echo -e "${RED}✗ Auth service not found${NC}"
    fi

    if [ -f "src/components/LandingPage.tsx" ]; then
        echo -e "${GREEN}✓ Landing page component found${NC}"
    else
        echo -e "${RED}✗ Landing page component not found${NC}"
    fi

    if [ -f "src/components/ui/features.tsx" ]; then
        echo -e "${GREEN}✓ Features component found${NC}"
    else
        echo -e "${RED}✗ Features component not found${NC}"
    fi

    echo ""
    echo -e "${BLUE}To test the landing page:${NC}"
    echo "1. Make sure you're not authenticated (clear tokens)"
    echo "2. Landing page should display automatically"
    echo "3. Click 'Get Started' to see auth form"
    echo "4. Click 'Back to home' to return to landing"
    echo ""
    read -p "Press Enter to continue..."
}

# Function to build
build_production() {
    echo -e "${YELLOW}Building for production...${NC}"
    npm run build
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Build successful!${NC}"
        echo -e "${BLUE}Output directory: dist/${NC}"
    else
        echo ""
        echo -e "${RED}✗ Build failed${NC}"
    fi
    echo ""
    read -p "Press Enter to continue..."
}

# Function to run typecheck
run_typecheck() {
    echo -e "${YELLOW}Running TypeScript type check...${NC}"
    npm run typecheck
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ No TypeScript errors!${NC}"
    else
        echo ""
        echo -e "${RED}✗ TypeScript errors found${NC}"
    fi
    echo ""
    read -p "Press Enter to continue..."
}

# Function to show documentation
show_docs() {
    echo -e "${GREEN}📖 Documentation Files:${NC}"
    echo ""
    echo "1. SUMMARY.md - Implementation summary"
    echo "2. LANDING_PAGE.md - Complete documentation"
    echo "3. QUICKSTART_LANDING.md - Quick start guide"
    echo "4. ICONS_REFERENCE.md - Icons reference"
    echo "5. src/components/ui/README.md - UI components guide"
    echo ""
    echo -e "${YELLOW}To read a file:${NC}"
    echo "  cat SUMMARY.md"
    echo "  cat LANDING_PAGE.md"
    echo ""
    read -p "Press Enter to continue..."
}

# Function to open test helper
open_test_helper() {
    echo -e "${YELLOW}Opening test helper in browser...${NC}"

    # Detect OS and open browser
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v xdg-open > /dev/null; then
            xdg-open test-landing.html
        elif command -v gnome-open > /dev/null; then
            gnome-open test-landing.html
        else
            echo -e "${YELLOW}Could not detect browser opener.${NC}"
            echo "Please manually open: test-landing.html"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        open test-landing.html
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        start test-landing.html
    else
        echo -e "${YELLOW}Could not detect OS.${NC}"
        echo "Please manually open: test-landing.html"
    fi

    echo ""
    echo -e "${GREEN}Use the test helper to:${NC}"
    echo "  • Clear authentication tokens"
    echo "  • Check authentication status"
    echo "  • View manual commands"
    echo ""
    read -p "Press Enter to continue..."
}

# Main loop
while true; do
    clear
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Landing Page Test Helper Script     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    show_menu
    read choice

    case $choice in
        1)
            start_dev
            ;;
        2)
            clear_tokens
            ;;
        3)
            check_auth
            ;;
        4)
            build_production
            ;;
        5)
            run_typecheck
            ;;
        6)
            show_docs
            ;;
        7)
            open_test_helper
            ;;
        8)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please choose 1-8.${NC}"
            sleep 2
            ;;
    esac
done
